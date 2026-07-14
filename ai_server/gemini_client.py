import asyncio

from google.genai import errors

from .rate_limit import gemini_analyze_limiter
from .schemas import (
    AnalyzeResponse,
    ClaudeMdCandidate,
    GeminiAnalyzeSchema,
    HookCandidate,
    SkillRecommendation,
)

# gemini-2.5-flash-lite는 2026-07-13 기준 신규 유저에게 더 이상 제공되지
# 않아(404 NOT_FOUND, T-08 실측 중 발견) 3.1 세대로 교체함. RPM/RPD도 더
# 여유롭다(RPM 10→15, RPD 20→500, AI Studio 대시보드 실측).
GEMINI_MODEL = "gemini-3.1-flash-lite"
GEMINI_TIMEOUT_SECONDS = 15

SYSTEM_INSTRUCTION = """너는 Claude Code 세션 로그에서 반복되는 행동 패턴을 보고,
그 사람에게 도움이 될 자동화 규칙(hook)이나 프로젝트 규칙(claude_md)을 제안하는
어시스턴트다. 결과는 비개발자도 이해할 수 있는 plain language로 설명해야 한다.
suggested_text와 reason은 항상 한국어로 작성해라 (영어로 쓰지 마라).

판단 기준:
- hook: 매번 결정론적으로 자동 실행돼야 하는 단일 트리거→단일 명령. 판단 불필요.
  예: ".ts 파일 수정 후 항상 npm test를 실행한다" → PostToolUse 이벤트, Edit
  matcher, "npm test" 커맨드.
- claude_md: 세션마다 컨텍스트로 스며들면 되는 단일 사실/선호.
  예: "탭 대신 스페이스를 쓴다" → CLAUDE.md에 넣을 한 줄 규칙.
- skill: 2단계 이상 이어지고, 중간에 판단/분기가 섞이는 반복 절차. "이 순서로
  이렇게 해야 한다"는 여러 문장으로 설명해야 하는 경우.
  예: "마이그레이션 실행 후 시드 갱신, 그다음 서버 재시작을 항상 이 순서로 한다"
  → skill_name은 kebab-case로 간결하게(예: "run-migrations"), skill_description은
  한 줄 요약, suggested_steps는 실행 순서를 번호 매긴 목록으로 markdown 작성.
  이 타입은 hook/claude_md보다 반복 기준이 낮아 2회 이상만 반복돼도 후보로
  삼아라(hook/claude_md는 3회 기준).

hook 후보의 event/matcher/command는 실제 Claude Code 설정 파일(settings.json)의
hooks 스키마를 정확히 따라야 한다 (틀리면 실제로 동작하지 않는 hook이 된다):
- event: 반드시 다음 중 하나만 써라 — PreToolUse, PostToolUse, Notification,
  UserPromptSubmit, Stop, SubagentStop. 이 목록에 없는 이름을 지어내지 마라.
- matcher: 파일 경로나 파일 확장자 패턴이 아니라 **도구 이름**에 매치되는
  정규식이다 (예: "Edit", "Write", "Bash", "MultiEdit"). ".ts 파일 수정"처럼
  파일 종류가 언급되면, 그 파일을 다루는 도구 이름(보통 Edit 또는 MultiEdit)을
  matcher로 써라 — 파일 확장자 필터링이 필요하면 그건 matcher가 아니라 command
  안에서 처리해라. "npm run build"처럼 실행된 커맨드 문자열 자체를 matcher에
  넣지 마라 — Bash 도구로 실행된 것이면 matcher는 "Bash"다.
- command: 그대로 실행 가능한 완전한 셸 커맨드여야 한다. `{file_path}` 같은
  존재하지 않는 템플릿 문법을 지어내지 마라 — 그런 값은 실제로 채워지지 않는다.

패턴이 3회 미만 반복된 것으로 보이면 후보로 만들지 마라. reason 필드에는 항상
"왜 이걸 추천하는지"를 유저의 실제 행동을 근거로 설명해라."""


class GeminiCallFailed(Exception):
    pass


class GeminiQuotaExceeded(GeminiCallFailed):
    """Gemini가 실제로 429(RESOURCE_EXHAUSTED)를 반환한 경우.

    RpdCounter(rate_limit.py)가 대부분의 쿼터 초과를 사전 차단하므로 이 경로는
    레이스 컨디션에서만 발생하는 희귀 케이스다. 429는 현재 RPM 윈도우가 아직
    풀리지 않았다는 뜻이라 같은 호출 안에서 즉시 재시도해도 성공 가능성이
    낮고, 오히려 다음 재시도가 분당 쿼터를 한 번 더 갉아먹으므로 재시도하지
    않고 즉시 실패시킨다(fail fast). google-genai==1.0.0의
    `google.genai.errors.ClientError`는 HTTP 상태코드를 `.code`에 담아 실어
    주므로 429를 다른 4xx/5xx/타임아웃/malformed 실패와 깔끔하게 구분할 수
    있다(Task 3 investigation, 2026-07-13).
    """

    pass


def _to_analyze_response(parsed: GeminiAnalyzeSchema) -> AnalyzeResponse:
    """Gemini가 hook/claude_md/skill로 나눠 응답한 리스트에 type을 채워 넣어
    AnalyzeResponse(Union 기반)로 조립한다. GeminiAnalyzeSchema 문서에
    설명한 대로, 리스트 소속 자체가 이미 타입을 나타내므로 여기서 채우면
    된다."""
    candidates = (
        [HookCandidate(type="hook", **h.model_dump()) for h in parsed.hook_candidates]
        + [
            ClaudeMdCandidate(type="claude_md", **c.model_dump())
            for c in parsed.claude_md_candidates
        ]
        + [
            SkillRecommendation(type="skill", **s.model_dump())
            for s in parsed.skill_candidates
        ]
    )
    return AnalyzeResponse(candidates=candidates)


async def call_gemini_analyze(client, pattern_summary: str) -> AnalyzeResponse:
    """client는 google.genai.Client 인스턴스 (또는 테스트용 가짜).
    client.aio.models.generate_content(**kwargs) -> awaitable[response]
    response.parsed 가 response_schema(GeminiAnalyzeSchema)로 지정한
    pydantic 인스턴스여야 한다.
    """
    last_error: Exception | None = None
    async with gemini_analyze_limiter:
        for attempt in range(2):  # 최초 시도 + 재시도 1회
            try:
                response = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=GEMINI_MODEL,
                        contents=f"다음은 전처리된 세션 로그 패턴입니다:\n{pattern_summary}",
                        config={
                            "system_instruction": SYSTEM_INSTRUCTION,
                            "response_mime_type": "application/json",
                            "response_schema": GeminiAnalyzeSchema,
                        },
                    ),
                    timeout=GEMINI_TIMEOUT_SECONDS,
                )
                if response.parsed is None:
                    raise GeminiCallFailed("Gemini가 스키마에 맞는 응답을 생성하지 못함")
                return _to_analyze_response(response.parsed)
            except errors.ClientError as e:
                if e.code == 429:
                    raise GeminiQuotaExceeded(str(e)) from e
                last_error = e  # 429가 아닌 4xx는 일반 재시도 대상
            except Exception as e:  # 타임아웃/malformed 등을 광범위하게 재시도 대상으로 취급
                last_error = e
        raise GeminiCallFailed(str(last_error)) from last_error
