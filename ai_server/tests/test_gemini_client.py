import pytest
import requests
from google.genai import errors

from ai_server.gemini_client import (
    GeminiCallFailed,
    GeminiQuotaExceeded,
    call_gemini_analyze,
)
from ai_server.schemas import (
    AnalyzeResponse,
    ClaudeMdCandidate,
    GeminiAnalyzeSchema,
    GeminiClaudeMdCandidate,
    GeminiHookCandidate,
    HookCandidate,
)
from ai_server.tests.fakes import FakeClient


class FakeResponse:
    def __init__(self, parsed):
        self.parsed = parsed


class FakeModels:
    """실제 client.aio.models.generate_content 자리에 들어가는 가짜.

    responses 리스트를 순서대로 소비한다. 항목이 Exception이면 raise,
    GeminiAnalyzeSchema면 FakeResponse로 감싸 반환한다 (response.parsed 자리)."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.call_count = 0

    async def generate_content(self, **kwargs):
        self.call_count += 1
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeResponse(parsed=item)


def make_client_error(status_code: int) -> errors.ClientError:
    """실제 google.genai.errors.ClientError 인스턴스를 생성한다 (429 판별 테스트용)."""
    resp = requests.Response()
    resp.status_code = status_code
    resp._content = (
        b'{"error": {"code": %d, "message": "boom", "status": "RESOURCE_EXHAUSTED"}}'
        % status_code
    )
    return errors.ClientError(status_code, resp)


EMPTY_GEMINI_RESPONSE = GeminiAnalyzeSchema(hook_candidates=[], claude_md_candidates=[])
EMPTY_ANALYZE_RESPONSE = AnalyzeResponse(candidates=[])


@pytest.mark.asyncio
async def test_succeeds_on_first_try():
    client = FakeClient(FakeModels([EMPTY_GEMINI_RESPONSE]))
    result = await call_gemini_analyze(client, "패턴 요약")
    assert result == EMPTY_ANALYZE_RESPONSE
    assert client.aio.models.call_count == 1


@pytest.mark.asyncio
async def test_retries_once_then_succeeds():
    client = FakeClient(FakeModels([RuntimeError("일시적 오류"), EMPTY_GEMINI_RESPONSE]))
    result = await call_gemini_analyze(client, "패턴 요약")
    assert result == EMPTY_ANALYZE_RESPONSE
    assert client.aio.models.call_count == 2


@pytest.mark.asyncio
async def test_fails_after_two_attempts():
    client = FakeClient(FakeModels([RuntimeError("오류1"), RuntimeError("오류2")]))
    with pytest.raises(GeminiCallFailed):
        await call_gemini_analyze(client, "패턴 요약")
    assert client.aio.models.call_count == 2


@pytest.mark.asyncio
async def test_raises_when_response_not_parsed():
    # 스키마 강제에도 불구하고 Gemini가 malformed 응답을 주는 경우
    client = FakeClient(FakeModels([None, None]))
    with pytest.raises(GeminiCallFailed):
        await call_gemini_analyze(client, "패턴 요약")


@pytest.mark.asyncio
async def test_raises_quota_exceeded_on_429_without_retry():
    # 실제 google-genai SDK가 던지는 ClientError(429)는 GeminiQuotaExceeded로
    # 구분되고, 재시도 없이 즉시 실패한다 (RpdCounter가 대부분 사전 차단하는
    # 희귀 레이스 컨디션이므로 재시도해도 성공 가능성이 낮음).
    client = FakeClient(FakeModels([make_client_error(429), EMPTY_GEMINI_RESPONSE]))
    with pytest.raises(GeminiQuotaExceeded):
        await call_gemini_analyze(client, "패턴 요약")
    assert client.aio.models.call_count == 1


@pytest.mark.asyncio
async def test_non_429_client_error_still_retries():
    # 429가 아닌 ClientError(예: 400)는 일반 실패 경로를 타고 재시도한다.
    client = FakeClient(FakeModels([make_client_error(400), EMPTY_GEMINI_RESPONSE]))
    result = await call_gemini_analyze(client, "패턴 요약")
    assert result == EMPTY_ANALYZE_RESPONSE
    assert client.aio.models.call_count == 2


@pytest.mark.asyncio
async def test_injects_type_field_when_converting_gemini_response():
    # Gemini는 anyOf/const를 지원하지 않아 type 필드 없이 hook_candidates/
    # claude_md_candidates로 나눠 응답한다 (2026-07-13, 실제 API 검증 중 발견).
    # call_gemini_analyze는 리스트 소속에 따라 type을 채워 AnalyzeResponse
    # (Union 기반)로 조립해야 한다.
    gemini_response = GeminiAnalyzeSchema(
        hook_candidates=[
            GeminiHookCandidate(
                event="PostToolUse",
                matcher="Edit",
                command="npm test",
                reason="테스트를 항상 직접 돌리셨어요.",
                confidence="high",
            )
        ],
        claude_md_candidates=[
            GeminiClaudeMdCandidate(
                suggested_text="탭 대신 스페이스를 사용합니다.",
                reason="여러 번 정정하셨어요.",
                confidence="medium",
            )
        ],
    )
    client = FakeClient(FakeModels([gemini_response]))

    result = await call_gemini_analyze(client, "패턴 요약")

    assert result == AnalyzeResponse(
        candidates=[
            HookCandidate(
                type="hook",
                event="PostToolUse",
                matcher="Edit",
                command="npm test",
                reason="테스트를 항상 직접 돌리셨어요.",
                confidence="high",
            ),
            ClaudeMdCandidate(
                type="claude_md",
                suggested_text="탭 대신 스페이스를 사용합니다.",
                reason="여러 번 정정하셨어요.",
                confidence="medium",
            ),
        ]
    )
