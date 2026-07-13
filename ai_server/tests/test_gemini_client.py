import pytest
import requests
from google.genai import errors

from ai_server.gemini_client import (
    GeminiCallFailed,
    GeminiQuotaExceeded,
    call_gemini_analyze,
)
from ai_server.schemas import AnalyzeResponse


class FakeResponse:
    def __init__(self, parsed):
        self.parsed = parsed


class FakeModels:
    """실제 client.aio.models.generate_content 자리에 들어가는 가짜.

    responses 리스트를 순서대로 소비한다. 항목이 Exception이면 raise,
    AnalyzeResponse면 FakeResponse로 감싸 반환한다."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.call_count = 0

    async def generate_content(self, **kwargs):
        self.call_count += 1
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeResponse(parsed=item)


class FakeAio:
    def __init__(self, responses):
        self.models = FakeModels(responses)


class FakeClient:
    def __init__(self, responses):
        self.aio = FakeAio(responses)


def make_client_error(status_code: int) -> errors.ClientError:
    """실제 google.genai.errors.ClientError 인스턴스를 생성한다 (429 판별 테스트용)."""
    resp = requests.Response()
    resp.status_code = status_code
    resp._content = (
        b'{"error": {"code": %d, "message": "boom", "status": "RESOURCE_EXHAUSTED"}}'
        % status_code
    )
    return errors.ClientError(status_code, resp)


EMPTY = AnalyzeResponse(candidates=[])


@pytest.mark.asyncio
async def test_succeeds_on_first_try():
    client = FakeClient([EMPTY])
    result = await call_gemini_analyze(client, "패턴 요약")
    assert result == EMPTY
    assert client.aio.models.call_count == 1


@pytest.mark.asyncio
async def test_retries_once_then_succeeds():
    client = FakeClient([RuntimeError("일시적 오류"), EMPTY])
    result = await call_gemini_analyze(client, "패턴 요약")
    assert result == EMPTY
    assert client.aio.models.call_count == 2


@pytest.mark.asyncio
async def test_fails_after_two_attempts():
    client = FakeClient([RuntimeError("오류1"), RuntimeError("오류2")])
    with pytest.raises(GeminiCallFailed):
        await call_gemini_analyze(client, "패턴 요약")
    assert client.aio.models.call_count == 2


@pytest.mark.asyncio
async def test_raises_when_response_not_parsed():
    # 스키마 강제에도 불구하고 Gemini가 malformed 응답을 주는 경우
    client = FakeClient([None, None])
    with pytest.raises(GeminiCallFailed):
        await call_gemini_analyze(client, "패턴 요약")


@pytest.mark.asyncio
async def test_raises_quota_exceeded_on_429_without_retry():
    # 실제 google-genai SDK가 던지는 ClientError(429)는 GeminiQuotaExceeded로
    # 구분되고, 재시도 없이 즉시 실패한다 (RpdCounter가 대부분 사전 차단하는
    # 희귀 레이스 컨디션이므로 재시도해도 성공 가능성이 낮음).
    client = FakeClient([make_client_error(429), EMPTY])
    with pytest.raises(GeminiQuotaExceeded):
        await call_gemini_analyze(client, "패턴 요약")
    assert client.aio.models.call_count == 1


@pytest.mark.asyncio
async def test_non_429_client_error_still_retries():
    # 429가 아닌 ClientError(예: 400)는 일반 실패 경로를 타고 재시도한다.
    client = FakeClient([make_client_error(400), EMPTY])
    result = await call_gemini_analyze(client, "패턴 요약")
    assert result == EMPTY
    assert client.aio.models.call_count == 2
