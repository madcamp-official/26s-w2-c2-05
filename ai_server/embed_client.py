import asyncio

from .gemini_client import GeminiCallFailed, GEMINI_TIMEOUT_SECONDS
from .rate_limit import gemini_embed_limiter
from .schemas import EmbedResponse

EMBEDDING_MODEL = "gemini-embedding-001"


async def call_gemini_embed(client, text: str) -> EmbedResponse:
    """client.aio.models.embed_content(**kwargs) -> awaitable[response]
    response.embeddings[0].values 가 float 리스트여야 한다."""
    async with gemini_embed_limiter:
        try:
            response = await asyncio.wait_for(
                client.aio.models.embed_content(
                    model=EMBEDDING_MODEL,
                    contents=text,
                    config={"task_type": "CLUSTERING"},
                ),
                timeout=GEMINI_TIMEOUT_SECONDS,
            )
            return EmbedResponse(vector=response.embeddings[0].values)
        except Exception as e:
            raise GeminiCallFailed(str(e)) from e
