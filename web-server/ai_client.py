import os

import httpx

AI_SERVER_URL = os.environ.get("AI_SERVER_URL", "http://localhost:8001")


class GeminiQuotaExceeded(Exception):
    pass


async def analyze(pattern_summary: str, client: httpx.AsyncClient | None = None) -> dict:
    owns_client = client is None
    client = client or httpx.AsyncClient(base_url=AI_SERVER_URL, timeout=20.0)
    try:
        resp = await client.post("/analyze", json={"pattern_summary": pattern_summary})
        if resp.status_code == 429:
            raise GeminiQuotaExceeded()
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


async def generate_base_claude_md(
    onboarding: dict, client: httpx.AsyncClient | None = None
) -> str:
    owns_client = client is None
    client = client or httpx.AsyncClient(base_url=AI_SERVER_URL, timeout=20.0)
    try:
        resp = await client.post("/generate-base-claude-md", json=onboarding)
        if resp.status_code == 429:
            raise GeminiQuotaExceeded()
        resp.raise_for_status()
        return resp.json()["base_claude_md"]
    finally:
        if owns_client:
            await client.aclose()
