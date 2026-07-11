# 웹서버 + 프론트엔드 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 프로젝트 생성/참여, 세션 업로드(전처리 → AI 서버 호출 → 점진적 매칭 → 팀 추천 승격), 개인/팀 추천 조회, CLAUDE.md/hooks 다운로드를 처리하는 FastAPI 웹서버와, 그 위에서 동작하는 Next.js 프론트엔드를 만든다.

**Architecture:** SQLite + SQLModel로 데이터를 저장하는 FastAPI 웹서버가 AI 서버(`docs/superpowers/plans/2026-07-10-ai-server.md`)를 `httpx`로 내부 호출한다. Next.js는 `next.config.js`의 `rewrites()`로 `/api/*`를 웹서버에 통째로 프록시하는 BFF 역할만 하고, 브라우저는 항상 Next.js(같은 origin)에만 요청한다.

**Tech Stack:** Python, FastAPI, SQLModel, SQLite, `numpy`, `httpx`, `pytest`+`pytest-asyncio` / TypeScript, Next.js(App Router), `react-dropzone`, `vitest`+React Testing Library

## Global Constraints

- DB는 SQLite 파일 하나(`app.db`) — DESIGN.md "DB 스키마" 절
- 팀 추천 승격 임계값은 **2명 이상** (실제 팀 규모=2인팀 기준으로 3명에서 낮춤) — DESIGN.md D4
- 세션 업로드는 같은 (project, member) 조합에 대해 **최신 업로드로 교체(upsert)** — DESIGN.md D7
- 업로드 파일 크기 상한 10MB
- AI 서버는 `localhost:8001`로만 호출 (인터넷 노출 없음) — DESIGN.md "배포 구조" 절
- 유저 식별은 회원가입 없이 표시이름 입력 + 서버 발급 UUID를 `localStorage`에 저장 — DESIGN.md D5
- "자동 반영"은 웹 UI 상태 갱신을 의미하며, 로컬 파일 저장은 유저가 다운로드/복사하는 수동 단계 — DESIGN.md D1
- 이 플랜의 `web_server.preprocessing`은 Claude Code 세션 JSONL의 이벤트 필드(`type: tool_use`, `type: user`, `message.content`)를 일반적으로 알려진 구조로 가정해 구현한다. **Task 3 착수 전 팀의 실제 세션 JSONL 샘플 하나를 확보해서 필드명이 맞는지 반드시 대조할 것** — 다르면 Task 3의 파싱 로직만 교체하면 되고 이후 태스크는 영향받지 않는다 (인터페이스가 `extract_pattern_summary(text) -> str | None`로 고정되어 있으므로).

---

### Task 1: DB 모델 + 엔진

**Files:**
- Create: `web-server/models.py`
- Create: `web-server/db.py`
- Create: `web-server/requirements.txt`
- Create: `web-server/tests/test_models.py`
- Create: `web-server/tests/__init__.py` (빈 파일)
- Create: `web-server/__init__.py` (빈 파일)

**Interfaces:**
- Produces: `Project`, `Member`, `Session`, `RecommendationGroup`, `GroupMembership`, `PersonalRecommendation` (SQLModel 테이블), `engine`, `init_db()` — 이후 모든 태스크가 이 모델들을 가져다 씀

- [ ] **Step 1: requirements.txt 작성**

```text
fastapi==0.115.0
uvicorn[standard]==0.32.0
sqlmodel==0.0.22
numpy==2.1.0
httpx==0.27.0
python-multipart==0.0.12
pytest==8.3.0
pytest-asyncio==0.24.0
```

- [ ] **Step 2: 실패하는 테스트 작성**

```python
# web-server/tests/test_models.py
from sqlmodel import SQLModel, create_engine, Session as DBSession
from web_server.models import Project, Member


def _memory_engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine


def test_create_project_and_member():
    engine = _memory_engine()
    with DBSession(engine) as db:
        project = Project(name="26s-w2-c2-05", share_code="AB12CD")
        db.add(project)
        db.commit()
        db.refresh(project)

        member = Member(project_id=project.id, display_name="박서윤")
        db.add(member)
        db.commit()
        db.refresh(member)

        assert member.project_id == project.id
        assert db.get(Project, project.id).share_code == "AB12CD"


def test_recommendation_group_defaults_not_promoted():
    engine = _memory_engine()
    from web_server.models import RecommendationGroup

    with DBSession(engine) as db:
        project = Project(name="test", share_code="ZZ9999")
        db.add(project)
        db.commit()
        db.refresh(project)

        group = RecommendationGroup(
            project_id=project.id, type="hook", representative_text="npm test",
            event="PostToolUse", matcher="Edit",
        )
        db.add(group)
        db.commit()
        db.refresh(group)

        assert group.promoted is False
        assert group.representative_vector is None
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `cd web-server && python -m pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'web_server'`

- [ ] **Step 4: 모델 구현**

```python
# web-server/models.py
import uuid
from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


def new_id() -> str:
    return str(uuid.uuid4())


class Project(SQLModel, table=True):
    __tablename__ = "projects"
    id: str = Field(default_factory=new_id, primary_key=True)
    name: str
    share_code: str = Field(unique=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Member(SQLModel, table=True):
    __tablename__ = "members"
    id: str = Field(default_factory=new_id, primary_key=True)
    project_id: str = Field(foreign_key="projects.id")
    display_name: str
    joined_at: datetime = Field(default_factory=datetime.utcnow)


class Session(SQLModel, table=True):
    __tablename__ = "sessions"
    id: str = Field(default_factory=new_id, primary_key=True)
    project_id: str = Field(foreign_key="projects.id")
    member_id: str = Field(foreign_key="members.id")
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "processed"  # 'processed' | 'no_patterns'


class RecommendationGroup(SQLModel, table=True):
    __tablename__ = "recommendation_groups"
    id: str = Field(default_factory=new_id, primary_key=True)
    project_id: str = Field(foreign_key="projects.id")
    type: str  # 'hook' | 'claude_md'
    representative_text: str
    event: Optional[str] = None  # hook 타입만 사용
    matcher: Optional[str] = None  # hook 타입만 사용
    representative_vector: Optional[str] = None  # JSON-encoded list[float], claude_md만
    promoted: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class GroupMembership(SQLModel, table=True):
    __tablename__ = "group_memberships"
    group_id: str = Field(foreign_key="recommendation_groups.id", primary_key=True)
    member_id: str = Field(foreign_key="members.id", primary_key=True)
    session_id: str = Field(foreign_key="sessions.id")
    original_text: str
    reason: str
    confidence: str


class PersonalRecommendation(SQLModel, table=True):
    __tablename__ = "personal_recommendations"
    id: str = Field(default_factory=new_id, primary_key=True)
    session_id: str = Field(foreign_key="sessions.id")
    member_id: str = Field(foreign_key="members.id")
    type: str
    payload: str  # JSON-serialized candidate (schema는 AI 서버 plan의 Candidate와 동일)
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

```python
# web-server/db.py
from sqlmodel import SQLModel, create_engine

DATABASE_URL = "sqlite:///./app.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `cd web-server && python -m pytest tests/test_models.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: 커밋**

```bash
git add web-server/models.py web-server/db.py web-server/requirements.txt web-server/tests/test_models.py web-server/tests/__init__.py web-server/__init__.py
git commit -m "feat(web-server): add DB models and engine"
```

---

### Task 2: 프로젝트 생성/참여 API

**Files:**
- Create: `web-server/codes.py`
- Create: `web-server/deps.py`
- Create: `web-server/routers/__init__.py` (빈 파일)
- Create: `web-server/routers/projects.py`
- Create: `web-server/main.py`
- Create: `web-server/tests/test_projects.py`

**Interfaces:**
- Consumes: `Project`, `Member`, `engine` (Task 1)
- Produces: `get_db` (의존성), `app` (FastAPI 인스턴스), `POST /projects`, `POST /projects/{share_code}/join` — 프론트(Task 9)가 이 두 엔드포인트를 호출

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# web-server/tests/test_projects.py
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session as DBSession

from web_server.main import app
from web_server.deps import get_db


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    def override_get_db():
        with DBSession(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_create_and_join_project(client):
    create_resp = client.post("/projects", json={"name": "26s-w2-c2-05"})
    assert create_resp.status_code == 200
    share_code = create_resp.json()["share_code"]
    assert len(share_code) == 6

    join_resp = client.post(
        f"/projects/{share_code}/join", json={"display_name": "박서윤"}
    )
    assert join_resp.status_code == 200
    assert join_resp.json()["project_id"] == create_resp.json()["project_id"]


def test_join_with_invalid_code_returns_404(client):
    resp = client.post("/projects/ZZZZZZ/join", json={"display_name": "박서윤"})
    assert resp.status_code == 404
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd web-server && python -m pytest tests/test_projects.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'web_server.main'`

- [ ] **Step 3: 구현**

```python
# web-server/codes.py
import secrets
import string

ALPHABET = string.ascii_uppercase + string.digits


def generate_share_code(length: int = 6) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))
```

```python
# web-server/deps.py
from typing import Iterator
from sqlmodel import Session as DBSession
from .db import engine


