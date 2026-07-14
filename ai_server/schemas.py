from typing import Literal, Union
from pydantic import BaseModel, Field


class HookCandidate(BaseModel):
    type: Literal["hook"]
    event: str
    matcher: str
    command: str
    reason: str
    confidence: Literal["low", "medium", "high"]


class ClaudeMdCandidate(BaseModel):
    type: Literal["claude_md"]
    suggested_text: str
    reason: str
    confidence: Literal["low", "medium", "high"]


class SkillRecommendation(BaseModel):
    type: Literal["skill"]
    skill_name: str
    skill_description: str
    suggested_steps: str
    reason: str
    confidence: Literal["low", "medium", "high"]


Candidate = Union[HookCandidate, ClaudeMdCandidate, SkillRecommendation]


class AnalyzeRequest(BaseModel):
    pattern_summary: str = Field(..., min_length=1)


class AnalyzeResponse(BaseModel):
    """`call_gemini_analyze`의 반환 타입 (내부/`AnalyzeEndpointResponse` 조립용).

    Gemini의 `response_schema`로 직접 쓰이지 않는다 — `Union`(anyOf)을
    Gemini 구조화 출력이 지원하지 않아(2026-07-13 T-08 실측 중 발견) 실제
    Gemini 요청에는 `GeminiAnalyzeSchema`를 쓰고, `call_gemini_analyze`가
    그 결과를 이 타입으로 변환해서 반환한다.
    """

    candidates: list[Candidate]


class GeminiHookCandidate(BaseModel):
    """Gemini `response_schema` 전용 — `HookCandidate`에서 `type`을 뺀 버전.

    `hook_candidates` 리스트 소속 자체가 타입을 나타내므로 `type` 필드가
    필요 없다. (`type: Literal["hook"]`처럼 값이 하나뿐인 Literal은 JSON
    스키마의 `const`로 변환되는데, Gemini가 `const`를 지원하지 않아
    2026-07-13 실측 중 제거함.)
    """

    event: str
    matcher: str
    command: str
    reason: str
    confidence: Literal["low", "medium", "high"]


class GeminiClaudeMdCandidate(BaseModel):
    suggested_text: str
    reason: str
    confidence: Literal["low", "medium", "high"]


class GeminiSkillCandidate(BaseModel):
    """GeminiHookCandidate/GeminiClaudeMdCandidate와 동일한 이유로 type 없음
    (skill_candidates 리스트 소속 자체가 타입을 나타냄)."""

    skill_name: str
    skill_description: str
    suggested_steps: str
    reason: str
    confidence: Literal["low", "medium", "high"]


class GeminiAnalyzeSchema(BaseModel):
    """Gemini `generate_content`의 `response_schema`로 직접 전달되는 스키마.

    `AnalyzeResponse`(Union 기반)를 그대로 쓰면 두 가지 이유로 실패한다
    (2026-07-13, 실제 API 호출로 확인):
    1. `Union[HookCandidate, ClaudeMdCandidate]`가 JSON 스키마의 `anyOf`로
       변환되는데, Gemini 구조화 출력은 `anyOf`를 지원하지 않는다
       (`ValueError: AnyOf is not supported in the response schema`).
    2. 각 후보의 `type: Literal[...]` 단일값 필드가 `const`로 변환되는데,
       이것도 지원 안 됨(`Extra inputs are not permitted` — `const`가
       `google.genai.types.Schema`에 없는 필드라 검증 실패).

    그래서 hook/claude_md를 애초에 두 개의 리스트로 나눠 요청하고,
    `call_gemini_analyze`가 응답을 받은 뒤 `type`을 채워 `AnalyzeResponse`
    (Union 기반)로 조립해서 반환한다.
    """

    hook_candidates: list[GeminiHookCandidate]
    claude_md_candidates: list[GeminiClaudeMdCandidate]
    skill_candidates: list[GeminiSkillCandidate]


class AnalyzeEndpointResponse(BaseModel):
    """`/analyze` 엔드포인트의 실제 HTTP 응답 스키마 (Task 5에서 사용).

    AnalyzeResponse와 별도 타입인 이유: remaining_rpd는 Gemini가 알 수
    없는 값이라(우리 쪽 RPD 카운터에서 가져옴) Gemini에 보내는 스키마에는
    넣을 수 없다.
    """

    candidates: list[Candidate]
    remaining_rpd: int


class EmbedRequest(BaseModel):
    text: str = Field(..., min_length=1)


class EmbedResponse(BaseModel):
    vector: list[float]


class OnboardingRequest(BaseModel):
    principles: list[str]
    tech_stack: str
    team_or_individual: Literal["team", "individual"]
    indent_style: Literal["tabs", "spaces"]
    custom_requirements: str = ""


class OnboardingResponse(BaseModel):
    base_claude_md: str
