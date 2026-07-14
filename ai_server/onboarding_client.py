import asyncio

from google.genai import errors

from .gemini_client import GEMINI_MODEL, GEMINI_TIMEOUT_SECONDS, GeminiCallFailed, GeminiQuotaExceeded
from .rate_limit import gemini_analyze_limiter
from .schemas import OnboardingRequest, OnboardingResponse

SYSTEM_INSTRUCTION = """너는 새 프로젝트의 CLAUDE.md(Claude Code 프로젝트 규칙 파일)
초안을 만들어주는 어시스턴트다. 입력으로 개발 원칙 목록(원칙 키), 기술 스택,
팀/개인 여부, 들여쓰기 스타일, 자유 요구사항을 받는다.

출력 규칙:
- base_claude_md는 순수 markdown 텍스트 하나로만 작성해라. "다음은 요청하신
  CLAUDE.md입니다" 같은 안내 문구나 서론/결론을 붙이지 마라.
- 각 원칙 키(예: "tdd", "conventional_commits")를 그대로 나열하지 말고, 그
  원칙이 실제로 뜻하는 구체적인 규칙 문장으로 풀어써라.
- 각 규칙은 짧고 담백한 지시문으로만 쓰고, "왜 이 규칙인지"는 설명하지 마라
  (AnalyzeResponse의 reason 필드와 달리 이 문서엔 근거 설명이 필요 없다).
- team_or_individual이 "team"이면 "우리는 ~한다"처럼 팀 합의 규칙으로,
  "individual"이면 "나는 ~한다"처럼 개인 규칙으로 톤을 맞춰라.
- indent_style은 반드시 명시적인 규칙 한 줄로 포함해라(탭 또는 스페이스).
- custom_requirements가 비어 있으면 그 항목을 위한 빈 섹션이나 자리표시자를
  만들지 마라. 비어 있지 않으면 다른 규칙과 자연스럽게 섞어 넣어라.
- {tech_stack}, {project_name} 같은 존재하지 않는 템플릿 문법을 지어내지 마라.
- 전체 출력은 반드시 한국어로 작성해라 (영어로 쓰지 마라)."""


def _build_contents(req: OnboardingRequest) -> str:
    return (
        "다음 온보딩 입력으로 CLAUDE.md 초안을 작성해줘:\n"
        f"- 선택된 개발 원칙: {', '.join(req.principles) if req.principles else '없음'}\n"
        f"- 기술 스택: {req.tech_stack}\n"
        f"- 팀/개인: {req.team_or_individual}\n"
        f"- 들여쓰기 스타일: {req.indent_style}\n"
        f"- 추가 요구사항: {req.custom_requirements or '없음'}"
    )


async def call_gemini_onboarding(client, req: OnboardingRequest) -> OnboardingResponse:
    """client는 google.genai.Client 인스턴스 (또는 테스트용 가짜).
    client.aio.models.generate_content(**kwargs) -> awaitable[response]
    response.parsed 가 response_schema(OnboardingResponse)로 지정한
    pydantic 인스턴스여야 한다.
    """
    last_error: Exception | None = None
    async with gemini_analyze_limiter:
        for attempt in range(2):  # 최초 시도 + 재시도 1회
            try:
                response = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=GEMINI_MODEL,
                        contents=_build_contents(req),
                        config={
                            "system_instruction": SYSTEM_INSTRUCTION,
                            "response_mime_type": "application/json",
                            "response_schema": OnboardingResponse,
                        },
                    ),
                    timeout=GEMINI_TIMEOUT_SECONDS,
                )
                if response.parsed is None:
                    raise GeminiCallFailed("Gemini가 스키마에 맞는 응답을 생성하지 못함")
                return response.parsed
            except errors.ClientError as e:
                if e.code == 429:
                    raise GeminiQuotaExceeded(str(e)) from e
                last_error = e  # 429가 아닌 4xx는 일반 재시도 대상
            except Exception as e:  # 타임아웃/malformed 등을 광범위하게 재시도 대상으로 취급
                last_error = e
        raise GeminiCallFailed(str(last_error)) from last_error
