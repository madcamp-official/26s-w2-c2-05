from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel

from ..deps import get_db, get_current_user
from ..models import Project, ProjectMember, User
from .. import github_client

router = APIRouter()


class ProjectOut(BaseModel):
    id: str
    name: str
    content: str
    github_repo: str | None
    created_at: datetime
    role: str


def _to_project_out(project: Project, role: str) -> ProjectOut:
    return ProjectOut(
        id=project.id,
        name=project.name,
        content=project.content,
        github_repo=project.github_repo,
        created_at=project.created_at,
        role=role,
    )


class CreateProjectRequest(BaseModel):
    name: str


class UpdateContentRequest(BaseModel):
    content: str


class SetGithubRepoRequest(BaseModel):
    repo: str


class InviteMemberRequest(BaseModel):
    username: str


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
def update_project_content(
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
    project.content = req.content
    db.add(project)
    db.commit()
    db.refresh(project)
    return _to_project_out(project, member.role)


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
    if db.get(ProjectMember, (project_id, user.user_id)) is None:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다")
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

    token = github_client.decrypt_token(owner.github_token_encrypted)
    try:
        github_client.push_file(
            token=token,
            repo=project.github_repo,
            path="CLAUDE.md",
            content=project.content,
            message=f"Update CLAUDE.md via {project.name}",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}
