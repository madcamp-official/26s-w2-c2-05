from pathlib import Path
from sqlmodel import SQLModel, create_engine

DB_PATH = Path(__file__).parent / "app.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
