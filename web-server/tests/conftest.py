import importlib

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

# "web-server" 디렉터리명에 하이픈이 있어 일반 import 문으로는 접근할 수 없어
# importlib로 문자열 임포트한다 (main.py 내부의 `from .db import` 같은 상대
# 임포트가 풀리려면 이 방식으로 패키지 소속을 맞춰줘야 함).
main = importlib.import_module("web-server.main")
deps = importlib.import_module("web-server.deps")
auth = importlib.import_module("web-server.auth")
models = importlib.import_module("web-server.models")

app = main.app
get_db = deps.get_db


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)

    def override_get_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with Session(engine) as session:
        yield session
    app.dependency_overrides.clear()


@pytest.fixture()
def client(db_session):
    return TestClient(app)


def make_user_and_token(db_session, username: str) -> tuple:
    user = models.User(username=username, password=auth.hash_password("pw1234"))
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    token = auth.create_access_token(user.user_id)
    return user, token


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