def get_db() -> Iterator[DBSession]:
    with DBSession(engine) as session:
        yield session
```

```python
# web-server/routers/projects.py
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session as DBSession, select
from pydantic import BaseModel

from ..deps import get_db
from ..models import Project, Member
from ..codes import generate_share_code

router = APIRouter()


class CreateProjectRequest(BaseModel):
    name: str


class CreateProjectResponse(BaseModel):
    project_id: str
    share_code: str


@router.post("/projects", response_model=CreateProjectResponse)
def create_project(req: CreateProjectRequest, db: DBSession = Depends(get_db)):
    project = Project(name=req.name, share_code=generate_share_code())
    db.add(project)
    db.commit()
    db.refresh(project)
    return CreateProjectResponse(project_id=project.id, share_code=project.share_code)


class JoinProjectRequest(BaseModel):
    display_name: str


class JoinProjectResponse(BaseModel):
    member_id: str
    project_id: str


@router.post("/projects/{share_code}/join", response_model=JoinProjectResponse)
def join_project(
    share_code: str, req: JoinProjectRequest, db: DBSession = Depends(get_db)
):
    project = db.exec(select(Project).where(Project.share_code == share_code)).first()
    if project is None:
        raise HTTPException(status_code=404, detail="존재하지 않는 프로젝트 코드입니다")
    member = Member(project_id=project.id, display_name=req.display_name)
    db.add(member)
    db.commit()
    db.refresh(member)
    return JoinProjectResponse(member_id=member.id, project_id=project.id)
```

```python
# web-server/main.py
from fastapi import FastAPI
from .db import init_db
from .routers import projects

app = FastAPI()
app.include_router(projects.router)


@app.on_event("startup")
def on_startup():
    init_db()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd web-server && python -m pytest tests/test_projects.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 커밋**

```bash
git add web-server/codes.py web-server/deps.py web-server/routers/__init__.py web-server/routers/projects.py web-server/main.py web-server/tests/test_projects.py
git commit -m "feat(web-server): add project create/join endpoints"
```

---

### Task 3: 전처리 (JSONL → 패턴 요약)

**Files:**
- Create: `web-server/preprocessing.py`
- Create: `web-server/tests/test_preprocessing.py`

**Interfaces:**
- Consumes: 없음 (순수 함수, 표준 라이브러리만 사용)
- Produces: `extract_pattern_summary(jsonl_text: str) -> str | None` — Task 6이 이 함수를 호출

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# web-server/tests/test_preprocessing.py
import json
from web_server.preprocessing import extract_pattern_summary


def _line(event: dict) -> str:
    return json.dumps(event, ensure_ascii=False)


def test_extracts_repeated_bash_command():
    events = [
        _line({"type": "tool_use", "name": "Bash", "input": {"command": "npm test"}})
        for _ in range(4)
    ]
    summary = extract_pattern_summary("\n".join(events))
    assert summary is not None
    assert "npm test" in summary
    assert "4번" in summary


def test_extracts_repeated_user_correction():
    events = [
        _line({"type": "user", "message": {"content": "탭 말고 스페이스 써주세요"}})
        for _ in range(3)
    ]
    summary = extract_pattern_summary("\n".join(events))
    assert summary is not None
    assert "스페이스" in summary


def test_ignores_patterns_under_threshold():
    events = [
        _line({"type": "tool_use", "name": "Bash", "input": {"command": "ls"}})
        for _ in range(2)
    ]
    summary = extract_pattern_summary("\n".join(events))
    assert summary is None


def test_ignores_malformed_lines():
    summary = extract_pattern_summary("not valid json\n{}\n")
    assert summary is None
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd web-server && python -m pytest tests/test_preprocessing.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'web_server.preprocessing'`

- [ ] **Step 3: 구현**

```python
# web-server/preprocessing.py
import json
import re
from collections import Counter

# 3회 미만 반복은 노이즈로 간주하고 버린다 (원본 스펙 "판단 기준" 절)
REPEAT_THRESHOLD = 3

_CORRECTION_KEYWORDS = ["아니", "말고", "대신", "하지 마", "다시"]


def extract_pattern_summary(jsonl_text: str) -> str | None:
    """Claude Code 세션 JSONL에서 반복 패턴을 추출해 사람이 읽을 수 있는
    요약 텍스트로 만든다. 유의미한 패턴이 하나도 없으면 None을 반환한다.

    이벤트 필드 구조는 Task 3 착수 전 실제 세션 JSONL 샘플로 검증할 것
    (이 플랜의 Global Constraints 참고)."""
    bash_commands: list[str] = []
    user_corrections: list[str] = []

    for line in jsonl_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        if event.get("type") == "tool_use" and event.get("name") == "Bash":
            command = event.get("input", {}).get("command", "").strip()
            if command:
                bash_commands.append(_normalize_command(command))

        if event.get("type") == "user":
            text = _extract_user_text(event)
            if text and _looks_like_correction(text):
                user_corrections.append(text.strip())

    summary_lines: list[str] = []

    for command, count in Counter(bash_commands).most_common():
        if count >= REPEAT_THRESHOLD:
            summary_lines.append(f'- bash 커맨드 "{command}"를 {count}번 반복 실행함')

    for text, count in Counter(user_corrections).most_common():
        if count >= REPEAT_THRESHOLD:
            summary_lines.append(f'- 유저가 "{text}"라고 {count}번 다시 알려줌')

    if not summary_lines:
        return None
    return "\n".join(summary_lines)


def _normalize_command(command: str) -> str:
    return re.sub(r"\s+", " ", command).strip()


