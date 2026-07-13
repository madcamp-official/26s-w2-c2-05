import os

from fastapi import FastAPI, Depends, HTTPException
from google import genai

from .schemas import AnalyzeRequest, AnalyzeEndpointResponse, EmbedRequest, EmbedResponse
from .gemini_client import call_gemini_analyze, GeminiCallFailed, GeminiQuotaExceeded
from .embed_client import call_gemini_embed
from .rate_limit import gemini_analyze_rpd_counter

app = FastAPI()


def get_gemini_client() -> genai.Client:
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


@app.post("/analyze", response_model=AnalyzeEndpointResponse)
async def analyze(
    req: AnalyzeRequest, client=Depends(get_gemini_client)
) -> AnalyzeEndpointResponse:
    if not gemini_analyze_rpd_counter.consume():
        raise HTTPException(status_code=429, detail="오늘의 요청 한도를 모두 사용했습니다")
    try:
        result = await call_gemini_analyze(client, req.pattern_summary)
    except GeminiQuotaExceeded:
        raise HTTPException(status_code=429, detail="오늘의 요청 한도를 모두 사용했습니다")
    except GeminiCallFailed:
        raise HTTPException(status_code=503, detail="잠시 후 다시 시도해주세요")
    return AnalyzeEndpointResponse(
        candidates=result.candidates,
        remaining_rpd=gemini_analyze_rpd_counter.remaining(),
    )


@app.post("/embed", response_model=EmbedResponse)
async def embed(req: EmbedRequest, client=Depends(get_gemini_client)) -> EmbedResponse:
    try:
        return await call_gemini_embed(client, req.text)
    except GeminiCallFailed:
        raise HTTPException(status_code=503, detail="잠시 후 다시 시도해주세요")
