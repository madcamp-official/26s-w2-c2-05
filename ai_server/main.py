import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException
from google import genai

from .schemas import (
    AnalyzeRequest,
    AnalyzeEndpointResponse,
    EmbedRequest,
    EmbedResponse,
    OnboardingRequest,
    OnboardingResponse,
    RemainingRpdResponse,
)
from .gemini_client import call_gemini_analyze, GeminiCallFailed, GeminiQuotaExceeded
from .embed_client import call_gemini_embed
from .onboarding_client import call_gemini_onboarding
from .rate_limit import gemini_analyze_rpd_counter

load_dotenv(Path(__file__).parent / ".env")

app = FastAPI()

RPD_EXHAUSTED_DETAIL = "오늘의 요청 한도를 모두 사용했습니다"


@lru_cache()
def get_gemini_client() -> genai.Client:
    # 요청마다 새로 만들지 않고 한 번만 만들어서 재사용 — genai.Client는
    # 내부적으로 HTTP 커넥션 풀을 들고 있어 매번 새로 만들면 낭비다.
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


@app.post("/analyze", response_model=AnalyzeEndpointResponse)
async def analyze(
    req: AnalyzeRequest, client=Depends(get_gemini_client)
) -> AnalyzeEndpointResponse:
    # consume()은 호출 1건당 1번만 차감한다 — call_gemini_analyze 내부에서
    # 재시도가 일어나면 로컬 카운터 기준으로는 실제 Gemini 요청 수를 과소
    # 계산하게 되지만(예: 1회 재시도 시 실제로는 Gemini에 2번 요청), 최종
    # 실패든 성공이든 이미 Gemini의 서버 쪽 쿼터는 그만큼 소모된 뒤라 여기서
    # 환불하지 않는 게 맞다 — 환불하면 우리 로컬 카운터가 실제 계정 한도보다
    # 더 여유 있다고 착각해 초과 요청을 허용할 위험이 있다(2026-07-13, 최종
    # 브랜치 리뷰에서 확인).
    if not gemini_analyze_rpd_counter.consume():
        raise HTTPException(status_code=429, detail=RPD_EXHAUSTED_DETAIL)
    try:
        result = await call_gemini_analyze(client, req.pattern_summary)
    except GeminiQuotaExceeded:
        raise HTTPException(status_code=429, detail=RPD_EXHAUSTED_DETAIL)
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


@app.post("/generate-base-claude-md", response_model=OnboardingResponse)
async def generate_base_claude_md(
    req: OnboardingRequest, client=Depends(get_gemini_client)
) -> OnboardingResponse:
    # 온보딩도 생성 모델(analyze와 동일 쿼터)을 쓰므로 같은 RPD 카운터를 소비한다.
    if not gemini_analyze_rpd_counter.consume():
        raise HTTPException(status_code=429, detail=RPD_EXHAUSTED_DETAIL)
    try:
        return await call_gemini_onboarding(client, req)
    except GeminiQuotaExceeded:
        raise HTTPException(status_code=429, detail=RPD_EXHAUSTED_DETAIL)
    except GeminiCallFailed:
        raise HTTPException(status_code=503, detail="잠시 후 다시 시도해주세요")


@app.get("/remaining-rpd", response_model=RemainingRpdResponse)
def get_remaining_rpd() -> RemainingRpdResponse:
    # 소모(consume) 없이 현재 남은 일일 한도만 조회 — 프론트에 서비스 전체
    # 남은 요청 수를 보여주기 위한 읽기 전용 엔드포인트.
    return RemainingRpdResponse(remaining_rpd=gemini_analyze_rpd_counter.remaining())
