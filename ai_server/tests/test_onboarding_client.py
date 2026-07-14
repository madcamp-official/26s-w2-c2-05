import pytest
import requests
from google.genai import errors

from ai_server.gemini_client import GeminiCallFailed, GeminiQuotaExceeded
from ai_server.onboarding_client import call_gemini_onboarding
from ai_server.schemas import OnboardingRequest, OnboardingResponse
from ai_server.tests.fakes import FakeClient


class FakeResponse:
    def __init__(self, parsed):
        self.parsed = parsed


class FakeModels:
    """실제 client.aio.models.generate_content 자리에 들어가는 가짜.

    responses 리스트를 순서대로 소비한다. 항목이 Exception이면 raise,
    OnboardingResponse면 FakeResponse로 감싸 반환한다 (response.parsed 자리)."""

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


REQ = OnboardingRequest(
    principles=["tdd"],
    tech_stack="Python, FastAPI",
    team_or_individual="team",
    indent_style="spaces",
)
EMPTY_ONBOARDING_RESPONSE = OnboardingResponse(base_claude_md="# CLAUDE.md")


@pytest.mark.asyncio
async def test_succeeds_on_first_try():
    client = FakeClient(FakeModels([EMPTY_ONBOARDING_RESPONSE]))
    result = await call_gemini_onboarding(client, REQ)
    assert result == EMPTY_ONBOARDING_RESPONSE
    assert client.aio.models.call_count == 1


@pytest.mark.asyncio
async def test_retries_once_then_succeeds():
    client = FakeClient(FakeModels([RuntimeError("일시적 오류"), EMPTY_ONBOARDING_RESPONSE]))
    result = await call_gemini_onboarding(client, REQ)
    assert result == EMPTY_ONBOARDING_RESPONSE
    assert client.aio.models.call_count == 2


@pytest.mark.asyncio
async def test_fails_after_two_attempts():
    client = FakeClient(FakeModels([RuntimeError("오류1"), RuntimeError("오류2")]))
    with pytest.raises(GeminiCallFailed):
        await call_gemini_onboarding(client, REQ)
    assert client.aio.models.call_count == 2


@pytest.mark.asyncio
async def test_raises_when_response_not_parsed():
    client = FakeClient(FakeModels([None, None]))
    with pytest.raises(GeminiCallFailed):
        await call_gemini_onboarding(client, REQ)


@pytest.mark.asyncio
async def test_raises_quota_exceeded_on_429_without_retry():
    client = FakeClient(FakeModels([make_client_error(429), EMPTY_ONBOARDING_RESPONSE]))
    with pytest.raises(GeminiQuotaExceeded):
        await call_gemini_onboarding(client, REQ)
    assert client.aio.models.call_count == 1


@pytest.mark.asyncio
async def test_non_429_client_error_still_retries():
    client = FakeClient(FakeModels([make_client_error(400), EMPTY_ONBOARDING_RESPONSE]))
    result = await call_gemini_onboarding(client, REQ)
    assert result == EMPTY_ONBOARDING_RESPONSE
    assert client.aio.models.call_count == 2
