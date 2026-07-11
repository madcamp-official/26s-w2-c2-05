from typing import Iterator
from sqlmodel import Session
from .db import engine


def get_db() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
