# Skill 추천 타입 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** hook/claude_md에 이은 3번째 추천 타입 `skill`을 추가한다 — 세션 로그에서
반복되는 다단계 bash 시퀀스를 감지하고, Gemini가 이를 skill 후보로 제안하며,
사용자가 "적용하기"를 누르면 실제 `Skill` 엔터티가 생성되어 편집/저장/PUSH까지
가능해진다.

**Architecture:** AI서버(스키마+프롬프트) → 웹서버(전처리 시퀀스 추출 → 매칭 →
새 `Skill` 테이블/라우터 → 세션 업로드/적용 로직 연결 → PUSH 확장) → 프론트(3번째
탭 + 추천 카드 + 적용 플로우) 순서로 의존성이 흐른다.

**Tech Stack:** FastAPI + SQLModel + pytest/pytest-asyncio/httpx(ai_server, web-server),
Next.js/TypeScript(frontend). 스펙 문서: `docs/superpowers/specs/2026-07-14-skill-recommendation-design.md`.

## Global Constraints

- 백엔드는 TDD(Red→Green), 프론트는 UI 구현 후 브라우저 수동 확인 (`CLAUDE.md` 4절).
- skill 최소 반복 임계값은 2회 (hook/claude_md의 3회와 다름).
- 시퀀스는 bash 커맨드만 대상(v1), 갭 허용 부분수열 매칭, 최대 4단계까지 점진 확장.
- 팀 병합은 `skill_description` 임베딩 코사인 유사도 ≥0.85 (claude_md와 동일 임계값).
- **⚠️ 충돌 위험**: `feature/ai-server` 브랜치를 웹서버 팀원과 공유 중이다(별도
  `feature/web-server` 브랜치 없음). `web-server/models.py`,
  `web-server/routers/sessions.py`, `web-server/routers/projects.py`,
  `frontend/app/project/[id]/page.tsx`는 팀원이 최근 활발히 수정한 고위험 파일이다.
  이 파일들을 다루는 태스크(Task 4, 7, 8, 10) 시작 직전에 반드시
  `git fetch origin && git log --oneline feature/ai-server..origin/feature/ai-server`로
  새 커밋 여부를 확인하고, 있으면 `git pull --rebase`로 먼저 동기화한 뒤 진행한다.
  각 태스크는 완료 즉시 커밋한다(작은 단위로 자주 커밋 = 충돌 시 리베이스 범위 최소화).
- AI서버 태스크(1~2)는 팀원과 겹치는 파일이 전혀 없으므로 충돌 걱정 없이 먼저 진행한다.

---

## Phase 1 — AI 서버 (충돌 위험 없음, 독립적으로 먼저 진행)

### Task 1: AI서버 스키마에 SkillRecommendation 추가

**Files:**
- Modify: `ai_server/schemas.py`
- Test: `ai_server/tests/test_schemas.py`

**Interfaces:**
- Produces: `SkillRecommendation`(type/skill_name/skill_description/suggested_steps/reason/confidence),
  `GeminiSkillCandidate`(type 없는 버전), `Candidate` Union에 포함,
  `GeminiAnalyzeSchema.skill_candidates: list[GeminiSkillCandidate]`.

- [ ] **Step 1: 실패하는 테스트 작성**

`ai_server/tests/test_schemas.py` 끝에 추가:

```python
def test_skill_recommendation_round_trips():
    from ai_server.schemas import SkillRecommendation

    rec = SkillRecommendation(
        type="skill",
        skill_name="run-migrations",
        skill_description="마이그레이션 후 시드와 재시작을 순서대로 진행한다",
        suggested_steps="1. migrate 실행\n2. seed 실행\n3. 서버 재시작",
        reason="매번 이 순서로 실행하셨어요.",
        confidence="high",
    )
    dumped = rec.model_dump_json()
    restored = SkillRecommendation.model_validate_json(dumped)
    assert restored.skill_name == "run-migrations"
    assert restored.type == "skill"


def test_analyze_response_holds_skill_candidate():
    from ai_server.schemas import AnalyzeResponse, SkillRecommendation

    resp = AnalyzeResponse(
        candidates=[
            SkillRecommendation(
                type="skill",
                skill_name="run-migrations",
                skill_description="설명",
                suggested_steps="단계",
                reason="이유",
                confidence="medium",
            )
        ]
    )
    assert resp.candidates[0].type == "skill"


def test_gemini_analyze_schema_accepts_skill_candidates():
    from ai_server.schemas import GeminiAnalyzeSchema, GeminiSkillCandidate

    schema = GeminiAnalyzeSchema(
        hook_candidates=[],
        claude_md_candidates=[],
        skill_candidates=[
            GeminiSkillCandidate(
                skill_name="run-migrations",
                skill_description="설명",
                suggested_steps="단계",
                reason="이유",
                confidence="high",
            )
        ],
    )
    assert schema.skill_candidates[0].skill_name == "run-migrations"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `ai_server/.venv/bin/python -m pytest ai_server/tests/test_schemas.py -v`
Expected: FAIL — `ImportError: cannot import name 'SkillRecommendation'` 등.

- [ ] **Step 3: 최소 구현**

`ai_server/schemas.py`에서 `Candidate = Union[HookCandidate, ClaudeMdCandidate]` 줄을 찾아
그 위에 새 클래스를 추가하고, `Union`과 `GeminiAnalyzeSchema`를 확장한다:

```python
class SkillRecommendation(BaseModel):
    type: Literal["skill"]
    skill_name: str
    skill_description: str
    suggested_steps: str
    reason: str
    confidence: Literal["low", "medium", "high"]


class GeminiSkillCandidate(BaseModel):
    """GeminiHookCandidate/GeminiClaudeMdCandidate와 동일한 이유로 type 없음
    (skill_candidates 리스트 소속 자체가 타입을 나타냄)."""

    skill_name: str
    skill_description: str
    suggested_steps: str
    reason: str
    confidence: Literal["low", "medium", "high"]


Candidate = Union[HookCandidate, ClaudeMdCandidate, SkillRecommendation]
```

`GeminiAnalyzeSchema` 클래스 안의 `claude_md_candidates: list[GeminiClaudeMdCandidate]` 줄
바로 아래에 추가 (기본값을 주면 Gemini `response_schema`가 거부하므로 필수 필드로 유지):

```python
    skill_candidates: list[GeminiSkillCandidate]
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `ai_server/.venv/bin/python -m pytest ai_server/tests/test_schemas.py -v`
Expected: PASS (9 passed)

- [ ] **Step 5: 기존 GeminiAnalyzeSchema 생성 코드 수정 (필수 필드 추가로 인한 기존 테스트 깨짐 수정)**

`ai_server/tests/test_gemini_client.py`에서 `GeminiAnalyzeSchema(...)`를 생성하는
두 곳에 `skill_candidates=[]`를 추가해야 한다 (안 하면 이 태스크 완료 후
`test_gemini_client.py`가 깨짐 — Step 6에서 확인).

`EMPTY_GEMINI_RESPONSE` 줄을:
```python
EMPTY_GEMINI_RESPONSE = GeminiAnalyzeSchema(hook_candidates=[], claude_md_candidates=[])
```
다음으로 변경:
```python
EMPTY_GEMINI_RESPONSE = GeminiAnalyzeSchema(
    hook_candidates=[], claude_md_candidates=[], skill_candidates=[]
)
```

`test_injects_type_field_when_converting_gemini_response` 안의
`gemini_response = GeminiAnalyzeSchema(...)` 블록 끝(`claude_md_candidates=[...]` 리스트
닫힌 후, 클래스 닫는 괄호 전)에 `skill_candidates=[]` 추가.

