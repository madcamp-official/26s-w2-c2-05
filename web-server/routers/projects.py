import json
from datetime import datetime, timezone
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel

from ..deps import get_db, get_current_user
from ..models import Project, ProjectMember, ProjectRevision, Skill, User
from .. import ai_client, github_client
from .presence import manager

router = APIRouter()


def _as_utc(dt: datetime) -> datetime:
    # SQLite는 tzinfo를 저장하지 않아 DB에서 읽어온 datetime은 항상 naive로
    # 돌아온다. 우리 모델은 항상 UTC로 저장하므로(default_factory=datetime.utcnow),
    # 여기서 tzinfo를 명시적으로 붙여줘야 JSON 응답에 "Z"/"+00:00"이 붙고,
    # 프론트에서 new Date(...)가 이를 로컬 시간으로 오인하지 않는다.
    return dt.replace(tzinfo=timezone.utc)


class ProjectOut(BaseModel):
    id: str
    name: str
    content: str
    hooks_content: str
    github_repo: str | None
    created_at: datetime
    updated_at: datetime
    role: str


def _to_project_out(project: Project, role: str) -> ProjectOut:
    return ProjectOut(
        id=project.id,
        name=project.name,
        content=project.content,
        hooks_content=project.hooks_content,
        github_repo=project.github_repo,
        created_at=_as_utc(project.created_at),
        updated_at=_as_utc(project.updated_at),
        role=role,
    )


class CreateProjectRequest(BaseModel):
    name: str


class UpdateContentRequest(BaseModel):
    content: str
    expected_updated_at: datetime | None = None


class UpdateHooksRequest(BaseModel):
    hooks_content: str
    expected_updated_at: datetime | None = None


class RenameProjectRequest(BaseModel):
    name: str


class SetGithubRepoRequest(BaseModel):
    repo: str


class InviteMemberRequest(BaseModel):
    username: str


class OnboardingRequest(BaseModel):
    principles: list[str]
    tech_stack: str
    team_or_individual: Literal["team", "individual"]
    indent_style: Literal["tabs", "spaces"]
    custom_requirements: str = ""


