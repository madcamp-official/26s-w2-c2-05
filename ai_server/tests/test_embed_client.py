import pytest
from ai_server.embed_client import call_gemini_embed
from ai_server.gemini_client import GeminiCallFailed


class FakeEmbedding:
    def __init__(self, values):
        self.values = values


class FakeEmbedResponse:
    def __init__(self, values):
        self.embeddings = [FakeEmbedding(values)]


class FakeModels:
    def __init__(self, result):
        self._result = result
        self.call_count = 0

    async def embed_content(self, **kwargs):
        self.call_count += 1
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


class FakeAio:
    def __init__(self, result):
        self.models = FakeModels(result)


class FakeClient:
    def __init__(self, result):
        self.aio = FakeAio(result)


@pytest.mark.asyncio
async def test_returns_vector_on_success():
    client = FakeClient(FakeEmbedResponse([0.1, 0.2, 0.3]))
    result = await call_gemini_embed(client, "스페이스로 들여쓰기 통일")
    assert result.vector == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_raises_gemini_call_failed_on_error():
    client = FakeClient(RuntimeError("네트워크 오류"))
    with pytest.raises(GeminiCallFailed):
        await call_gemini_embed(client, "스페이스로 들여쓰기 통일")
