from typing import Literal, Union
from pydantic import BaseModel, Field


class HookCandidate(BaseModel):
    type: Literal["hook"] = "hook"
    event: str
    matcher: str
    command: str
    reason: str
    confidence: Literal["low", "medium", "high"]


class ClaudeMdCandidate(BaseModel):
    type: Literal["claude_md"] = "claude_md"
    suggested_text: str
    reason: str
    confidence: Literal["low", "medium", "high"]


Candidate = Union[HookCandidate, ClaudeMdCandidate]


class AnalyzeRequest(BaseModel):
    pattern_summary: str = Field(..., min_length=1)


class AnalyzeResponse(BaseModel):
    candidates: list[Candidate]


class AnalyzeEndpointResponse(BaseModel):
    """`/analyze` 엔드포인트의 실제 HTTP 응답 스키마 (Task 5에서 사용).

    AnalyzeResponse와 별도 타입인 이유: AnalyzeResponse는 Gemini의
    response_schema로도 쓰이는데, remaining_rpd는 Gemini가 알 수 없는
    값이라 그 스키마에 넣으면 Gemini가 값을 지어내게 된다.
    """

    candidates: list[Candidate]
    remaining_rpd: int


class EmbedRequest(BaseModel):
    text: str = Field(..., min_length=1)


class EmbedResponse(BaseModel):
    vector: list[float]