- [ ] **Step 6: 전체 ai_server 테스트로 회귀 확인**

Run: `ai_server/.venv/bin/python -m pytest ai_server -v`
Expected: 전체 PASS (기존 37개 + 신규 3개 = 40개)

- [ ] **Step 7: 커밋**

```bash
git add ai_server/schemas.py ai_server/tests/test_schemas.py ai_server/tests/test_gemini_client.py
git commit -m "feat(ai_server): add SkillRecommendation schema for skill candidate type"
```

---

### Task 2: AI서버 프롬프트 + 응답 조립에 skill 반영

**Files:**
- Modify: `ai_server/gemini_client.py`
- Test: `ai_server/tests/test_gemini_client.py`

**Interfaces:**
- Consumes: Task 1의 `SkillRecommendation`, `GeminiSkillCandidate`, `GeminiAnalyzeSchema.skill_candidates`.
- Produces: `_to_analyze_response`가 skill 후보까지 조립한 `AnalyzeResponse` 반환.

- [ ] **Step 1: 실패하는 테스트 작성**

`ai_server/tests/test_gemini_client.py` 상단 import에 `GeminiSkillCandidate`,
`SkillRecommendation` 추가:

```python
from ai_server.schemas import (
    AnalyzeResponse,
    ClaudeMdCandidate,
    GeminiAnalyzeSchema,
    GeminiClaudeMdCandidate,
    GeminiHookCandidate,
    GeminiSkillCandidate,
    HookCandidate,
    SkillRecommendation,
)
```

파일 끝에 테스트 추가:

```python
@pytest.mark.asyncio
async def test_injects_type_field_for_skill_candidates():
    gemini_response = GeminiAnalyzeSchema(
        hook_candidates=[],
        claude_md_candidates=[],
        skill_candidates=[
            GeminiSkillCandidate(
                skill_name="run-migrations",
                skill_description="마이그레이션 후 시드와 재시작을 순서대로 진행한다",
                suggested_steps="1. migrate\n2. seed\n3. restart",
                reason="매번 이 순서로 실행하셨어요.",
                confidence="high",
            )
        ],
    )
    client = FakeClient(FakeModels([gemini_response]))

    result = await call_gemini_analyze(client, "패턴 요약")

    assert result == AnalyzeResponse(
        candidates=[
            SkillRecommendation(
                type="skill",
                skill_name="run-migrations",
                skill_description="마이그레이션 후 시드와 재시작을 순서대로 진행한다",
                suggested_steps="1. migrate\n2. seed\n3. restart",
                reason="매번 이 순서로 실행하셨어요.",
                confidence="high",
            )
        ]
    )
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `ai_server/.venv/bin/python -m pytest ai_server/tests/test_gemini_client.py::test_injects_type_field_for_skill_candidates -v`
Expected: FAIL — 조립 결과에 skill 후보가 빠져서 `AnalyzeResponse(candidates=[])`와 비교 실패.

- [ ] **Step 3: 최소 구현**

`ai_server/gemini_client.py` 상단 import 줄:
```python
from .schemas import AnalyzeResponse, ClaudeMdCandidate, GeminiAnalyzeSchema, HookCandidate
```
을 다음으로 변경:
```python
from .schemas import (
    AnalyzeResponse,
    ClaudeMdCandidate,
    GeminiAnalyzeSchema,
    HookCandidate,
    SkillRecommendation,
)
```

`SYSTEM_INSTRUCTION`의 "판단 기준:" 목록에서 `- claude_md: ...` 줄 바로 다음 줄에
새 항목을 추가 (기존 문자열 안에 삽입):

```
- skill: 2단계 이상 이어지고, 중간에 판단/분기가 섞이는 반복 절차. "이 순서로
  이렇게 해야 한다"는 여러 문장으로 설명해야 하는 경우.
  예: "마이그레이션 실행 후 시드 갱신, 그다음 서버 재시작을 항상 이 순서로 한다"
  → skill_name은 kebab-case로 간결하게(예: "run-migrations"), skill_description은
  한 줄 요약, suggested_steps는 실행 순서를 번호 매긴 목록으로 markdown 작성.
  이 타입은 hook/claude_md보다 반복 기준이 낮아 2회 이상만 반복돼도 후보로
  삼아라(hook/claude_md는 3회 기준).
```

`_to_analyze_response` 함수를 다음으로 변경:

```python
def _to_analyze_response(parsed: GeminiAnalyzeSchema) -> AnalyzeResponse:
    """Gemini가 hook/claude_md/skill로 나눠 응답한 리스트에 type을 채워 넣어
    AnalyzeResponse(Union 기반)로 조립한다. GeminiAnalyzeSchema 문서에
    설명한 대로, 리스트 소속 자체가 이미 타입을 나타내므로 여기서 채우면
    된다."""
    candidates = (
        [HookCandidate(type="hook", **h.model_dump()) for h in parsed.hook_candidates]
        + [
            ClaudeMdCandidate(type="claude_md", **c.model_dump())
            for c in parsed.claude_md_candidates
        ]
        + [
            SkillRecommendation(type="skill", **s.model_dump())
            for s in parsed.skill_candidates
        ]
    )
    return AnalyzeResponse(candidates=candidates)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `ai_server/.venv/bin/python -m pytest ai_server/tests/test_gemini_client.py -v`
Expected: PASS (전체)

- [ ] **Step 5: 전체 ai_server 테스트 + 회귀 확인**

Run: `ai_server/.venv/bin/python -m pytest ai_server -v`
Expected: 전체 PASS (41개)

- [ ] **Step 6: 커밋 + 원격 반영**

```bash
git add ai_server/gemini_client.py ai_server/tests/test_gemini_client.py
git commit -m "feat(ai_server): classify and assemble skill candidates in analyze response"
git push origin feature/ai-server
```

(AI서버 파트는 팀원과 겹치는 파일이 없어 여기서 바로 push해도 안전하다 — Phase 2
진입 전에 원격에 반영해두면 이후 pull 시 diff가 깔끔해진다.)

---

## Phase 2 — 웹서버 백엔드

### Task 3: 전처리 — 다단계 시퀀스 추출

**Files:**
- Modify: `web-server/preprocessing.py`
- Test: `web-server/tests/test_preprocessing.py`

**Interfaces:**
- Produces: `extract_pattern_summary`가 반환하는 요약 문자열에 시퀀스 반복 라인
  (`- "A" → "B" 순서로 N번 반복 실행함`)이 추가로 포함될 수 있음. 내부 헬퍼
  `_extract_sequences(commands: list[str]) -> list[tuple[tuple[str, ...], int]]`,
  `_count_gapped_matches(commands: list[str], sequence: tuple[str, ...]) -> int` 신규.

**충돌 위험 없음** — 이 파일은 팀원이 최근 건드리지 않았다.

- [ ] **Step 1: 실패하는 테스트 작성**

`web-server/tests/test_preprocessing.py` 끝에 추가 (기존 `_assistant_bash_event`,
`_line` 헬퍼 재사용):

