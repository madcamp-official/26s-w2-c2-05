from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel

from ..deps import get_db
from ..models import Project

router = APIRouter()


class CreateProjectRequest(BaseModel):
    name: str


class UpdateContentRequest(BaseModel):
    content: str


@router.post("/projects", response_model=Project)
def create_project(req: CreateProjectRequest, db: Session = Depends(get_db)) -> Project:
    project = Project(name=req.name)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/projects", response_model=list[Project])
def list_projects(db: Session = Depends(get_db)) -> list[Project]:
    return db.exec(select(Project)).all()


@router.get("/projects/{project_id}", response_model=Project)
def get_project(project_id: str, db: Session = Depends(get_db)) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    return project


@router.put("/projects/{project_id}", response_model=Project)
def update_project_content(
    project_id: str, req: UpdateContentRequest, db: Session = Depends(get_db)
) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    project.content = req.content
    db.add(project)
    db.commit()
    db.refresh(project)
    return project
