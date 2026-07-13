import uuid
from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field

DEFAULT_MD = "# CLAUDE.md\n\n이 프로젝트에서 Claude가 지켜야 할 규칙을 적어보세요.\n"


def new_id() -> str:
    return str(uuid.uuid4())

class User(SQLModel, table=True):
    __tablename__ = "users"
    user_id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    password: str
    github_token_encrypted: Optional[str] = Field(default=None)
    github_username: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Project(SQLModel, table=True):
    __tablename__ = "projects"
    id: str = Field(default_factory=new_id, primary_key=True)
    name: str
    content: str = Field(default=DEFAULT_MD)
    github_repo: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ProjectMember(SQLModel, table=True):
    __tablename__ = "project_members"
    project_id: str = Field(foreign_key="projects.id", primary_key=True)
    user_id: int = Field(foreign_key="users.user_id", primary_key=True)
    role: str = Field(default="member")

class GithubOAuthState(SQLModel, table=True):
    __tablename__ = "github_oauth_states"
    state: str = Field(primary_key=True)
    user_id: int = Field(foreign_key="users.user_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ProjectRevision(SQLModel, table=True):
    __tablename__ = "project_revisions"
    id: str = Field(default_factory=new_id, primary_key=True)
    project_id: str = Field(foreign_key="projects.id")
    user_id: int = Field(foreign_key="users.user_id")
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)