```python
def test_extracts_sequence_with_gap_between_steps():
    commands = ["migrate", "other", "seed", "migrate", "seed"]
    events = [_assistant_bash_event(c) for c in commands]
    summary = extract_pattern_summary("\n".join(_line(e) for e in events))
    assert summary is not None
    assert '"migrate" → "seed" 순서로 2번 반복 실행함' in summary


def test_sequence_below_threshold_not_extracted():
    events = [_assistant_bash_event(c) for c in ["migrate", "seed"]]
    summary = extract_pattern_summary("\n".join(_line(e) for e in events))
    assert summary is None


def test_sequence_extends_to_three_steps_and_drops_shorter_chain():
    events = []
    for _ in range(2):
        events.append(_assistant_bash_event("migrate"))
        events.append(_assistant_bash_event("seed"))
        events.append(_assistant_bash_event("restart"))
    summary = extract_pattern_summary("\n".join(_line(e) for e in events))
    assert summary is not None
    assert '"migrate" → "seed" → "restart" 순서로 2번 반복 실행함' in summary
    assert '"migrate" → "seed" 순서로' not in summary


def test_sequence_capped_at_four_steps():
    commands_cycle = ["a", "b", "c", "d", "e"]
    events = []
    for _ in range(2):
        for cmd in commands_cycle:
            events.append(_assistant_bash_event(cmd))
    summary = extract_pattern_summary("\n".join(_line(e) for e in events))
    assert summary is not None
    sequence_lines = [line for line in summary.splitlines() if "순서로" in line]
    assert sequence_lines
    for line in sequence_lines:
        assert line.count("→") <= 3
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `web-server/.venv/bin/python -m pytest web-server/tests/test_preprocessing.py -v`
Expected: FAIL — 새 테스트 4개 모두 실패(시퀀스 라인이 아예 생성 안 됨).

- [ ] **Step 3: 최소 구현**

`web-server/preprocessing.py`의 `REPEAT_THRESHOLD = 3` 줄 아래에 상수 추가:

```python
MIN_SEQUENCE_REPEATS = 2  # skill 후보는 hook/claude_md보다 낮은 임계값 (DESIGN.md 결정)
MAX_SEQUENCE_LENGTH = 4
```

파일 끝에 두 헬퍼 함수 추가:

```python
def _count_gapped_matches(commands: list[str], sequence: tuple[str, ...]) -> int:
    """sequence가 commands 안에서 순서대로(중간에 다른 커맨드가 껴도 됨) 몇 번
    겹치지 않게(non-overlapping) 나타나는지 센다."""
    count = 0
    pointer = 0
    for command in commands:
        if command == sequence[pointer]:
            pointer += 1
            if pointer == len(sequence):
                count += 1
                pointer = 0
    return count


def _extract_sequences(commands: list[str]) -> list[tuple[tuple[str, ...], int]]:
    """반복되는 순서 시퀀스(2~4단계)를 찾는다. Apriori 방식: 2단계 쌍부터
    임계값을 넘는 것을 찾고, 통과한 시퀀스를 한 단계씩 확장 시도한다 —
    확장에 성공하면(임계값 유지) 더 짧은 버전은 버리고 가장 긴 체인만 남긴다."""
    distinct = list(dict.fromkeys(commands))  # 등장 순서 유지한 채 중복 제거

    candidates: dict[tuple[str, ...], int] = {}
    for a in distinct:
        for b in distinct:
            if a == b:
                continue
            count = _count_gapped_matches(commands, (a, b))
            if count >= MIN_SEQUENCE_REPEATS:
                candidates[(a, b)] = count

    accepted: dict[tuple[str, ...], int] = dict(candidates)
    frontier = candidates

    while frontier:
        next_frontier: dict[tuple[str, ...], int] = {}
        for seq in frontier:
            if len(seq) >= MAX_SEQUENCE_LENGTH:
                continue
            for extra in distinct:
                if extra in seq:
                    continue
                extended = seq + (extra,)
                count = _count_gapped_matches(commands, extended)
                if count >= MIN_SEQUENCE_REPEATS:
                    next_frontier[extended] = count
                    accepted[extended] = count
                    accepted.pop(seq, None)
        frontier = next_frontier

    return sorted(accepted.items(), key=lambda item: (-len(item[0]), -item[1]))
```

`extract_pattern_summary` 함수 안, 기존 두 `for ... in Counter(...).most_common():`
루프 뒤(즉 `if not summary_lines:` 줄 바로 전)에 추가:

```python
    for sequence, count in _extract_sequences(bash_commands):
        arrow_chain = " → ".join(f'"{s}"' for s in sequence)
        summary_lines.append(f"- {arrow_chain} 순서로 {count}번 반복 실행함")
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `web-server/.venv/bin/python -m pytest web-server/tests/test_preprocessing.py -v`
Expected: PASS (10개 전체)

- [ ] **Step 5: 커밋**

```bash
git add web-server/preprocessing.py web-server/tests/test_preprocessing.py
git commit -m "feat(web-server): extract gapped multi-step bash sequences for skill candidates"
```

---

### Task 4: `Skill` 테이블 + `ProjectRevision` 확장

**Files:**
- Modify: `web-server/models.py`

**Interfaces:**
- Produces: `Skill(id, project_id, name, description, steps_content, created_at, updated_at)`,
  `ProjectRevision.target`에 `"skill"` 값 허용(문서화, 이미 `str` 타입이라 코드 변경 불필요),
  `ProjectRevision.skill_id: Optional[str]` 신규.

**⚠️ 충돌 위험 파일** — 시작 전에 `git fetch origin && git log --oneline feature/ai-server..origin/feature/ai-server`
확인 후 새 커밋 있으면 `git pull --rebase`.

- [ ] **Step 1: 새 테이블/컬럼 추가 (모델 변경은 이 프로젝트 관례상 별도 Red 테스트 없이
  진행 — 이후 태스크의 라우터 테스트가 실질적으로 검증한다. 다른 스프린트의
  T-01/T-02 "테이블 생성 확인"과 동일한 패턴)**

`web-server/models.py`의 `class ProjectRevision(SQLModel, table=True):` 블록에서
`target: str = Field(default="content")  # 'content' | 'hooks'` 줄을 다음으로 변경:

```python
    target: str = Field(default="content")  # 'content' | 'hooks' | 'skill'
    skill_id: Optional[str] = Field(default=None, foreign_key="skills.id")
```

파일 끝(`class GroupMembership` 다음)에 추가:

```python

class Skill(SQLModel, table=True):
    __tablename__ = "skills"
    id: str = Field(default_factory=new_id, primary_key=True)
    project_id: str = Field(foreign_key="projects.id")
    name: str
    description: str
    steps_content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

- [ ] **Step 2: 로컬 `app.db` 마이그레이션 (있다면)**

로컬에 이미 `web-server/app.db`가 있고 서버를 실행해본 적이 있다면(이전
스프린트들과 동일한 이슈), `SQLModel.metadata.create_all()`은 기존
`project_revisions` 테이블에 새 컬럼을 안 붙여준다. 다음을 실행:

```bash
sqlite3 web-server/app.db "ALTER TABLE project_revisions ADD COLUMN skill_id VARCHAR;"
```

(`skills` 테이블 자체는 새 테이블이라 `create_all()`이 알아서 만들어준다 —
`ALTER TABLE` 불필요.)

- [ ] **Step 3: 임포트 확인**

Run: `web-server/.venv/bin/python -c "import importlib; importlib.import_module('web-server.models').Skill; print('ok')"`
Expected: `ok` 출력 (문법 오류 없이 임포트됨)

- [ ] **Step 4: 커밋**

```bash
git add web-server/models.py
git commit -m "feat(web-server): add Skill table and ProjectRevision.skill_id column"
```

---

### Task 5: 매칭 — `match_skill_candidate`

**Files:**
- Modify: `web-server/matching.py`
- Test: `web-server/tests/test_matching.py`

**Interfaces:**
- Consumes: Task 4의 `RecommendationGroup`(기존, `type="skill"` 값만 새로 씀).
- Produces: `match_skill_candidate(db, project_id, user_id, session_id, skill_description, vector, reason, confidence) -> RecommendationGroup`.

**충돌 위험 낮음** — `matching.py`는 팀원이 최근 안 건드림. 그래도 Task 4에서 pull했다면
그 상태 유지.

- [ ] **Step 1: 실패하는 테스트 작성**

`web-server/tests/test_matching.py` 끝에 추가:

```python
def test_skill_groups_by_similarity_not_exact_text(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    member, member_token = make_user_and_token(db_session, "member")
    project_id = _create_project(client, owner_token)
    client.post(
        f"/projects/{project_id}/invite",
        json={"username": member.username},
        headers=auth_headers(owner_token),
    )
    session1 = _make_session(db_session, project_id, owner.user_id)
    session2 = _make_session(db_session, project_id, member.user_id)

    vector = [1.0, 0.0, 0.0]
    similar_vector = [0.99, 0.01, 0.0]

    matching.match_skill_candidate(
        db_session, project_id, owner.user_id, session1,
        "마이그레이션 후 시드와 재시작을 순서대로 진행한다", vector, "r1", "high",
    )
    group = matching.match_skill_candidate(
        db_session, project_id, member.user_id, session2,
        "DB 마이그레이션하고 시드 넣은 다음 서버를 재시작한다", similar_vector, "r2", "medium",
    )
    assert group.promoted is True
    assert group.type == "skill"


def test_skill_group_not_promoted_with_one_member(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)
    session_id = _make_session(db_session, project_id, owner.user_id)

    group = matching.match_skill_candidate(
        db_session, project_id, owner.user_id, session_id,
        "마이그레이션 후 시드와 재시작을 순서대로 진행한다", [1.0, 0.0], "r1", "high",
    )
    assert group.promoted is False
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `web-server/.venv/bin/python -m pytest web-server/tests/test_matching.py -v`
Expected: FAIL — `AttributeError: module 'web-server.matching' has no attribute 'match_skill_candidate'`

- [ ] **Step 3: 최소 구현**

`web-server/matching.py`의 `match_claude_md_candidate` 함수 바로 다음에 추가
(내용은 `match_claude_md_candidate`와 동일 구조, `type_`만 `"skill"`):

```python
def match_skill_candidate(
    db: DBSession,
    project_id: str,
    user_id: int,
    session_id: str,
    skill_description: str,
    vector: list[float],
    reason: str,
    confidence: str,
) -> RecommendationGroup:
    candidates = db.exec(
        select(RecommendationGroup).where(
            RecommendationGroup.project_id == project_id,
            RecommendationGroup.type == "skill",
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
        db, existing, project_id, "skill", skill_description, user_id,
        session_id, skill_description, reason, confidence,
    )
    if existing is None:
        group.representative_vector = json.dumps(vector)
        db.add(group)
        db.commit()
        db.refresh(group)
    return group
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `web-server/.venv/bin/python -m pytest web-server/tests/test_matching.py -v`
Expected: PASS (전체)

- [ ] **Step 5: 커밋**

```bash
git add web-server/matching.py web-server/tests/test_matching.py
git commit -m "feat(web-server): add skill candidate matching by description embedding similarity"
```

---

### Task 6: 스킬 CRUD 라우터 (`routers/skills.py` 신규)

**Files:**
- Create: `web-server/routers/skills.py`
- Modify: `web-server/main.py` (라우터 등록)
- Test: `web-server/tests/test_skills.py` (신규)

**Interfaces:**
- Consumes: Task 4의 `Skill` 모델.
- Produces: `GET/PUT/DELETE /projects/{project_id}/skills`, `/skills/{skill_id}` 엔드포인트.

**충돌 위험**: `main.py`는 28줄짜리 작은 파일이라 위험 낮음. 새 라우터 파일이라 그 자체는
충돌 없음.

- [ ] **Step 1: 실패하는 테스트 작성**

`web-server/tests/test_skills.py` 신규 생성:

```python
from .conftest import auth_headers, make_user_and_token, models


def _create_project(client, owner_token: str) -> str:
    resp = client.post(
        "/projects", json={"name": "test"}, headers=auth_headers(owner_token)
    )
    return resp.json()["id"]


def _create_skill_directly(db_session, project_id: str) -> str:
    skill = models.Skill(
        project_id=project_id,
        name="run-migrations",
        description="마이그레이션을 실행한다",
        steps_content="1. migrate\n2. seed\n3. restart",
    )
    db_session.add(skill)
    db_session.commit()
    db_session.refresh(skill)
    return skill.id


def test_list_skills_returns_project_skills(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)
    _create_skill_directly(db_session, project_id)

    resp = client.get(f"/projects/{project_id}/skills", headers=auth_headers(owner_token))
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["name"] == "run-migrations"


def test_non_member_cannot_list_skills(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    outsider, outsider_token = make_user_and_token(db_session, "outsider")
    project_id = _create_project(client, owner_token)

    resp = client.get(
        f"/projects/{project_id}/skills", headers=auth_headers(outsider_token)
    )
    assert resp.status_code == 403


def test_get_single_skill(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)
    skill_id = _create_skill_directly(db_session, project_id)

    resp = client.get(
        f"/projects/{project_id}/skills/{skill_id}", headers=auth_headers(owner_token)
    )
    assert resp.status_code == 200
    assert resp.json()["steps_content"] == "1. migrate\n2. seed\n3. restart"


def test_update_skill_creates_skill_revision(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)
    skill_id = _create_skill_directly(db_session, project_id)

    resp = client.put(
        f"/projects/{project_id}/skills/{skill_id}",
        json={
            "name": "run-migrations",
            "description": "수정된 설명",
            "steps_content": "1. migrate\n2. seed",
        },
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "수정된 설명"

    revisions_resp = client.get(
        f"/projects/{project_id}/revisions?target=skill", headers=auth_headers(owner_token)
    )
    assert revisions_resp.status_code == 200
    assert len(revisions_resp.json()) == 1


def test_non_member_cannot_update_skill(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    outsider, outsider_token = make_user_and_token(db_session, "outsider")
    project_id = _create_project(client, owner_token)
    skill_id = _create_skill_directly(db_session, project_id)

    resp = client.put(
        f"/projects/{project_id}/skills/{skill_id}",
        json={"name": "x", "description": "x", "steps_content": "x"},
        headers=auth_headers(outsider_token),
    )
    assert resp.status_code == 403


def test_delete_skill(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)
    skill_id = _create_skill_directly(db_session, project_id)

    resp = client.delete(
        f"/projects/{project_id}/skills/{skill_id}", headers=auth_headers(owner_token)
    )
    assert resp.status_code == 200

    list_resp = client.get(
        f"/projects/{project_id}/skills", headers=auth_headers(owner_token)
    )
    assert list_resp.json() == []


def test_get_nonexistent_skill_returns_404(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)

    resp = client.get(
        f"/projects/{project_id}/skills/does-not-exist", headers=auth_headers(owner_token)
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `web-server/.venv/bin/python -m pytest web-server/tests/test_skills.py -v`
Expected: FAIL — 404 Not Found (라우터가 없어서 모든 요청이 404).

- [ ] **Step 3: 최소 구현**

`web-server/routers/skills.py` 신규 생성:

```python
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
```

`web-server/main.py`의 import 줄:
```python
from .routers import projects, auth, github_auth, presence, sessions
```
을 다음으로 변경:
```python
from .routers import projects, auth, github_auth, presence, sessions, skills
```
그리고 `app.include_router(sessions.router)` 줄 다음에 추가:
```python
app.include_router(skills.router)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `web-server/.venv/bin/python -m pytest web-server/tests/test_skills.py -v`
Expected: PASS (7개 전체)

- [ ] **Step 5: 전체 web-server 테스트로 회귀 확인**

Run: `web-server/.venv/bin/python -m pytest web-server/tests -v`
Expected: 전체 PASS

- [ ] **Step 6: 커밋**

```bash
git add web-server/routers/skills.py web-server/main.py web-server/tests/test_skills.py
git commit -m "feat(web-server): add Skill CRUD router (list/get/update/delete)"
```

---

### Task 7: 세션 업로드 오케스트레이션 + 적용 로직에 skill 연결

**Files:**
- Modify: `web-server/routers/sessions.py`
- Test: `web-server/tests/test_sessions.py` (끝에 추가)
- Test: `web-server/tests/test_apply_skill.py` (신규)

**Interfaces:**
- Consumes: Task 5의 `match_skill_candidate`, Task 6의 `Skill` 모델.
- Produces: `_create_skill_from_payload(db, project_id, payload: dict) -> None` 신규 헬퍼.

**⚠️ 가장 높은 충돌 위험 파일** — 시작 전 반드시
`git fetch origin && git log --oneline feature/ai-server..origin/feature/ai-server`로
새 커밋 확인 후 필요하면 `git pull --rebase`.

- [ ] **Step 1: 실패하는 테스트 작성 (업로드 오케스트레이션 연결)**

`web-server/tests/test_sessions.py` 끝에 추가:

```python
def test_skill_candidate_matches_and_promotes(client, db_session, monkeypatch):
    async def fake_analyze_skill(pattern_summary, client=None):
        return {
            "candidates": [
                {
                    "type": "skill",
                    "skill_name": "run-migrations",
                    "skill_description": "마이그레이션 후 시드와 재시작을 순서대로 진행한다",
                    "suggested_steps": "1. migrate\n2. seed\n3. restart",
                    "reason": "매번 이 순서로 실행하셨어요.",
                    "confidence": "high",
                }
            ],
            "remaining_rpd": 499,
        }

    async def fake_embed(text, client=None):
        return [0.1, 0.2, 0.3]

    monkeypatch.setattr(ai_client, "analyze", fake_analyze_skill)
    monkeypatch.setattr(ai_client, "embed", fake_embed)
    owner, owner_token = make_user_and_token(db_session, "owner")
    member, member_token = make_user_and_token(db_session, "member")
    project_id = _create_project(client, owner_token)
    client.post(
        f"/projects/{project_id}/invite",
        json={"username": member.username},
        headers=auth_headers(owner_token),
    )
    file_content = _jsonl_with_repeated_bash("npm test", 5)

    client.post(
        f"/projects/{project_id}/sessions",
        files={"file": ("s1.jsonl", io.BytesIO(file_content), "application/jsonl")},
        headers=auth_headers(owner_token),
    )
    second_resp = client.post(
        f"/projects/{project_id}/sessions",
        files={"file": ("s2.jsonl", io.BytesIO(file_content), "application/jsonl")},
        headers=auth_headers(member_token),
    )
    groups = second_resp.json()["updated_team_groups"]
    assert groups[0]["type"] == "skill"
    assert groups[0]["promoted"] is True
```

`web-server/tests/test_apply_skill.py` 신규 생성 (적용 시 실제 `Skill` 생성 확인):

```python
import io

from .conftest import auth_headers, make_user_and_token
from .test_sessions import _create_project, _jsonl_with_repeated_bash, ai_client


async def _fake_analyze_skill(pattern_summary, client=None):
    return {
        "candidates": [
            {
                "type": "skill",
                "skill_name": "run-migrations",
                "skill_description": "마이그레이션 후 시드와 재시작을 순서대로 진행한다",
                "suggested_steps": "1. migrate 실행\n2. seed 실행\n3. 서버 재시작",
                "reason": "매번 이 순서로 실행하셨어요.",
                "confidence": "high",
            }
        ],
        "remaining_rpd": 499,
    }


async def _fake_embed(text, client=None):
    return [0.1, 0.2, 0.3]


def _upload_and_get_recommendation_id(client, project_id, token) -> str:
    file_content = _jsonl_with_repeated_bash("npm test", 5)
    client.post(
        f"/projects/{project_id}/sessions",
        files={"file": ("s.jsonl", io.BytesIO(file_content), "application/jsonl")},
        headers=auth_headers(token),
    )
    resp = client.get(
        f"/projects/{project_id}/recommendations/me", headers=auth_headers(token)
    )
    return resp.json()[0]["id"]


def test_apply_personal_skill_recommendation_creates_skill(client, db_session, monkeypatch):
    monkeypatch.setattr(ai_client, "analyze", _fake_analyze_skill)
    monkeypatch.setattr(ai_client, "embed", _fake_embed)
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)
    rec_id = _upload_and_get_recommendation_id(client, project_id, owner_token)

    apply_resp = client.post(
        f"/projects/{project_id}/personal-recommendations/{rec_id}/apply",
        headers=auth_headers(owner_token),
    )
    assert apply_resp.status_code == 200

    skills_resp = client.get(
        f"/projects/{project_id}/skills", headers=auth_headers(owner_token)
    )
    assert skills_resp.status_code == 200
    assert len(skills_resp.json()) == 1
    assert skills_resp.json()[0]["name"] == "run-migrations"


def test_apply_team_skill_group_creates_skill(client, db_session, monkeypatch):
    monkeypatch.setattr(ai_client, "analyze", _fake_analyze_skill)
    monkeypatch.setattr(ai_client, "embed", _fake_embed)
    owner, owner_token = make_user_and_token(db_session, "owner")
    member, member_token = make_user_and_token(db_session, "member")
    project_id = _create_project(client, owner_token)
    client.post(
        f"/projects/{project_id}/invite",
        json={"username": member.username},
        headers=auth_headers(owner_token),
    )
    _upload_and_get_recommendation_id(client, project_id, owner_token)
    _upload_and_get_recommendation_id(client, project_id, member_token)

    team_resp = client.get(
        f"/projects/{project_id}/recommendations/team", headers=auth_headers(owner_token)
    )
    group_id = team_resp.json()[0]["id"]

    apply_resp = client.post(
        f"/projects/{project_id}/recommendation-groups/{group_id}/apply",
        headers=auth_headers(owner_token),
    )
    assert apply_resp.status_code == 200

    skills_resp = client.get(
        f"/projects/{project_id}/skills", headers=auth_headers(owner_token)
    )
    assert len(skills_resp.json()) == 1
    assert skills_resp.json()[0]["name"] == "run-migrations"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `web-server/.venv/bin/python -m pytest web-server/tests/test_sessions.py::test_skill_candidate_matches_and_promotes web-server/tests/test_apply_skill.py -v`
Expected: FAIL — `KeyError`/`match_skill_candidate` 미사용으로 skill 후보가
매칭 안 되고 `updated_team_groups`가 비거나, 적용해도 `Skill`이 생성 안 돼 목록이 빔.

- [ ] **Step 3: 최소 구현**

`web-server/routers/sessions.py` 상단 import 줄:
```python
from ..matching import match_claude_md_candidate, match_hook_candidate
from ..models import (
    GroupMembership,
    PersonalRecommendation,
    Project,
    ProjectMember,
    RecommendationGroup,
    Session as SessionModel,
    User,
)
```
을 다음으로 변경:
```python
from ..matching import match_claude_md_candidate, match_hook_candidate, match_skill_candidate
from ..models import (
    GroupMembership,
    PersonalRecommendation,
    Project,
    ProjectMember,
    RecommendationGroup,
    Session as SessionModel,
    Skill,
    User,
)
```

`upload_session` 함수 안, `elif candidate["type"] == "claude_md":` 블록
(`updated_groups.append(group)`로 끝나는 부분) 바로 다음에 추가:

```python
        elif candidate["type"] == "skill":
            vector = await ai_client.embed(candidate["skill_description"])
            group = match_skill_candidate(
                db, project_id, user.user_id, session.id,
                candidate["skill_description"], vector,
                candidate["reason"], candidate["confidence"],
            )
            updated_groups.append(group)
```

`_replace_prior_session` 함수 바로 위(파일 끝 쪽)에 새 헬퍼 추가:

```python
def _create_skill_from_payload(db: DBSession, project_id: str, payload: dict) -> None:
    db.add(
        Skill(
            project_id=project_id,
            name=payload["skill_name"],
            description=payload["skill_description"],
            steps_content=payload["suggested_steps"],
        )
    )
```

`apply_personal_recommendation` 함수에서 `rec.applied = True` / `db.add(rec)` 다음
줄에 추가:

```python
    if rec.type == "skill":
        _create_skill_from_payload(db, project_id, json.loads(rec.payload))
```

`apply_recommendation_group` 함수에서 `group.applied = True` / `db.add(group)`
다음 줄에 추가:

```python
    if group.type == "skill":
        representative_rec = db.exec(
            select(PersonalRecommendation)
            .where(PersonalRecommendation.group_id == group_id)
            .order_by(PersonalRecommendation.created_at)
        ).first()
        if representative_rec is not None:
            _create_skill_from_payload(db, project_id, json.loads(representative_rec.payload))
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `web-server/.venv/bin/python -m pytest web-server/tests/test_sessions.py web-server/tests/test_apply_skill.py -v`
Expected: PASS (전체)

- [ ] **Step 5: 전체 web-server 테스트로 회귀 확인**

Run: `web-server/.venv/bin/python -m pytest web-server/tests -v`
Expected: 전체 PASS

- [ ] **Step 6: 커밋**

```bash
git add web-server/routers/sessions.py web-server/tests/test_sessions.py web-server/tests/test_apply_skill.py
git commit -m "feat(web-server): wire skill matching into upload and create Skill on apply"
```

---

### Task 8: PUSH에 스킬 파일 추가

**Files:**
- Modify: `web-server/routers/projects.py`
- Test: `web-server/tests/test_push.py`

**⚠️ 충돌 위험 파일** — 시작 전 `git fetch origin && git log --oneline feature/ai-server..origin/feature/ai-server`
확인.

- [ ] **Step 1: 실패하는 테스트 작성**

`web-server/tests/test_push.py`의 `test_push_sends_both_claude_md_and_hooks` 함수
바로 다음에 추가:

```python
def test_push_sends_files_for_each_skill(client, db_session, monkeypatch):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project_with_repo_and_token(client, db_session, owner_token, owner)

    skill = models.Skill(
        project_id=project_id,
        name="run-migrations",
        description="마이그레이션 실행",
        steps_content="1. migrate\n2. seed",
    )
    db_session.add(skill)
    db_session.commit()

    calls = []
    monkeypatch.setattr(
        github_client, "push_file",
        lambda token, repo, path, content, message: calls.append(path),
    )

    resp = client.post(f"/projects/{project_id}/push", headers=auth_headers(owner_token))
    assert resp.status_code == 200
    assert calls == [
        "CLAUDE.md",
        ".claude/settings.json",
        ".claude/skills/run-migrations/SKILL.md",
    ]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `web-server/.venv/bin/python -m pytest web-server/tests/test_push.py::test_push_sends_files_for_each_skill -v`
Expected: FAIL — `calls == ["CLAUDE.md", ".claude/settings.json"]`(스킬 파일 없음).

- [ ] **Step 3: 최소 구현**

`web-server/routers/projects.py` 상단 import 줄:
```python
from ..models import Project, ProjectMember, ProjectRevision, User
```
을 다음으로 변경:
```python
from ..models import Project, ProjectMember, ProjectRevision, Skill, User
```

`push_to_github` 함수의 `github_client.push_file(... path=".claude/settings.json" ...)`
호출 바로 다음(같은 `try:` 블록 안, `except ValueError as e:` 전)에 추가:

```python
        skills = db.exec(select(Skill).where(Skill.project_id == project_id)).all()
        for skill in skills:
            skill_md = (
                f"---\nname: {skill.name}\ndescription: {skill.description}\n---\n\n"
                f"{skill.steps_content}"
            )
            github_client.push_file(
                token=token,
                repo=project.github_repo,
                path=f".claude/skills/{skill.name}/SKILL.md",
                content=skill_md,
                message=f"Update skill {skill.name} via {project.name}",
            )
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `web-server/.venv/bin/python -m pytest web-server/tests/test_push.py -v`
Expected: PASS (전체)

- [ ] **Step 5: 전체 web-server 테스트로 회귀 확인**

Run: `web-server/.venv/bin/python -m pytest web-server/tests -v`
Expected: 전체 PASS

- [ ] **Step 6: 커밋**

```bash
git add web-server/routers/projects.py web-server/tests/test_push.py
git commit -m "feat(web-server): push each skill to .claude/skills/<name>/SKILL.md"
```

---

## Phase 3 — 프론트엔드

### Task 9: `lib/projects.ts` — Skill 타입/함수 추가

**Files:**
- Modify: `frontend/lib/projects.ts`

**Interfaces:**
- Produces: `Skill`, `SkillPayload` 타입, `listSkills/getSkill/saveSkill/deleteSkill` 함수.
  `PersonalRecommendation.type`/`TeamRecommendation.type`에 `"skill"` 허용.

**충돌 위험 낮음** — 이 파일은 온보딩 스프린트 이후 팀원이 hooks 관련해서만 건드림,
스킬 관련 추가는 새 코드 블록이라 겹칠 여지 적음.

- [ ] **Step 1: 타입/함수 추가 (프론트는 TDD 대신 타입체크 + 수동 확인 — CLAUDE.md 4절)**

`export type PersonalRecommendation = {` 블록의 `type: "hook" | "claude_md";`를
`type: "hook" | "claude_md" | "skill";`로 변경.

`export type TeamRecommendation = {` 블록의 `type: "hook" | "claude_md";`도
동일하게 `type: "hook" | "claude_md" | "skill";`로 변경.

`export type ClaudeMdPayload = {...}` 블록 다음에 추가:

```typescript
export type SkillPayload = {
  skill_name: string;
  skill_description: string;
  suggested_steps: string;
  reason: string;
  confidence: "low" | "medium" | "high";
};
```

`PersonalRecommendation.payload` 필드 타입을
`payload: HookPayload | ClaudeMdPayload;`에서
`payload: HookPayload | ClaudeMdPayload | SkillPayload;`로 변경.

파일 끝에 추가:

```typescript
export type Skill = {
  id: string;
  name: string;
  description: string;
  steps_content: string;
  created_at: string;
  updated_at: string;
};

export async function listSkills(id: string): Promise<Skill[]> {
  const res = await fetch(`${API_BASE}/projects/${id}/skills`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("스킬 목록을 불러오지 못했습니다");
  return res.json();
}

export async function getSkill(id: string, skillId: string): Promise<Skill> {
  const res = await fetch(`${API_BASE}/projects/${id}/skills/${skillId}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("스킬을 찾을 수 없습니다");
  return res.json();
}

export async function saveSkill(
  id: string,
  skillId: string,
  data: { name: string; description: string; steps_content: string }
): Promise<Skill> {
  const res = await fetch(`${API_BASE}/projects/${id}/skills/${skillId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? "스킬 저장에 실패했습니다");
  }
  return res.json();
}

export async function deleteSkill(id: string, skillId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/projects/${id}/skills/${skillId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? "스킬 삭제에 실패했습니다");
  }
}
```

- [ ] **Step 2: 타입체크 확인**

Run: `cd frontend && npx tsc --noEmit`
Expected: exit code 0 (page.tsx는 아직 Skill 타입을 안 써서 에러 없음)

- [ ] **Step 3: 커밋**

```bash
git add frontend/lib/projects.ts
git commit -m "feat(frontend): add Skill type and CRUD functions to projects.ts"
```

---

### Task 10: 프로젝트 페이지 — Skill 탭 + 추천 카드 + 적용 플로우

**Files:**
- Modify: `frontend/app/project/[id]/page.tsx`

**Interfaces:**
- Consumes: Task 9의 `Skill`, `SkillPayload`, `listSkills/getSkill/saveSkill/deleteSkill`.

**⚠️ 가장 높은 충돌 위험 파일** — 시작 전 반드시
`git fetch origin && git log --oneline feature/ai-server..origin/feature/ai-server`
확인 후 새 커밋 있으면 `git pull --rebase`. 이 태스크는 되도록 한 번에 끝내고
바로 커밋 + push할 것(오래 열어두지 않기).

- [ ] **Step 1: import + 상태 추가**

`import { ... } from "@/lib/projects";` 블록에 추가:
```typescript
  listSkills,
  saveSkill,
  deleteSkill,
  type Skill,
  type SkillPayload,
```

`const [editorTab, setEditorTab] = useState<"content" | "hooks">("content");`를
다음으로 변경:
```typescript
  const [editorTab, setEditorTab] = useState<"content" | "hooks" | "skill">("content");
```

`const [recTab, setRecTab] = useState<"my" | "team">("my");` 다음 줄에 추가:
```typescript
  const [skills, setSkills] = useState<Skill[]>([]);
  const [selectedSkillId, setSelectedSkillId] = useState<string | null>(null);
  const [skillNameInput, setSkillNameInput] = useState("");
  const [skillDescriptionInput, setSkillDescriptionInput] = useState("");
  const [skillStepsInput, setSkillStepsInput] = useState("");
```

`const activeRecType = editorTab === "content" ? "claude_md" : "hook";`를
다음으로 변경:
```typescript
  const activeRecType =
    editorTab === "content" ? "claude_md" : editorTab === "hooks" ? "hook" : "skill";
```

- [ ] **Step 2: 스킬 목록 로드 useEffect 추가**

`useEffect(() => { getMyRecommendations... }, [projectId]);` 블록 다음에 추가:

```typescript
  useEffect(() => {
    listSkills(projectId)
      .then(setSkills)
      .catch((err) => setError((err as Error).message));
  }, [projectId]);
```

- [ ] **Step 3: 스킬 선택/삭제 핸들러 추가**

`function formatClaudeMdCandidate` 함수 위에 추가:

```typescript
  function selectSkill(skill: Skill) {
    setSelectedSkillId(skill.id);
    setSkillNameInput(skill.name);
    setSkillDescriptionInput(skill.description);
    setSkillStepsInput(skill.steps_content);
  }

  async function handleDeleteSkill() {
    if (!selectedSkillId) return;
    setError(null);
    try {
      await deleteSkill(projectId, selectedSkillId);
      setSkills((prev) => prev.filter((s) => s.id !== selectedSkillId));
      setSelectedSkillId(null);
      setSkillNameInput("");
      setSkillDescriptionInput("");
      setSkillStepsInput("");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function handleApplySkillPersonal(rec: PersonalRecommendation) {
    setError(null);
    try {
      await applyPersonalRecommendationApi(projectId, rec.id);
      const [updatedSkills, updatedPersonalRecs] = await Promise.all([
        listSkills(projectId),
        getMyRecommendations(projectId),
      ]);
      setSkills(updatedSkills);
      setPersonalRecs(updatedPersonalRecs);
      const payload = rec.payload as SkillPayload;
      const created = updatedSkills.find((s) => s.name === payload.skill_name);
      setEditorTab("skill");
      if (created) selectSkill(created);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function handleApplySkillTeam(rec: TeamRecommendation) {
    setError(null);
    try {
      await applyRecommendationGroup(projectId, rec.id);
      const [updatedSkills, updatedTeamRecs] = await Promise.all([
        listSkills(projectId),
        getTeamRecommendations(projectId),
      ]);
      setSkills(updatedSkills);
      setTeamRecs(updatedTeamRecs);
      const created = updatedSkills.find((s) => s.description === rec.representative_text);
      setEditorTab("skill");
      if (created) selectSkill(created);
    } catch (err) {
      setError((err as Error).message);
    }
  }
```

- [ ] **Step 4: `handleSave`에 skill 분기 추가**

`async function handleSave() {` 함수 본문 맨 앞, `setError(null); setSaving(true); try {`
바로 다음 줄에 추가 (기존 `if (editorTab === "hooks") {` 블록보다 먼저 와야 함):

```typescript
      if (editorTab === "skill") {
        if (!selectedSkillId) return;
        const updated = await saveSkill(projectId, selectedSkillId, {
          name: skillNameInput,
          description: skillDescriptionInput,
          steps_content: skillStepsInput,
        });
        setSkills((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
        const latest = await listRevisions(projectId);
        setRevisions(latest);
        return;
      }
```

- [ ] **Step 5: 탭 버튼에 "Skill" 추가**

`CLAUDE.md`/`Hooks` 탭 버튼이 있는 `<div className="mb-2 mt-10 flex gap-1">` 블록의
Hooks 버튼 다음에 추가:

```tsx
            <button
              type="button"
              onClick={() => setEditorTab("skill")}
              className={`rounded-md px-3 py-1 text-sm font-medium transition ${
                editorTab === "skill"
                  ? "bg-orange text-white"
                  : "text-ink/60 hover:bg-orange-light/40"
              }`}
            >
              Skill
            </button>
```

- [ ] **Step 6: 편집 영역을 3분기로 확장**

기존:
```tsx
          {editorTab === "content" ? (
            <textarea
              value={content}
              ...
            />
          ) : (
            <textarea
              value={hooksContent}
              ...
            />
          )}
```
을 다음으로 변경 (skill 탭일 때만 목록+편집기, 나머지는 기존 그대로):

```tsx
          {editorTab === "skill" ? (
            <div className="flex h-[420px] gap-4">
              <ul className="w-40 flex-shrink-0 overflow-y-auto flex flex-col gap-1">
                {skills.length === 0 && (
                  <p className="text-xs text-ink/40">아직 스킬이 없습니다</p>
                )}
                {skills.map((skill) => (
                  <li key={skill.id}>
                    <button
                      type="button"
                      onClick={() => selectSkill(skill)}
                      className={`w-full rounded-md px-2 py-1.5 text-left text-sm transition ${
                        selectedSkillId === skill.id
                          ? "bg-orange text-white"
                          : "text-ink/70 hover:bg-orange-light/40"
                      }`}
                    >
                      {skill.name}
                    </button>
                  </li>
                ))}
              </ul>
              {selectedSkillId ? (
                <div className="flex flex-1 flex-col gap-2">
                  <input
                    value={skillNameInput}
                    onChange={(e) => setSkillNameInput(e.target.value)}
                    placeholder="스킬 이름 (kebab-case)"
                    className="rounded-md border border-ink/15 px-3 py-2 text-sm font-mono focus:border-orange focus:outline-none focus:ring-2 focus:ring-orange/30"
                  />
                  <input
                    value={skillDescriptionInput}
                    onChange={(e) => setSkillDescriptionInput(e.target.value)}
                    placeholder="한 줄 설명"
                    className="rounded-md border border-ink/15 px-3 py-2 text-sm focus:border-orange focus:outline-none focus:ring-2 focus:ring-orange/30"
                  />
                  <textarea
                    value={skillStepsInput}
                    onChange={(e) => setSkillStepsInput(e.target.value)}
                    spellCheck={false}
                    className="flex-1 w-full resize-none rounded-lg border border-ink/10 bg-white p-4 font-mono text-sm leading-relaxed text-ink shadow-sm focus:border-orange focus:outline-none focus:ring-2 focus:ring-orange/30"
                  />
                  <button
                    type="button"
                    onClick={handleDeleteSkill}
                    className="self-start rounded-md border border-red-200 px-3 py-1.5 text-sm text-red-600 transition hover:bg-red-50"
                  >
                    이 스킬 삭제
                  </button>
                </div>
              ) : (
                <p className="flex-1 text-sm text-ink/40">
                  왼쪽에서 스킬을 선택하거나, 오른쪽 추천 카드에서 스킬을 적용해보세요.
                </p>
              )}
            </div>
          ) : editorTab === "content" ? (
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              spellCheck={false}
              className="h-[420px] w-full resize-none rounded-lg border border-ink/10 bg-white p-4 font-mono text-sm leading-relaxed text-ink shadow-sm focus:border-orange focus:outline-none focus:ring-2 focus:ring-orange/30"
            />
          ) : (
            <textarea
              value={hooksContent}
              onChange={(e) => setHooksContent(e.target.value)}
              spellCheck={false}
              className="h-[420px] w-full resize-none rounded-lg border border-ink/10 bg-white p-4 font-mono text-sm leading-relaxed text-ink shadow-sm focus:border-orange focus:outline-none focus:ring-2 focus:ring-orange/30"
            />
          )}
```

또한 바로 위 `<label>` 안내 문구도 skill 케이스를 추가:
```tsx
          <label className="mb-2 block text-sm font-medium text-ink/70">
            {editorTab === "content"
              ? "CLAUDE.md 내용을 수정 후 저장을 눌러주세요"
              : editorTab === "hooks"
              ? ".claude/settings.json 내용을 수정 후 저장을 눌러주세요 (JSON 형식)"
              : "왼쪽에서 스킬을 선택해 수정 후 저장을 눌러주세요"}
          </label>
```

- [ ] **Step 7: 추천 카드에 skill 렌더링 + 적용 분기 추가**

개인 추천 카드의 커맨드 미리보기 부분:
```tsx
                        <code className="mt-2 block rounded bg-orange-light/40 px-2 py-1 text-xs text-ink/70">
                          {rec.type === "claude_md"
                            ? (rec.payload as ClaudeMdPayload).suggested_text
                            : `${(rec.payload as HookPayload).event} → ${(rec.payload as HookPayload).command}`}
                        </code>
```
을 다음으로 변경:
```tsx
                        <code className="mt-2 block rounded bg-orange-light/40 px-2 py-1 text-xs text-ink/70">
                          {rec.type === "claude_md"
                            ? (rec.payload as ClaudeMdPayload).suggested_text
                            : rec.type === "hook"
                            ? `${(rec.payload as HookPayload).event} → ${(rec.payload as HookPayload).command}`
                            : `${(rec.payload as SkillPayload).skill_name}: ${(rec.payload as SkillPayload).suggested_steps}`}
                        </code>
```

같은 카드의 "적용하기" 버튼:
```tsx
                        <button
                          type="button"
                          onClick={() => applyPersonalRecommendation(rec)}
                          disabled={isApplied}
                          ...
```
을 다음으로 변경:
```tsx
                        <button
                          type="button"
                          onClick={() =>
                            rec.type === "skill"
                              ? handleApplySkillPersonal(rec)
                              : applyPersonalRecommendation(rec)
                          }
                          disabled={isApplied}
                          ...
```

팀 추천 카드의 "적용하기" 버튼도 동일하게:
```tsx
                      <button
                        type="button"
                        onClick={() => applyTeamRecommendation(rec)}
                        disabled={isApplied}
                        ...
```
을 다음으로 변경:
```tsx
                      <button
                        type="button"
                        onClick={() =>
                          rec.type === "skill"
                            ? handleApplySkillTeam(rec)
                            : applyTeamRecommendation(rec)
                        }
                        disabled={isApplied}
                        ...
```

- [ ] **Step 8: 변경 이력 배지에 "Skill" 추가**

```tsx
                      <span
                        className={`rounded px-1.5 py-0.5 text-xs font-medium ${
                          r.target === "hooks"
                            ? "bg-orange-light/60 text-orange-dark"
                            : "bg-ink/10 text-ink/60"
                        }`}
                      >
                        {r.target === "hooks" ? "Hooks" : "CLAUDE.md"}
                      </span>
```
을 다음으로 변경:
```tsx
                      <span
                        className={`rounded px-1.5 py-0.5 text-xs font-medium ${
                          r.target === "hooks"
                            ? "bg-orange-light/60 text-orange-dark"
                            : r.target === "skill"
                            ? "bg-blue-100 text-blue-700"
                            : "bg-ink/10 text-ink/60"
                        }`}
                      >
                        {r.target === "hooks" ? "Hooks" : r.target === "skill" ? "Skill" : "CLAUDE.md"}
                      </span>
```

- [ ] **Step 9: 타입체크**

Run: `cd frontend && npx tsc --noEmit`
Expected: exit code 0

- [ ] **Step 10: 커밋 + push**

```bash
git add frontend/app/project/\[id\]/page.tsx
git commit -m "feat(frontend): add Skill tab, recommendation cards, and apply flow"
git push origin feature/ai-server
```

(가장 위험한 파일이므로 완료 즉시 push해서 팀원 작업과의 diff 창을 최소화한다.)

---

### Task 11: 전체 검증

**Files:** 없음 (검증만)

- [ ] **Step 1: 전체 백엔드 테스트**

Run: `ai_server/.venv/bin/python -m pytest ai_server -q && web-server/.venv/bin/python -m pytest web-server/tests -q`
Expected: 둘 다 전체 PASS

- [ ] **Step 2: 프론트 타입체크**

Run: `cd frontend && npx tsc --noEmit`
Expected: exit code 0

- [ ] **Step 3: 브라우저 수동 시나리오**

세 서버(ai_server:8001, web-server:8000, frontend:3000) 기동 후:
1. 반복되는 bash 시퀀스(예: `migrate`→`seed`→`restart`를 2회 이상)가 담긴
   세션 JSONL을 업로드해 skill 후보가 뜨는지 확인.
2. "적용하기" 클릭 → Skill 탭으로 자동 전환되고 방금 만든 스킬이 선택된 상태로
   보이는지 확인.
3. 이름/설명/steps 수정 후 "저장" → 변경 이력에 "Skill" 배지로 기록되는지 확인.
4. 2계정으로 같은 시퀀스를 업로드해 팀 추천으로 승격되는지, 승격된 팀 추천
   "적용하기"도 스킬을 만드는지 확인.
5. GitHub repo 연결 후 PUSH → 레포에 `.claude/skills/<name>/SKILL.md`가
   실제로 생성되는지 확인.
6. "이 스킬 삭제" 클릭 → 목록에서 사라지는지 확인.

- [ ] **Step 4: 커밋(수동 확인 결과를 스프린트 문서에 기록하고 싶다면 별도 요청 시)**

이 태스크 자체는 코드 변경이 없으므로 커밋 불필요. 스프린트 문서
(`docs/sprints/`)에 완료 기록을 남기고 싶으면 사용자에게 확인 후 진행.