def _extract_user_text(event: dict) -> str:
    content = event.get("message", {}).get("content", "")
    if isinstance(content, list):
        parts = [c.get("text", "") for c in content if isinstance(c, dict)]
        return " ".join(parts)
    if isinstance(content, str):
        return content
    return ""


def _looks_like_correction(text: str) -> bool:
    return any(keyword in text for keyword in _CORRECTION_KEYWORDS)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd web-server && python -m pytest tests/test_preprocessing.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: 커밋**

```bash
git add web-server/preprocessing.py web-server/tests/test_preprocessing.py
git commit -m "feat(web-server): add rule-based pattern extraction"
```

---

### Task 4: AI 서버 클라이언트

**Files:**
- Create: `web-server/ai_client.py`
- Create: `web-server/tests/test_ai_client.py`

**Interfaces:**
- Consumes: 없음 (AI 서버 plan의 `/analyze`, `/embed` HTTP 계약에만 의존)
- Produces: `analyze(pattern_summary, client=None) -> dict`, `embed(text, client=None) -> list[float]` — Task 6이 이 함수들을 호출

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# web-server/tests/test_ai_client.py
import pytest
import httpx

from web_server import ai_client


@pytest.mark.asyncio
async def test_analyze_returns_parsed_json():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/analyze"
        return httpx.Response(200, json={"candidates": []})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://test"
    ) as fake_client:
        result = await ai_client.analyze("패턴 요약", client=fake_client)

    assert result == {"candidates": []}


@pytest.mark.asyncio
async def test_embed_returns_vector():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/embed"
        return httpx.Response(200, json={"vector": [0.1, 0.2]})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://test"
    ) as fake_client:
        result = await ai_client.embed("스페이스로 들여쓰기 통일", client=fake_client)

    assert result == [0.1, 0.2]


@pytest.mark.asyncio
async def test_analyze_raises_on_ai_server_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"detail": "잠시 후 다시 시도해주세요"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://test"
    ) as fake_client:
        with pytest.raises(httpx.HTTPStatusError):
            await ai_client.analyze("패턴 요약", client=fake_client)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd web-server && python -m pytest tests/test_ai_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'web_server.ai_client'`

- [ ] **Step 3: 구현**

```python
# web-server/ai_client.py
import os
import httpx

AI_SERVER_URL = os.environ.get("AI_SERVER_URL", "http://localhost:8001")


async def analyze(pattern_summary: str, client: httpx.AsyncClient | None = None) -> dict:
    owns_client = client is None
    client = client or httpx.AsyncClient(base_url=AI_SERVER_URL, timeout=20.0)
    try:
        resp = await client.post("/analyze", json={"pattern_summary": pattern_summary})
        resp.raise_for_status()
        return resp.json()
    finally:
        if owns_client:
            await client.aclose()


async def embed(text: str, client: httpx.AsyncClient | None = None) -> list[float]:
    owns_client = client is None
    client = client or httpx.AsyncClient(base_url=AI_SERVER_URL, timeout=20.0)
    try:
        resp = await client.post("/embed", json={"text": text})
        resp.raise_for_status()
        return resp.json()["vector"]
    finally:
        if owns_client:
            await client.aclose()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd web-server && python -m pytest tests/test_ai_client.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋**

```bash
git add web-server/ai_client.py web-server/tests/test_ai_client.py
git commit -m "feat(web-server): add AI server HTTP client"
```

---

### Task 5: 매칭/병합 로직

**Files:**
- Create: `web-server/matching.py`
- Create: `web-server/tests/test_matching.py`

**Interfaces:**
- Consumes: `RecommendationGroup`, `GroupMembership` (Task 1)
- Produces: `normalize_command`, `cosine_similarity`, `match_hook_candidate(...)`, `match_claude_md_candidate(...)` — Task 6이 이 함수들을 호출

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# web-server/tests/test_matching.py
import pytest
from sqlmodel import SQLModel, create_engine, Session as DBSession

from web_server.models import Project, Member, Session as SessionModel
from web_server.matching import (
    match_hook_candidate,
    match_claude_md_candidate,
    cosine_similarity,
)


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with DBSession(engine) as session:
        yield session


def _make_project(db):
    project = Project(name="test", share_code="AAA111")
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def _make_member_session(db, project, member_name):
    member = Member(project_id=project.id, display_name=member_name)
    db.add(member)
    db.commit()
    db.refresh(member)

    sess = SessionModel(project_id=project.id, member_id=member.id)
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return member, sess


def test_cosine_similarity_identical_vectors_is_one():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_vectors_is_zero():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_hook_group_not_promoted_with_one_member(db):
    project = _make_project(db)
    member, sess = _make_member_session(db, project, "지민")

    group = match_hook_candidate(
        db, project.id, member.id, sess.id,
        "PostToolUse", "Edit", "npm test", "매번 실행함", "high",
    )
    assert group.promoted is False


def test_hook_group_promoted_at_two_distinct_members(db):
    project = _make_project(db)
    member1, sess1 = _make_member_session(db, project, "지민")
    member2, sess2 = _make_member_session(db, project, "태호")

    match_hook_candidate(
        db, project.id, member1.id, sess1.id,
        "PostToolUse", "Edit", "npm test", "r1", "high",
    )
    group = match_hook_candidate(
        db, project.id, member2.id, sess2.id,
        "PostToolUse", "Edit", "npm  test", "r2", "high",  # 공백 차이는 정규화로 흡수
    )
    assert group.promoted is True
    assert group.event == "PostToolUse"
    assert group.matcher == "Edit"


def test_different_event_does_not_merge(db):
    project = _make_project(db)
    member1, sess1 = _make_member_session(db, project, "지민")
    member2, sess2 = _make_member_session(db, project, "태호")

    match_hook_candidate(
        db, project.id, member1.id, sess1.id,
        "PostToolUse", "Edit", "npm test", "r1", "high",
    )
    group2 = match_hook_candidate(
        db, project.id, member2.id, sess2.id,
        "PreToolUse", "Edit", "npm test", "r2", "high",  # event가 다름 → 다른 그룹
    )
    assert group2.promoted is False


def test_same_member_reupload_does_not_double_count(db):
    project = _make_project(db)
    member, sess = _make_member_session(db, project, "지민")

    match_hook_candidate(
        db, project.id, member.id, sess.id,
        "PostToolUse", "Edit", "npm test", "r1", "high",
    )
    group = match_hook_candidate(
        db, project.id, member.id, sess.id,
        "PostToolUse", "Edit", "npm test", "r2 (갱신됨)", "high",
    )
    assert group.promoted is False  # 여전히 1명


def test_claude_md_groups_by_similarity_not_exact_text(db):
    project = _make_project(db)
    member1, sess1 = _make_member_session(db, project, "지민")
    member2, sess2 = _make_member_session(db, project, "태호")

    vector = [1.0, 0.0, 0.0]
    similar_vector = [0.99, 0.01, 0.0]

    match_claude_md_candidate(
        db, project.id, member1.id, sess1.id,
        "스페이스로 들여쓰기 통일", vector, "r1", "high",
    )
    group = match_claude_md_candidate(
        db, project.id, member2.id, sess2.id,
        "탭 대신 스페이스 써주세요", similar_vector, "r2", "medium",
    )
    assert group.promoted is True
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd web-server && python -m pytest tests/test_matching.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'web_server.matching'`

- [ ] **Step 3: 구현**

```python
# web-server/matching.py
import json
import numpy as np
from sqlmodel import Session as DBSession, select

from .models import RecommendationGroup, GroupMembership

