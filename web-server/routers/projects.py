from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel

from ..deps import get_db, get_current_user
from ..models import Project, ProjectMember, User

router = APIRouter()


class CreateProjectRequest(BaseModel):
    name: str


class UpdateContentRequest(BaseModel):
    content: str


@router.post("/projects", response_model=Project)
def create_project(
    req: CreateProjectRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Project:
    project = Project(name=req.name)
    db.add(project)
    db.add(ProjectMember(project_id=project.id, user_id=user.user_id, role="owner"))
    db.commit()
    db.refresh(project)
    return project


@router.get("/projects", response_model=list[Project])
def list_projects(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[Project]:
    return db.exec(
        select(Project)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(ProjectMember.user_id == user.user_id)
    ).all()


@router.get("/projects/{project_id}", response_model=Project)
def get_project(
    project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    if db.get(ProjectMember, (project_id, user.user_id)) is None:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다")
    return project


@router.put("/projects/{project_id}", response_model=Project)
def update_project_content(
    project_id: str,
    req: UpdateContentRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    if db.get(ProjectMember, (project_id, user.user_id)) is None:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다")
    project.content = req.content
    db.add(project)
    db.commit()
    db.refresh(project)
    return project