@router.post("/projects", response_model=ProjectOut)
def create_project(
    req: CreateProjectRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectOut:
    project = Project(name=req.name)
    db.add(project)
    db.add(ProjectMember(project_id=project.id, user_id=user.user_id, role="owner"))
    db.commit()
    db.refresh(project)
    return _to_project_out(project, "owner")


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[ProjectOut]:
    rows = db.exec(
        select(Project, ProjectMember.role)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(ProjectMember.user_id == user.user_id)
    ).all()
    return [_to_project_out(project, role) for project, role in rows]


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> ProjectOut:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    member = db.get(ProjectMember, (project_id, user.user_id))
    if member is None:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다")
    return _to_project_out(project, member.role)


@router.put("/projects/{project_id}", response_model=ProjectOut)
async def update_project_content(
    project_id: str,
    req: UpdateContentRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectOut:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    member = db.get(ProjectMember, (project_id, user.user_id))
    if member is None:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다")
    if (
        req.expected_updated_at is not None
        and _as_utc(project.updated_at) != req.expected_updated_at
    ):
        raise HTTPException(status_code=409, detail="다른 팀원이 먼저 저장했어요")
    project.content = req.content
    project.updated_at = datetime.utcnow()
    db.add(project)
    db.add(
        ProjectRevision(project_id=project_id, user_id=user.user_id, content=req.content)
    )
    db.commit()
    db.refresh(project)
    await manager.broadcast_content_updated(project_id, "content", user.username)
    return _to_project_out(project, member.role)

@router.post("/projects/{project_id}/onboarding", response_model=ProjectOut)
async def onboard_project(
    project_id: str,
    req: OnboardingRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectOut:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    member = db.get(ProjectMember, (project_id, user.user_id))
    if member is None:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다")
    try:
        content = await ai_client.generate_base_claude_md(req.model_dump())
    except ai_client.GeminiQuotaExceeded:
        raise HTTPException(status_code=429, detail="오늘의 요청 한도를 모두 사용했습니다")
    except httpx.HTTPStatusError:
        raise HTTPException(status_code=503, detail="잠시 후 다시 시도해주세요")
    project.content = content
    db.add(project)
    db.commit()
    db.refresh(project)
    return _to_project_out(project, member.role)

@router.put("/projects/{project_id}/hooks", response_model=ProjectOut)
async def update_project_hooks(
    project_id: str,
    req: UpdateHooksRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectOut:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    member = db.get(ProjectMember, (project_id, user.user_id))
    if member is None:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다")
    if (
        req.expected_updated_at is not None
        and _as_utc(project.updated_at) != req.expected_updated_at
    ):
        raise HTTPException(status_code=409, detail="다른 팀원이 먼저 저장했어요")
    try:
        json.loads(req.hooks_content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="올바른 JSON 형식이 아니에요")
    project.hooks_content = req.hooks_content
    project.updated_at = datetime.utcnow()
    db.add(project)
    db.add(
        ProjectRevision(
            project_id=project_id,
            user_id=user.user_id,
            content=req.hooks_content,
            target="hooks",
        )
    )
    db.commit()
    db.refresh(project)
    await manager.broadcast_content_updated(project_id, "hooks", user.username)
    return _to_project_out(project, member.role)


@router.put("/projects/{project_id}/name", response_model=ProjectOut)
def rename_project(
    project_id: str,
    req: RenameProjectRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectOut:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    member = db.get(ProjectMember, (project_id, user.user_id))
    if member is None or member.role != "owner":
        raise HTTPException(status_code=403, detail="owner만 이름을 수정할 수 있습니다")
    project.name = req.name
    db.add(project)
    db.commit()
    db.refresh(project)
    return _to_project_out(project, member.role)


class RevisionListOut(BaseModel):
    id: str
    created_at: datetime
    username: str
    target: str


class RevisionDetailOut(BaseModel):
    id: str
    created_at: datetime
    username: str
    content: str


@router.get("/projects/{project_id}/revisions", response_model=list[RevisionListOut])
def list_revisions(
    project_id: str,
    target: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[RevisionListOut]:
    if db.get(ProjectMember, (project_id, user.user_id)) is None:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다")
    query = (
        select(ProjectRevision, User)
        .join(User, User.user_id == ProjectRevision.user_id)
        .where(ProjectRevision.project_id == project_id)
    )
    if target is not None:
        query = query.where(ProjectRevision.target == target)
    rows = db.exec(query.order_by(ProjectRevision.created_at.desc())).all()
    return [
        RevisionListOut(
            id=r.id, created_at=_as_utc(r.created_at), username=u.username, target=r.target
        )
        for r, u in rows
    ]


@router.get(
    "/projects/{project_id}/revisions/{revision_id}", response_model=RevisionDetailOut
)
def get_revision(
    project_id: str,
    revision_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RevisionDetailOut:
    if db.get(ProjectMember, (project_id, user.user_id)) is None:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다")
    revision = db.get(ProjectRevision, revision_id)
    if revision is None or revision.project_id != project_id:
        raise HTTPException(status_code=404, detail="리비전을 찾을 수 없습니다")
    author = db.get(User, revision.user_id)
    return RevisionDetailOut(
        id=revision.id,
        created_at=_as_utc(revision.created_at),
        username=author.username,
        content=revision.content,
    )


@router.delete("/projects/{project_id}")
def delete_project(
    project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    member = db.get(ProjectMember, (project_id, user.user_id))
    if member is None or member.role != "owner":
        raise HTTPException(status_code=403, detail="owner만 삭제할 수 있습니다")

    revisions = db.exec(
        select(ProjectRevision).where(ProjectRevision.project_id == project_id)
    ).all()
    for revision in revisions:
        db.delete(revision)

    members = db.exec(
        select(ProjectMember).where(ProjectMember.project_id == project_id)
    ).all()
    for m in members:
        db.delete(m)

    db.delete(project)
    db.commit()
    return {"ok": True}


@router.post("/projects/{project_id}/invite")
def invite_member(
    project_id: str,
    req: InviteMemberRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    member = db.get(ProjectMember, (project_id, user.user_id))
    if member is None or member.role != "owner":
        raise HTTPException(status_code=403, detail="owner만 초대할 수 있습니다")
    target = db.exec(select(User).where(User.username == req.username)).first()
    if target is None:
        raise HTTPException(status_code=404, detail="존재하지 않는 사용자입니다")
    if db.get(ProjectMember, (project_id, target.user_id)) is not None:
        raise HTTPException(status_code=400, detail="이미 프로젝트 멤버입니다")
    db.add(ProjectMember(project_id=project_id, user_id=target.user_id, role="member"))
    db.commit()
    return {"ok": True}


@router.put("/projects/{project_id}/github", response_model=ProjectOut)
def set_github_repo(
    project_id: str,
    req: SetGithubRepoRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectOut:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    member = db.get(ProjectMember, (project_id, user.user_id))
    if member is None or member.role != "owner":
        raise HTTPException(status_code=403, detail="owner만 repo를 지정할 수 있습니다")
    project.github_repo = github_client.normalize_repo(req.repo)
    db.add(project)
    db.commit()
    db.refresh(project)
    return _to_project_out(project, member.role)


@router.post("/projects/{project_id}/push")
def push_to_github(
    project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    member = db.get(ProjectMember, (project_id, user.user_id))
    if member is None or member.role != "owner":
        raise HTTPException(status_code=403, detail="owner만 push를 실행할 수 있습니다")
    if not project.github_repo:
        raise HTTPException(status_code=400, detail="이 프로젝트에 연결된 GitHub repo가 없습니다")

    owner_membership = db.exec(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id, ProjectMember.role == "owner"
        )
    ).first()
    owner = db.get(User, owner_membership.user_id)
    if owner.github_token_encrypted is None:
        raise HTTPException(status_code=400, detail="프로젝트 owner가 GitHub 계정을 연결하지 않았습니다")

    try:
        json.loads(project.hooks_content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="hooks_content가 올바른 JSON 형식이 아니에요")

    token = github_client.decrypt_token(owner.github_token_encrypted)
    try:
        github_client.push_file(
            token=token,
            repo=project.github_repo,
            path="CLAUDE.md",
            content=project.content,
            message=f"Update CLAUDE.md via {project.name}",
        )
        github_client.push_file(
            token=token,
            repo=project.github_repo,
            path=".claude/settings.json",
            content=project.hooks_content,
            message=f"Update .claude/settings.json via {project.name}",
        )
        skills = db.exec(select(Skill).where(Skill.project_id == project_id)).all()
        for skill in skills:
            skill_md = (
                f"---\nname: {skill.name}\ndescription: {skill.description}\n---\n\n"
                f"{skill.steps_content}"
            )
            github_client.push_file(
                token=token,
                repo=project.github_repo,
                path=f".claude/skills/{skill.name}/SKILL.md",
                content=skill_md,
                message=f"Update skill {skill.name} via {project.name}",
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}