PROMOTION_THRESHOLD = 2  # DESIGN.md D4: 실제 팀 규모(2인팀)에 맞춤
SIMILARITY_THRESHOLD = 0.85


def normalize_command(command: str) -> str:
    return " ".join(command.strip().lower().split())


def cosine_similarity(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a), np.array(b)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def match_hook_candidate(
    db: DBSession,
    project_id: str,
    member_id: str,
    session_id: str,
    event: str,
    matcher: str,
    command: str,
    reason: str,
    confidence: str,
) -> RecommendationGroup:
    normalized = normalize_command(command)
    existing = db.exec(
        select(RecommendationGroup).where(
            RecommendationGroup.project_id == project_id,
            RecommendationGroup.type == "hook",
            RecommendationGroup.event == event,
            RecommendationGroup.matcher == matcher,
            RecommendationGroup.representative_text == normalized,
        )
    ).first()
    group = _join_or_create_group(
        db, existing, project_id, "hook", normalized, member_id, session_id,
        command, reason, confidence,
    )
    if existing is None:
        group.event = event
        group.matcher = matcher
        db.add(group)
        db.commit()
        db.refresh(group)
    return group


def match_claude_md_candidate(
    db: DBSession,
    project_id: str,
    member_id: str,
    session_id: str,
    suggested_text: str,
    vector: list[float],
    reason: str,
    confidence: str,
) -> RecommendationGroup:
    candidates = db.exec(
        select(RecommendationGroup).where(
            RecommendationGroup.project_id == project_id,
            RecommendationGroup.type == "claude_md",
        )
    ).all()

    best_match: RecommendationGroup | None = None
    best_score = 0.0
    for group in candidates:
        if group.representative_vector is None:
            continue
        group_vector = json.loads(group.representative_vector)
        score = cosine_similarity(vector, group_vector)
        if score > best_score:
            best_score = score
            best_match = group

    existing = best_match if best_score >= SIMILARITY_THRESHOLD else None
    group = _join_or_create_group(
        db, existing, project_id, "claude_md", suggested_text, member_id,
        session_id, suggested_text, reason, confidence,
    )
    if existing is None:
        group.representative_vector = json.dumps(vector)
        db.add(group)
        db.commit()
        db.refresh(group)
    return group


def _join_or_create_group(
    db: DBSession,
    existing: RecommendationGroup | None,
    project_id: str,
    type_: str,
    representative_text: str,
    member_id: str,
    session_id: str,
    original_text: str,
    reason: str,
    confidence: str,
) -> RecommendationGroup:
    if existing is None:
        group = RecommendationGroup(
            project_id=project_id, type=type_, representative_text=representative_text
        )
        db.add(group)
        db.commit()
        db.refresh(group)
    else:
        group = existing

    prior_membership = db.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group.id,
            GroupMembership.member_id == member_id,
        )
    ).first()
    if prior_membership is None:
        db.add(
            GroupMembership(
                group_id=group.id,
                member_id=member_id,
                session_id=session_id,
                original_text=original_text,
                reason=reason,
                confidence=confidence,
            )
        )
    else:
        prior_membership.session_id = session_id
        prior_membership.original_text = original_text
        prior_membership.reason = reason
        prior_membership.confidence = confidence
        db.add(prior_membership)
    db.commit()

    member_count = len(
        db.exec(
            select(GroupMembership).where(GroupMembership.group_id == group.id)
        ).all()
    )
    group.promoted = member_count >= PROMOTION_THRESHOLD
    db.add(group)
    db.commit()
    db.refresh(group)
    return group
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd web-server && python -m pytest tests/test_matching.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: 커밋**

```bash
git add web-server/matching.py web-server/tests/test_matching.py
git commit -m "feat(web-server): add incremental hook/claude_md matching"
```

---

### Task 6: 세션 업로드 오케스트레이션

**Files:**
- Create: `web-server/routers/sessions.py`
- Modify: `web-server/main.py` (라우터 등록 추가)
- Create: `web-server/tests/test_upload_session.py`

**Interfaces:**
- Consumes: `extract_pattern_summary` (Task 3), `ai_client.analyze`/`embed` (Task 4), `match_hook_candidate`/`match_claude_md_candidate` (Task 5), `Session`/`PersonalRecommendation` (Task 1)
- Produces: `POST /projects/{project_id}/members/{member_id}/sessions` — 프론트(Task 10)가 이 엔드포인트를 호출

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# web-server/tests/test_upload_session.py
import io
import json
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session as DBSession

from web_server.main import app
from web_server.deps import get_db
from web_server import ai_client


