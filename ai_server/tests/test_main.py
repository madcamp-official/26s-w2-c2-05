from fastapi.testclient import TestClient
from ai_server.main import app, get_gemini_client
from ai_server.schemas import AnalyzeResponse, HookCandidate, OnboardingResponse
from ai_server.gemini_client import GeminiCallFailed, GeminiQuotaExceeded


class StubClient:
    """analyze/embed 호출 함수를 직접 갈아끼우지 않고, FastAPI 의존성
    오버라이드로 이 스텁 클라이언트 자체를 주입한다."""


client = TestClient(app)


def test_analyze_endpoint_returns_candidates_and_remaining_rpd(monkeypatch):
    async def fake_call(client, pattern_summary):
        return AnalyzeResponse(
            candidates=[
                HookCandidate(
                    type="hook",
                    event="PostToolUse",
                    matcher="Edit",
                    command="npm test",
                    reason="테스트를 항상 직접 돌리셨어요.",
                    confidence="high",
                )
            ]
        )

    monkeypatch.setattr("ai_server.main.call_gemini_analyze", fake_call)
    monkeypatch.setattr("ai_server.main.gemini_analyze_rpd_counter.consume", lambda: True)
    monkeypatch.setattr("ai_server.main.gemini_analyze_rpd_counter.remaining", lambda: 19)
    app.dependency_overrides[get_gemini_client] = lambda: StubClient()

    resp = client.post("/analyze", json={"pattern_summary": "npm test 5회 반복"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["candidates"][0]["command"] == "npm test"
    assert body["remaining_rpd"] == 19
    app.dependency_overrides.clear()


def test_analyze_endpoint_returns_429_when_rpd_exhausted(monkeypatch):
    async def fake_call_should_not_be_called(client, pattern_summary):
        raise AssertionError("RPD 소진 시 Gemini를 호출하면 안 됨")

    monkeypatch.setattr("ai_server.main.call_gemini_analyze", fake_call_should_not_be_called)
    monkeypatch.setattr("ai_server.main.gemini_analyze_rpd_counter.consume", lambda: False)
    app.dependency_overrides[get_gemini_client] = lambda: StubClient()

    resp = client.post("/analyze", json={"pattern_summary": "패턴"})

    assert resp.status_code == 429
    app.dependency_overrides.clear()


def test_analyze_endpoint_returns_429_on_gemini_quota_exceeded(monkeypatch):
    async def fake_call(client, pattern_summary):
        raise GeminiQuotaExceeded("레이스 컨디션으로 실제 429")

    monkeypatch.setattr("ai_server.main.call_gemini_analyze", fake_call)
    monkeypatch.setattr("ai_server.main.gemini_analyze_rpd_counter.consume", lambda: True)
    app.dependency_overrides[get_gemini_client] = lambda: StubClient()

    resp = client.post("/analyze", json={"pattern_summary": "패턴"})

    assert resp.status_code == 429
    app.dependency_overrides.clear()


def test_analyze_endpoint_returns_503_on_other_failure(monkeypatch):
    async def fake_call(client, pattern_summary):
        raise GeminiCallFailed("재시도 후에도 실패")

    monkeypatch.setattr("ai_server.main.call_gemini_analyze", fake_call)
    monkeypatch.setattr("ai_server.main.gemini_analyze_rpd_counter.consume", lambda: True)
    app.dependency_overrides[get_gemini_client] = lambda: StubClient()

    resp = client.post("/analyze", json={"pattern_summary": "패턴"})

    assert resp.status_code == 503
    app.dependency_overrides.clear()


def test_embed_endpoint_returns_vector(monkeypatch):
    from ai_server.schemas import EmbedResponse

    async def fake_call(client, text):
        return EmbedResponse(vector=[0.1, 0.2])

    monkeypatch.setattr("ai_server.main.call_gemini_embed", fake_call)
    app.dependency_overrides[get_gemini_client] = lambda: StubClient()

    resp = client.post("/embed", json={"text": "스페이스로 들여쓰기 통일"})

    assert resp.status_code == 200
    assert resp.json()["vector"] == [0.1, 0.2]
    app.dependency_overrides.clear()


ONBOARDING_REQUEST_BODY = {
    "principles": ["tdd"],
    "tech_stack": "Python, FastAPI",
    "team_or_individual": "team",
    "indent_style": "spaces",
}


def test_onboarding_endpoint_returns_base_claude_md(monkeypatch):
    async def fake_call(client, req):
        return OnboardingResponse(base_claude_md="# CLAUDE.md\n\n- 스페이스 사용")

    monkeypatch.setattr("ai_server.main.call_gemini_onboarding", fake_call)
    monkeypatch.setattr("ai_server.main.gemini_analyze_rpd_counter.consume", lambda: True)
    app.dependency_overrides[get_gemini_client] = lambda: StubClient()

    resp = client.post("/generate-base-claude-md", json=ONBOARDING_REQUEST_BODY)

    assert resp.status_code == 200
    assert resp.json()["base_claude_md"].startswith("# CLAUDE.md")
    app.dependency_overrides.clear()


def test_onboarding_endpoint_returns_429_when_rpd_exhausted(monkeypatch):
    async def fake_call_should_not_be_called(client, req):
        raise AssertionError("RPD 소진 시 Gemini를 호출하면 안 됨")

    monkeypatch.setattr("ai_server.main.call_gemini_onboarding", fake_call_should_not_be_called)
    monkeypatch.setattr("ai_server.main.gemini_analyze_rpd_counter.consume", lambda: False)
    app.dependency_overrides[get_gemini_client] = lambda: StubClient()

    resp = client.post("/generate-base-claude-md", json=ONBOARDING_REQUEST_BODY)

    assert resp.status_code == 429
    app.dependency_overrides.clear()


def test_onboarding_endpoint_returns_429_on_gemini_quota_exceeded(monkeypatch):
    async def fake_call(client, req):
        raise GeminiQuotaExceeded("레이스 컨디션으로 실제 429")

    monkeypatch.setattr("ai_server.main.call_gemini_onboarding", fake_call)
    monkeypatch.setattr("ai_server.main.gemini_analyze_rpd_counter.consume", lambda: True)
    app.dependency_overrides[get_gemini_client] = lambda: StubClient()

    resp = client.post("/generate-base-claude-md", json=ONBOARDING_REQUEST_BODY)

    assert resp.status_code == 429
    app.dependency_overrides.clear()


def test_onboarding_endpoint_returns_503_on_other_failure(monkeypatch):
    async def fake_call(client, req):
        raise GeminiCallFailed("재시도 후에도 실패")

    monkeypatch.setattr("ai_server.main.call_gemini_onboarding", fake_call)
    monkeypatch.setattr("ai_server.main.gemini_analyze_rpd_counter.consume", lambda: True)
    app.dependency_overrides[get_gemini_client] = lambda: StubClient()

    resp = client.post("/generate-base-claude-md", json=ONBOARDING_REQUEST_BODY)

    assert resp.status_code == 503
    app.dependency_overrides.clear()


def test_remaining_rpd_endpoint_returns_current_count(monkeypatch):
    monkeypatch.setattr("ai_server.main.gemini_analyze_rpd_counter.remaining", lambda: 342)

    resp = client.get("/remaining-rpd")

    assert resp.status_code == 200
    assert resp.json() == {"remaining_rpd": 342}


def test_remaining_rpd_endpoint_does_not_consume_quota(monkeypatch):
    calls = {"consume": 0}

    def fake_remaining():
        return 500

    def fake_consume():
        calls["consume"] += 1
        return True

    monkeypatch.setattr("ai_server.main.gemini_analyze_rpd_counter.remaining", fake_remaining)
    monkeypatch.setattr("ai_server.main.gemini_analyze_rpd_counter.consume", fake_consume)

    client.get("/remaining-rpd")
    client.get("/remaining-rpd")

    assert calls["consume"] == 0
