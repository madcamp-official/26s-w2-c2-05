from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from ..deps import get_current_user, get_db
from ..models import ProjectMember, ProjectRevision, Skill, User

router = APIRouter()


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc)


class SkillOut(BaseModel):
    id: str
    name: str
    description: str
    steps_content: str
    created_at: datetime
    updated_at: datetime


def _to_skill_out(skill: Skill) -> SkillOut:
    return SkillOut(
        id=skill.id,
        name=skill.name,
        description=skill.description,
        steps_content=skill.steps_content,
        created_at=_as_utc(skill.created_at),
        updated_at=_as_utc(skill.updated_at),
    )


class UpdateSkillRequest(BaseModel):
    name: str
    description: str
    steps_content: str


@router.get("/projects/{project_id}/skills", response_model=list[SkillOut])
def list_skills(
    project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[SkillOut]:
    if db.get(ProjectMember, (project_id, user.user_id)) is None:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다")
    skills = db.exec(select(Skill).where(Skill.project_id == project_id)).all()
    return [_to_skill_out(s) for s in skills]


@router.get("/projects/{project_id}/skills/{skill_id}", response_model=SkillOut)
def get_skill(
    project_id: str,
    skill_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SkillOut:
    if db.get(ProjectMember, (project_id, user.user_id)) is None:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다")
    skill = db.get(Skill, skill_id)
    if skill is None or skill.project_id != project_id:
        raise HTTPException(status_code=404, detail="스킬을 찾을 수 없습니다")
    return _to_skill_out(skill)


@router.put("/projects/{project_id}/skills/{skill_id}", response_model=SkillOut)
def update_skill(
    project_id: str,
    skill_id: str,
    req: UpdateSkillRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SkillOut:
    if db.get(ProjectMember, (project_id, user.user_id)) is None:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다")
    skill = db.get(Skill, skill_id)
    if skill is None or skill.project_id != project_id:
        raise HTTPException(status_code=404, detail="스킬을 찾을 수 없습니다")
    skill.name = req.name
    skill.description = req.description
    skill.steps_content = req.steps_content
    skill.updated_at = datetime.utcnow()
    db.add(skill)
    db.add(
        ProjectRevision(
            project_id=project_id,
            user_id=user.user_id,
            content=req.steps_content,
            target="skill",
            skill_id=skill.id,
        )
    )
    db.commit()
    db.refresh(skill)
    return _to_skill_out(skill)


@router.delete("/projects/{project_id}/skills/{skill_id}")
def delete_skill(
    project_id: str,
    skill_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    if db.get(ProjectMember, (project_id, user.user_id)) is None:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다")
    skill = db.get(Skill, skill_id)
    if skill is None or skill.project_id != project_id:
        raise HTTPException(status_code=404, detail="스킬을 찾을 수 없습니다")
    db.delete(skill)
    db.commit()
    return {"ok": True}
