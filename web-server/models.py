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
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Project(SQLModel, table=True):
    __tablename__ = "projects"
    id: str = Field(default_factory=new_id, primary_key=True)
    name: str
    content: str = Field(default=DEFAULT_MD)
    created_at: datetime = Field(default_factory=datetime.utcnow)