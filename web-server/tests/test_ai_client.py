import importlib

import pytest
import httpx

ai_client = importlib.import_module("web-server.ai_client")
GeminiQuotaExceeded = ai_client.GeminiQuotaExceeded


@pytest.mark.asyncio
async def test_analyze_returns_parsed_json():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/analyze"
        return httpx.Response(200, json={"candidates": [], "remaining_rpd": 499})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://test"
    ) as fake_client:
        result = await ai_client.analyze("패턴 요약", client=fake_client)

    assert result == {"candidates": [], "remaining_rpd": 499}


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
async def test_analyze_raises_quota_exceeded_on_429():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"detail": "오늘의 요청 한도를 모두 사용했습니다"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://test"
    ) as fake_client:
        with pytest.raises(GeminiQuotaExceeded):
            await ai_client.analyze("패턴 요약", client=fake_client)


@pytest.mark.asyncio
async def test_analyze_raises_http_error_on_503():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"detail": "잠시 후 다시 시도해주세요"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://test"
    ) as fake_client:
        with pytest.raises(httpx.HTTPStatusError):
            await ai_client.analyze("패턴 요약", client=fake_client)


ONBOARDING_PAYLOAD = {
    "principles": ["tdd"],
    "tech_stack": "Python, FastAPI",
    "team_or_individual": "team",
    "indent_style": "spaces",
    "custom_requirements": "",
}


@pytest.mark.asyncio
async def test_generate_base_claude_md_returns_text():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/generate-base-claude-md"
        return httpx.Response(200, json={"base_claude_md": "# CLAUDE.md\n\n- 스페이스 사용"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://test"
    ) as fake_client:
        result = await ai_client.generate_base_claude_md(ONBOARDING_PAYLOAD, client=fake_client)

    assert result == "# CLAUDE.md\n\n- 스페이스 사용"


@pytest.mark.asyncio
async def test_generate_base_claude_md_raises_quota_exceeded_on_429():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"detail": "오늘의 요청 한도를 모두 사용했습니다"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://test"
    ) as fake_client:
        with pytest.raises(GeminiQuotaExceeded):
            await ai_client.generate_base_claude_md(ONBOARDING_PAYLOAD, client=fake_client)


@pytest.mark.asyncio
async def test_generate_base_claude_md_raises_http_error_on_503():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"detail": "잠시 후 다시 시도해주세요"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://test"
    ) as fake_client:
        with pytest.raises(httpx.HTTPStatusError):
            await ai_client.generate_base_claude_md(ONBOARDING_PAYLOAD, client=fake_client)