@pytest.fixture()
def client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    def override_get_db():
        with DBSession(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async def fake_analyze(pattern_summary, client=None):
        return {
            "candidates": [
                {
                    "type": "hook",
                    "event": "PostToolUse",
                    "matcher": "Edit",
                    "command": "npm test",
                    "reason": "테스트를 항상 직접 실행하셨어요.",
                    "confidence": "high",
                }
            ]
        }

    async def fake_embed(text, client=None):
        return [0.1, 0.2, 0.3]

    monkeypatch.setattr(ai_client, "analyze", fake_analyze)
    monkeypatch.setattr(ai_client, "embed", fake_embed)

    yield TestClient(app)
    app.dependency_overrides.clear()


def _jsonl_with_repeated_bash(command: str, times: int) -> bytes:
    lines = [
        json.dumps({"type": "tool_use", "name": "Bash", "input": {"command": command}})
        for _ in range(times)
    ]
    return "\n".join(lines).encode("utf-8")


def _create_project_and_member(client):
    create_resp = client.post("/projects", json={"name": "test"})
    share_code = create_resp.json()["share_code"]
    project_id = create_resp.json()["project_id"]
    join_resp = client.post(f"/projects/{share_code}/join", json={"display_name": "지민"})
    member_id = join_resp.json()["member_id"]
    return project_id, member_id


def test_upload_with_patterns_returns_personal_recommendation(client):
    project_id, member_id = _create_project_and_member(client)
    file_content = _jsonl_with_repeated_bash("npm test", 5)

    resp = client.post(
        f"/projects/{project_id}/members/{member_id}/sessions",
        files={"file": ("session.jsonl", io.BytesIO(file_content), "application/jsonl")},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "processed"
    assert body["personal_recommendations"][0]["payload"]["command"] == "npm test"


def test_upload_with_no_patterns_skips_ai_call(client):
    project_id, member_id = _create_project_and_member(client)
    file_content = _jsonl_with_repeated_bash("ls", 1)  # 임계값(3회) 미달

    resp = client.post(
        f"/projects/{project_id}/members/{member_id}/sessions",
        files={"file": ("session.jsonl", io.BytesIO(file_content), "application/jsonl")},
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "no_patterns"
    assert resp.json()["personal_recommendations"] == []


def test_reupload_replaces_prior_session_and_does_not_double_count(client):
    project_id, member_id = _create_project_and_member(client)
    file_content = _jsonl_with_repeated_bash("npm test", 5)

    first = client.post(
        f"/projects/{project_id}/members/{member_id}/sessions",
        files={"file": ("s1.jsonl", io.BytesIO(file_content), "application/jsonl")},
    )
    second = client.post(
        f"/projects/{project_id}/members/{member_id}/sessions",
        files={"file": ("s2.jsonl", io.BytesIO(file_content), "application/jsonl")},
    )

    assert first.json()["session_id"] != second.json()["session_id"]
    assert second.json()["updated_team_groups"][0]["affected_members"] == 1
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd web-server && python -m pytest tests/test_upload_session.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'web_server.routers.sessions'`

- [ ] **Step 3: 구현**

```python
# web-server/routers/sessions.py
import json
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlmodel import Session as DBSession, select
from pydantic import BaseModel

from ..deps import get_db
from ..models import (
    Session as SessionModel,
    PersonalRecommendation,
    RecommendationGroup,
    GroupMembership,
)
from ..preprocessing import extract_pattern_summary
from .. import ai_client
from ..matching import match_hook_candidate, match_claude_md_candidate

router = APIRouter()

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10MB


class RecommendationOut(BaseModel):
    type: str
    payload: dict


class TeamGroupOut(BaseModel):
    id: str
    type: str
    representative_text: str
    affected_members: int
    promoted: bool


class UploadSessionResponse(BaseModel):
    session_id: str
    status: str
    personal_recommendations: list[RecommendationOut]
    updated_team_groups: list[TeamGroupOut]


@router.post(
    "/projects/{project_id}/members/{member_id}/sessions",
    response_model=UploadSessionResponse,
)
async def upload_session(
    project_id: str,
    member_id: str,
    file: UploadFile = File(...),
    db: DBSession = Depends(get_db),
) -> UploadSessionResponse:
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="파일이 너무 큽니다 (10MB 초과)")

    jsonl_text = raw.decode("utf-8", errors="ignore")

    # D7: 같은 (project, member)의 이전 세션은 최신 업로드로 교체
    old_session = db.exec(
        select(SessionModel).where(
            SessionModel.project_id == project_id, SessionModel.member_id == member_id
        )
    ).first()
    if old_session is not None:
        old_recs = db.exec(
            select(PersonalRecommendation).where(
                PersonalRecommendation.session_id == old_session.id
            )
        ).all()
        for rec in old_recs:
            db.delete(rec)
        db.delete(old_session)
        db.commit()

    pattern_summary = extract_pattern_summary(jsonl_text)

    if pattern_summary is None:
        session = SessionModel(
            project_id=project_id, member_id=member_id, status="no_patterns"
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return UploadSessionResponse(
            session_id=session.id,
            status="no_patterns",
            personal_recommendations=[],
            updated_team_groups=[],
        )

    session = SessionModel(project_id=project_id, member_id=member_id, status="processed")
    db.add(session)
    db.commit()
    db.refresh(session)

    analyze_result = await ai_client.analyze(pattern_summary)

    personal_out: list[RecommendationOut] = []
    updated_groups: list[RecommendationGroup] = []

    for candidate in analyze_result["candidates"]:
        db.add(
            PersonalRecommendation(
                session_id=session.id,
                member_id=member_id,
                type=candidate["type"],
                payload=json.dumps(candidate, ensure_ascii=False),
            )
        )
        db.commit()
        personal_out.append(RecommendationOut(type=candidate["type"], payload=candidate))

        if candidate["type"] == "hook":
            group = match_hook_candidate(
                db, project_id, member_id, session.id,
                candidate["event"], candidate["matcher"], candidate["command"],
                candidate["reason"], candidate["confidence"],
            )
            updated_groups.append(group)
        elif candidate["type"] == "claude_md":
            vector = await ai_client.embed(candidate["suggested_text"])
            group = match_claude_md_candidate(
                db, project_id, member_id, session.id,
                candidate["suggested_text"], vector,
                candidate["reason"], candidate["confidence"],
            )
            updated_groups.append(group)

    team_groups_out = [
        TeamGroupOut(
            id=g.id,
            type=g.type,
            representative_text=g.representative_text,
            affected_members=_count_members(db, g.id),
            promoted=g.promoted,
        )
        for g in updated_groups
    ]

    return UploadSessionResponse(
        session_id=session.id,
        status="processed",
        personal_recommendations=personal_out,
        updated_team_groups=team_groups_out,
    )


def _count_members(db: DBSession, group_id: str) -> int:
    return len(
        db.exec(
            select(GroupMembership).where(GroupMembership.group_id == group_id)
        ).all()
    )
```

`web-server/main.py`에 라우터 등록 추가:

```python
# web-server/main.py (수정)
from fastapi import FastAPI
from .db import init_db
from .routers import projects, sessions

app = FastAPI()
app.include_router(projects.router)
app.include_router(sessions.router)


@app.on_event("startup")
def on_startup():
    init_db()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd web-server && python -m pytest tests/test_upload_session.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋**

```bash
git add web-server/routers/sessions.py web-server/main.py web-server/tests/test_upload_session.py
git commit -m "feat(web-server): wire session upload orchestration"
```

---

### Task 7: 조회 엔드포인트 (팀 추천, 개인 추천, CLAUDE.md, hooks)

**Files:**
- Create: `web-server/routers/recommendations.py`
- Modify: `web-server/main.py` (라우터 등록 추가)
- Create: `web-server/tests/test_recommendations.py`

**Interfaces:**
- Consumes: `RecommendationGroup`, `GroupMembership`, `PersonalRecommendation` (Task 1)
- Produces: `GET /projects/{project_id}/recommendations`, `GET /members/{member_id}/recommendations`, `GET /projects/{project_id}/claude-md`, `GET /projects/{project_id}/hooks` — 프론트(Task 11)가 이 엔드포인트들을 호출

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# web-server/tests/test_recommendations.py
import io
import json
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session as DBSession

from web_server.main import app
from web_server.deps import get_db
from web_server import ai_client


@pytest.fixture()
def client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    def override_get_db():
        with DBSession(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async def fake_analyze(pattern_summary, client=None):
        return {
            "candidates": [
                {
                    "type": "hook",
                    "event": "PostToolUse",
                    "matcher": "Edit",
                    "command": "npm test",
                    "reason": "테스트를 항상 직접 실행하셨어요.",
                    "confidence": "high",
                },
                {
                    "type": "claude_md",
                    "suggested_text": "스페이스로 들여쓰기 통일",
                    "reason": "탭 대신 스페이스를 여러 번 알려주셨어요.",
                    "confidence": "medium",
                },
            ]
        }

    async def fake_embed(text, client=None):
        return [1.0, 0.0, 0.0]

    monkeypatch.setattr(ai_client, "analyze", fake_analyze)
    monkeypatch.setattr(ai_client, "embed", fake_embed)

    yield TestClient(app)
    app.dependency_overrides.clear()


def _upload(client, project_id, member_id, filename="s.jsonl"):
    content = "\n".join(
        json.dumps({"type": "tool_use", "name": "Bash", "input": {"command": "npm test"}})
        for _ in range(5)
    ).encode("utf-8")
    return client.post(
        f"/projects/{project_id}/members/{member_id}/sessions",
        files={"file": (filename, io.BytesIO(content), "application/jsonl")},
    )


def _create_project_and_two_members(client):
    create_resp = client.post("/projects", json={"name": "test"})
    share_code = create_resp.json()["share_code"]
    project_id = create_resp.json()["project_id"]
    m1 = client.post(f"/projects/{share_code}/join", json={"display_name": "지민"}).json()["member_id"]
    m2 = client.post(f"/projects/{share_code}/join", json={"display_name": "태호"}).json()["member_id"]
    return project_id, m1, m2


def test_team_recommendations_empty_before_threshold(client):
    project_id, m1, m2 = _create_project_and_two_members(client)
    _upload(client, project_id, m1)

    resp = client.get(f"/projects/{project_id}/recommendations")
    assert resp.status_code == 200
    assert resp.json() == []


def test_team_recommendations_appear_after_threshold(client):
    project_id, m1, m2 = _create_project_and_two_members(client)
    _upload(client, project_id, m1, "s1.jsonl")
    _upload(client, project_id, m2, "s2.jsonl")

    resp = client.get(f"/projects/{project_id}/recommendations")
    assert resp.status_code == 200
    body = resp.json()
    hook_rec = next(r for r in body if r["type"] == "hook")
    assert hook_rec["affected_members"] == 2
    assert len(hook_rec["evidence"]) == 2


def test_personal_recommendations_scoped_to_member(client):
    project_id, m1, m2 = _create_project_and_two_members(client)
    _upload(client, project_id, m1)

    resp = client.get(f"/members/{m1}/recommendations")
    assert resp.status_code == 200
    assert len(resp.json()) == 2  # hook + claude_md

    resp2 = client.get(f"/members/{m2}/recommendations")
    assert resp2.json() == []


def test_claude_md_download_reflects_promoted_groups(client):
    project_id, m1, m2 = _create_project_and_two_members(client)
    _upload(client, project_id, m1, "s1.jsonl")
    _upload(client, project_id, m2, "s2.jsonl")

    resp = client.get(f"/projects/{project_id}/claude-md")
    assert resp.status_code == 200
    assert "스페이스로 들여쓰기 통일" in resp.text


def test_hooks_download_matches_claude_code_settings_shape(client):
    project_id, m1, m2 = _create_project_and_two_members(client)
    _upload(client, project_id, m1, "s1.jsonl")
    _upload(client, project_id, m2, "s2.jsonl")

    resp = client.get(f"/projects/{project_id}/hooks")
    assert resp.status_code == 200
    body = resp.json()
    assert body["hooks"]["PostToolUse"][0]["matcher"] == "Edit"
    assert body["hooks"]["PostToolUse"][0]["hooks"][0]["command"] == "npm test"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd web-server && python -m pytest tests/test_recommendations.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'web_server.routers.recommendations'`

- [ ] **Step 3: 구현**

```python
# web-server/routers/recommendations.py
import json
from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlmodel import Session as DBSession, select
from pydantic import BaseModel

from ..deps import get_db
from ..models import RecommendationGroup, GroupMembership, PersonalRecommendation

router = APIRouter()


class EvidenceOut(BaseModel):
    member_id: str
    original_text: str


class TeamRecommendationOut(BaseModel):
    id: str
    type: str
    representative_text: str
    affected_members: int
    evidence: list[EvidenceOut]


@router.get(
    "/projects/{project_id}/recommendations",
    response_model=list[TeamRecommendationOut],
)
def get_team_recommendations(project_id: str, db: DBSession = Depends(get_db)):
    groups = db.exec(
        select(RecommendationGroup).where(
            RecommendationGroup.project_id == project_id,
            RecommendationGroup.promoted == True,  # noqa: E712
        )
    ).all()

    out = []
    for group in groups:
        memberships = db.exec(
            select(GroupMembership).where(GroupMembership.group_id == group.id)
        ).all()
        out.append(
            TeamRecommendationOut(
                id=group.id,
                type=group.type,
                representative_text=group.representative_text,
                affected_members=len(memberships),
                evidence=[
                    EvidenceOut(member_id=m.member_id, original_text=m.original_text)
                    for m in memberships
                ],
            )
        )
    return out


class PersonalRecommendationOut(BaseModel):
    type: str
    payload: dict


@router.get(
    "/members/{member_id}/recommendations",
    response_model=list[PersonalRecommendationOut],
)
def get_personal_recommendations(member_id: str, db: DBSession = Depends(get_db)):
    recs = db.exec(
        select(PersonalRecommendation).where(PersonalRecommendation.member_id == member_id)
    ).all()
    return [
        PersonalRecommendationOut(type=r.type, payload=json.loads(r.payload)) for r in recs
    ]


@router.get("/projects/{project_id}/claude-md", response_class=PlainTextResponse)
def get_merged_claude_md(project_id: str, db: DBSession = Depends(get_db)) -> str:
    groups = db.exec(
        select(RecommendationGroup).where(
            RecommendationGroup.project_id == project_id,
            RecommendationGroup.type == "claude_md",
            RecommendationGroup.promoted == True,  # noqa: E712
        )
    ).all()
    if not groups:
        return "# CLAUDE.md\n\n(아직 팀 공통 규칙이 없습니다. 팀원이 더 업로드하면 여기 채워집니다.)\n"
    lines = ["# CLAUDE.md", ""]
    for group in groups:
        lines.append(f"- {group.representative_text}")
    return "\n".join(lines) + "\n"


@router.get("/projects/{project_id}/hooks")
def get_merged_hooks(project_id: str, db: DBSession = Depends(get_db)) -> dict:
    groups = db.exec(
        select(RecommendationGroup).where(
            RecommendationGroup.project_id == project_id,
            RecommendationGroup.type == "hook",
            RecommendationGroup.promoted == True,  # noqa: E712
        )
    ).all()
    hooks: dict[str, list[dict]] = {}
    for group in groups:
        event_hooks = hooks.setdefault(group.event, [])
        matcher_entry = next(
            (h for h in event_hooks if h["matcher"] == group.matcher), None
        )
        if matcher_entry is None:
            matcher_entry = {"matcher": group.matcher, "hooks": []}
            event_hooks.append(matcher_entry)
        matcher_entry["hooks"].append(
            {"type": "command", "command": group.representative_text}
        )
    return {"hooks": hooks}
```

`web-server/main.py`에 라우터 등록 추가:

```python
# web-server/main.py (수정)
from fastapi import FastAPI
from .db import init_db
from .routers import projects, sessions, recommendations

app = FastAPI()
app.include_router(projects.router)
app.include_router(sessions.router)
app.include_router(recommendations.router)


@app.on_event("startup")
def on_startup():
    init_db()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd web-server && python -m pytest tests/test_recommendations.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: 전체 백엔드 테스트 스위트 실행**

Run: `cd web-server && python -m pytest -v`
Expected: 모든 테스트 PASS (24 passed)

- [ ] **Step 6: 커밋**

```bash
git add web-server/routers/recommendations.py web-server/main.py web-server/tests/test_recommendations.py
git commit -m "feat(web-server): add recommendation/claude-md/hooks read endpoints"
```

---

### Task 8: Next.js 스캐폴딩 + BFF 프록시 설정

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/next.config.js`
- Create: `frontend/tsconfig.json`
- Create: `frontend/app/layout.tsx`

**Interfaces:**
- Consumes: 없음
- Produces: `/api/*` → 웹서버(`:8000`) 프록시 — 이후 모든 프론트 태스크가 `fetch("/api/...")`로 이 프록시를 통해 웹서버를 호출

- [ ] **Step 1: package.json 작성**

```json
{
  "name": "frontend",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "test": "vitest run"
  },
  "dependencies": {
    "next": "15.0.0",
    "react": "18.3.0",
    "react-dom": "18.3.0",
    "react-dropzone": "14.3.0"
  },
  "devDependencies": {
    "typescript": "5.6.0",
    "@types/react": "18.3.0",
    "@types/node": "22.0.0",
    "vitest": "2.1.0",
    "@testing-library/react": "16.0.0",
    "@testing-library/jest-dom": "6.5.0",
    "jsdom": "25.0.0"
  }
}
```

- [ ] **Step 2: next.config.js — BFF 프록시**

```javascript
// frontend/next.config.js
/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.WEB_SERVER_URL || "http://localhost:8000"}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
```

- [ ] **Step 3: tsconfig.json (경로 별칭 `@/` 설정 포함)**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["dom", "dom.iterable", "esnext"],
    "module": "esnext",
    "moduleResolution": "bundler",
    "jsx": "preserve",
    "strict": true,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "paths": { "@/*": ["./*"] }
  },
  "include": ["**/*.ts", "**/*.tsx"]
}
```

- [ ] **Step 4: 최소 레이아웃**

```tsx
// frontend/app/layout.tsx
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
```

- [ ] **Step 5: 설치 + 수동 검증**

```bash
cd frontend && npm install
npm run dev &
# 다른 터미널: 웹서버도 :8000에 띄운 상태에서
curl -X POST http://localhost:3000/api/projects \
  -H "Content-Type: application/json" -d '{"name":"test"}'
```

Expected: 웹서버(`:8000/projects`)에 직접 요청한 것과 동일한 JSON 응답 (`project_id`, `share_code`)이 `:3000/api/projects`를 통해서도 옴.

- [ ] **Step 6: 커밋**

```bash
git add frontend/package.json frontend/next.config.js frontend/tsconfig.json frontend/app/layout.tsx
git commit -m "chore(frontend): scaffold Next.js app with BFF proxy"
```

---

### Task 9: 프론트 — 프로젝트 생성/참여 화면

**Files:**
- Create: `frontend/lib/api.ts`
- Create: `frontend/lib/api.test.ts`
- Create: `frontend/app/join/page.tsx`
- Create: `frontend/app/join/page.test.tsx`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/vitest.setup.ts`

**Interfaces:**
- Consumes: `POST /projects`, `POST /projects/{share_code}/join` (Task 2, `/api/` 프록시 경유)
- Produces: `createProject`, `joinProject` — Task 10, 11이 `lib/api.ts`에 계속 함수를 추가함

- [ ] **Step 1: vitest 설정**

```typescript
// frontend/vitest.config.ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
  },
});
```

```typescript
// frontend/vitest.setup.ts
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 2: 실패하는 테스트 작성 (`lib/api.ts`)**

```typescript
// frontend/lib/api.test.ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { createProject, joinProject } from "./api";

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("createProject", () => {
  it("returns project_id and share_code on success", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ project_id: "p1", share_code: "AB12CD" }),
    }) as unknown as typeof fetch;

    const result = await createProject("26s-w2-c2-05");
    expect(result.share_code).toBe("AB12CD");
  });
});

describe("joinProject", () => {
  it("throws on failure response", async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false }) as unknown as typeof fetch;
    await expect(joinProject("ZZZZZZ", "지민")).rejects.toThrow();
  });
});
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `cd frontend && npx vitest run lib/api.test.ts`
Expected: FAIL with `Cannot find module './api'`

- [ ] **Step 4: 구현**

```typescript
// frontend/lib/api.ts
export async function createProject(name: string) {
  const res = await fetch("/api/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error("프로젝트 생성에 실패했습니다");
  return res.json() as Promise<{ project_id: string; share_code: string }>;
}

export async function joinProject(shareCode: string, displayName: string) {
  const res = await fetch(`/api/projects/${shareCode}/join`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ display_name: displayName }),
  });
  if (!res.ok) throw new Error("참여에 실패했습니다 — 코드를 확인해주세요");
  return res.json() as Promise<{ member_id: string; project_id: string }>;
}
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `cd frontend && npx vitest run lib/api.test.ts`
Expected: PASS (2 passed)

- [ ] **Step 6: 참여 화면 실패하는 테스트 작성**

```tsx
// frontend/app/join/page.test.tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import JoinPage from "./page";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

describe("JoinPage", () => {
  it("shows error message when join fails", async () => {
    vi.spyOn(api, "joinProject").mockRejectedValue(
      new Error("참여에 실패했습니다 — 코드를 확인해주세요")
    );
    render(<JoinPage />);

    fireEvent.change(screen.getByPlaceholderText("팀 참여 코드"), {
      target: { value: "ZZZZZZ" },
    });
    fireEvent.change(screen.getByPlaceholderText("표시 이름"), {
      target: { value: "지민" },
    });
    fireEvent.click(screen.getByText("참여하기"));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("코드를 확인해주세요");
    });
  });
});
```

- [ ] **Step 7: 테스트 실패 확인**

Run: `cd frontend && npx vitest run app/join/page.test.tsx`
Expected: FAIL with `Cannot find module './page'`

- [ ] **Step 8: 구현**

```tsx
// frontend/app/join/page.tsx
"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { joinProject } from "@/lib/api";

export default function JoinPage() {
  const [shareCode, setShareCode] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const { member_id, project_id } = await joinProject(shareCode, displayName);
      localStorage.setItem("member_id", member_id);
      localStorage.setItem("project_id", project_id);
      router.push("/upload");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <input
        value={shareCode}
        onChange={(e) => setShareCode(e.target.value)}
        placeholder="팀 참여 코드"
      />
      <input
        value={displayName}
        onChange={(e) => setDisplayName(e.target.value)}
        placeholder="표시 이름"
      />
      <button type="submit">참여하기</button>
      {error && <p role="alert">{error}</p>}
    </form>
  );
}
```

- [ ] **Step 9: 테스트 통과 확인**

Run: `cd frontend && npx vitest run app/join/page.test.tsx`
Expected: PASS (1 passed)

- [ ] **Step 10: 커밋**

```bash
git add frontend/vitest.config.ts frontend/vitest.setup.ts frontend/lib/api.ts frontend/lib/api.test.ts frontend/app/join/page.tsx frontend/app/join/page.test.tsx
git commit -m "feat(frontend): add project join screen"
```

---

### Task 10: 프론트 — 세션 업로드 + 개인 추천 카드

**Files:**
- Modify: `frontend/lib/api.ts` (uploadSession 추가)
- Create: `frontend/app/upload/page.tsx`
- Create: `frontend/app/upload/page.test.tsx`

**Interfaces:**
- Consumes: `POST /projects/{project_id}/members/{member_id}/sessions` (Task 6, `/api/` 프록시 경유)
- Produces: `uploadSession` — Task 11에서 참고할 응답 형태(`personal_recommendations`, `updated_team_groups`)

- [ ] **Step 1: `lib/api.ts`에 함수 추가**

```typescript
// frontend/lib/api.ts (추가)
export async function uploadSession(projectId: string, memberId: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`/api/projects/${projectId}/members/${memberId}/sessions`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error("업로드에 실패했습니다");
  return res.json();
}
```

- [ ] **Step 2: 실패하는 테스트 작성**

```tsx
// frontend/app/upload/page.test.tsx
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import UploadPage from "./page";
import * as api from "@/lib/api";

describe("UploadPage", () => {
  it("renders recommendation cards after successful upload", async () => {
    localStorage.setItem("project_id", "p1");
    localStorage.setItem("member_id", "m1");
    vi.spyOn(api, "uploadSession").mockResolvedValue({
      status: "processed",
      personal_recommendations: [
        { type: "hook", payload: { reason: "테스트를 항상 직접 실행하셨어요." } },
      ],
      updated_team_groups: [],
    });

    render(<UploadPage />);
    const input = screen.getByTestId("dropzone").querySelector("input")!;
    const file = new File(["dummy"], "session.jsonl", { type: "application/jsonl" });

    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByTestId("recommendation-card")).toHaveTextContent(
        "테스트를 항상 직접 실행하셨어요."
      );
    });
  });

  it("shows an error message when upload fails", async () => {
    localStorage.setItem("project_id", "p1");
    localStorage.setItem("member_id", "m1");
    vi.spyOn(api, "uploadSession").mockRejectedValue(new Error("업로드에 실패했습니다"));

    render(<UploadPage />);
    const input = screen.getByTestId("dropzone").querySelector("input")!;
    const file = new File(["dummy"], "session.jsonl", { type: "application/jsonl" });

    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("업로드에 실패했습니다");
    });
  });
});
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `cd frontend && npx vitest run app/upload/page.test.tsx`
Expected: FAIL with `Cannot find module './page'`

- [ ] **Step 4: 구현**

```tsx
// frontend/app/upload/page.tsx
"use client";
import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { uploadSession } from "@/lib/api";

type Candidate = {
  type: "hook" | "claude_md";
  payload: Record<string, string>;
};

export default function UploadPage() {
  const [recommendations, setRecommendations] = useState<Candidate[]>([]);
  const [status, setStatus] = useState<"idle" | "uploading" | "done" | "error">("idle");

  const onDrop = useCallback(async (files: File[]) => {
    const file = files[0];
    if (!file) return;
    setStatus("uploading");
    try {
      const projectId = localStorage.getItem("project_id")!;
      const memberId = localStorage.getItem("member_id")!;
      const result = await uploadSession(projectId, memberId, file);
      if (result.status === "no_patterns") {
        setRecommendations([]);
        setStatus("done");
        return;
      }
      setRecommendations(result.personal_recommendations);
      setStatus("done");
    } catch {
      setStatus("error");
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/jsonl": [".jsonl"] },
    maxFiles: 1,
  });

  return (
    <div>
      <div {...getRootProps()} data-testid="dropzone">
        <input {...getInputProps()} />
        {isDragActive ? (
          <p>여기에 놓으세요</p>
        ) : (
          <p>세션 JSONL 파일을 드래그하거나 클릭해서 올려주세요</p>
        )}
      </div>
      {status === "uploading" && <p>분석 중...</p>}
      {status === "error" && (
        <p role="alert">업로드에 실패했습니다. 잠시 후 다시 시도해주세요.</p>
      )}
      {recommendations.map((rec, i) => (
        <div key={i} data-testid="recommendation-card">
          <strong>{rec.type === "hook" ? "자동화 제안" : "프로젝트 규칙 제안"}</strong>
          <p>{rec.payload.reason}</p>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `cd frontend && npx vitest run app/upload/page.test.tsx`
Expected: PASS (2 passed)

- [ ] **Step 6: 커밋**

```bash
git add frontend/lib/api.ts frontend/app/upload/page.tsx frontend/app/upload/page.test.tsx
git commit -m "feat(frontend): add session upload with personal recommendation cards"
```

---

### Task 11: 프론트 — 팀 추천 화면

**Files:**
- Modify: `frontend/lib/api.ts` (getTeamRecommendations 추가)
- Create: `frontend/app/team/page.tsx`
- Create: `frontend/app/team/page.test.tsx`

**Interfaces:**
- Consumes: `GET /projects/{project_id}/recommendations` (Task 7, `/api/` 프록시 경유)
- Produces: 없음 (최종 화면)

- [ ] **Step 1: `lib/api.ts`에 함수 추가**

```typescript
// frontend/lib/api.ts (추가)
export async function getTeamRecommendations(projectId: string) {
  const res = await fetch(`/api/projects/${projectId}/recommendations`);
  if (!res.ok) throw new Error("팀 추천을 불러오지 못했습니다");
  return res.json();
}
```

- [ ] **Step 2: 실패하는 테스트 작성**

```tsx
// frontend/app/team/page.test.tsx
import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import TeamPage from "./page";
import * as api from "@/lib/api";

describe("TeamPage", () => {
  it("shows empty state when no team recommendations exist", async () => {
    localStorage.setItem("project_id", "p1");
    vi.spyOn(api, "getTeamRecommendations").mockResolvedValue([]);
    render(<TeamPage />);
    await waitFor(() => {
      expect(screen.getByText(/아직 팀 추천이 없습니다/)).toBeInTheDocument();
    });
  });

  it("shows evidence for promoted groups", async () => {
    localStorage.setItem("project_id", "p1");
    vi.spyOn(api, "getTeamRecommendations").mockResolvedValue([
      {
        id: "g1",
        type: "claude_md",
        representative_text: "스페이스로 들여쓰기 통일",
        affected_members: 2,
        evidence: [
          { member_id: "m1", original_text: "스페이스로 들여쓰기 통일" },
          { member_id: "m2", original_text: "탭 대신 스페이스 써주세요" },
        ],
      },
    ]);
    render(<TeamPage />);
    await waitFor(() => {
      expect(screen.getByTestId("team-rec-card")).toHaveTextContent("2명이 반영했어요");
    });
  });
});
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `cd frontend && npx vitest run app/team/page.test.tsx`
Expected: FAIL with `Cannot find module './page'`

- [ ] **Step 4: 구현**

```tsx
// frontend/app/team/page.tsx
"use client";
import { useEffect, useState } from "react";
import { getTeamRecommendations } from "@/lib/api";

type TeamRec = {
  id: string;
  type: string;
  representative_text: string;
  affected_members: number;
  evidence: { member_id: string; original_text: string }[];
};

export default function TeamPage() {
  const [recs, setRecs] = useState<TeamRec[]>([]);

  useEffect(() => {
    const projectId = localStorage.getItem("project_id");
    if (!projectId) return;
    getTeamRecommendations(projectId)
      .then(setRecs)
      .catch(() => setRecs([]));
  }, []);

  if (recs.length === 0) {
    return <p>아직 팀 추천이 없습니다. 팀원이 2명 이상 비슷한 패턴을 올리면 여기 나타나요.</p>;
  }

  return (
    <div>
      {recs.map((rec) => (
        <div key={rec.id} data-testid="team-rec-card">
          <strong>{rec.representative_text}</strong>
          <span>{rec.affected_members}명이 반영했어요</span>
          <ul>
            {rec.evidence.map((e, i) => (
              <li key={i}>{e.original_text}</li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `cd frontend && npx vitest run app/team/page.test.tsx`
Expected: PASS (2 passed)

- [ ] **Step 6: 전체 프론트 테스트 스위트 실행**

Run: `cd frontend && npm test`
Expected: 모든 테스트 PASS (7 passed)

- [ ] **Step 7: 커밋**

```bash
git add frontend/lib/api.ts frontend/app/team/page.tsx frontend/app/team/page.test.tsx
git commit -m "feat(frontend): add team recommendations screen with evidence"
```

---

## 이 플랜 이후 (별도 플랜으로 분리)

DESIGN.md Next Steps #4~#6 (`SkillRecommendation` 타입 추가, 프로젝트 생성 시 기본 템플릿 자동 생성, 개인 모드 즉시 적용 UX)은 이 플랜에 포함하지 않는다 — hook/claude_md 두 타입이 안정화된 뒤 별도 플랜으로 작성하는 게 DESIGN.md에 이미 기록된 순서다.
