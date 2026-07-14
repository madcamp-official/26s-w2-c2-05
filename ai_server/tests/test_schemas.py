import pytest
from pydantic import ValidationError

from ai_server.schemas import (
    AnalyzeResponse,
    HookCandidate,
    ClaudeMdCandidate,
    OnboardingRequest,
    OnboardingResponse,
)


def test_analyze_response_holds_mixed_candidates():
    resp = AnalyzeResponse(
        candidates=[
            HookCandidate(
                type="hook",
                event="PostToolUse",
                matcher="Edit",
                command="npm test",
                reason="테스트 파일을 수정할 때마다 항상 npm test를 실행했습니다.",
                confidence="high",
            ),
            ClaudeMdCandidate(
                type="claude_md",
                suggested_text="들여쓰기는 탭 대신 스페이스를 사용합니다.",
                reason="탭 대신 스페이스를 써달라고 여러 번 다시 알려주셨습니다.",
                confidence="medium",
            ),
        ]
    )
    assert resp.candidates[0].type == "hook"
    assert resp.candidates[1].type == "claude_md"

    # 직렬화 후 역직렬화해도 Union(pydantic v2 smart mode, type이 필수
    # Literal이라 구분 가능)이 올바르게 복원되는지 확인
    dumped = resp.model_dump_json()
    restored = AnalyzeResponse.model_validate_json(dumped)
    assert restored.candidates[0].command == "npm test"
    assert restored.candidates[1].suggested_text.startswith("들여쓰기")


def test_empty_candidates_is_valid():
    resp = AnalyzeResponse(candidates=[])
    assert resp.candidates == []


def test_analyze_endpoint_response_carries_remaining_rpd():
    from ai_server.schemas import AnalyzeEndpointResponse

    resp = AnalyzeEndpointResponse(candidates=[], remaining_rpd=19)
    assert resp.remaining_rpd == 19
    assert resp.candidates == []


def test_onboarding_request_holds_selected_fields():
    req = OnboardingRequest(
        principles=["tdd", "conventional_commits"],
        tech_stack="Python, FastAPI",
        team_or_individual="team",
        indent_style="spaces",
    )
    assert req.custom_requirements == ""

    dumped = req.model_dump_json()
    restored = OnboardingRequest.model_validate_json(dumped)
    assert restored.principles == ["tdd", "conventional_commits"]
    assert restored.tech_stack == "Python, FastAPI"
    assert restored.team_or_individual == "team"
    assert restored.indent_style == "spaces"


def test_onboarding_request_rejects_invalid_literal():
    with pytest.raises(ValidationError):
        OnboardingRequest(
            principles=[],
            tech_stack="Python",
            team_or_individual="solo",
            indent_style="spaces",
        )


def test_onboarding_response_holds_markdown_text():
    resp = OnboardingResponse(base_claude_md="# CLAUDE.md\n\n- 스페이스로 들여쓰기")
    dumped = resp.model_dump_json()
    restored = OnboardingResponse.model_validate_json(dumped)
    assert restored.base_claude_md.startswith("# CLAUDE.md")


def test_skill_recommendation_round_trips():
    from ai_server.schemas import SkillRecommendation

    rec = SkillRecommendation(
        type="skill",
        skill_name="run-migrations",
        skill_description="마이그레이션 후 시드와 재시작을 순서대로 진행한다",
        suggested_steps="1. migrate 실행\n2. seed 실행\n3. 서버 재시작",
        reason="매번 이 순서로 실행하셨어요.",
        confidence="high",
    )
    dumped = rec.model_dump_json()
    restored = SkillRecommendation.model_validate_json(dumped)
    assert restored.skill_name == "run-migrations"
    assert restored.type == "skill"


def test_analyze_response_holds_skill_candidate():
    from ai_server.schemas import AnalyzeResponse, SkillRecommendation

    resp = AnalyzeResponse(
        candidates=[
            SkillRecommendation(
                type="skill",
                skill_name="run-migrations",
                skill_description="설명",
                suggested_steps="단계",
                reason="이유",
                confidence="medium",
            )
        ]
    )
    assert resp.candidates[0].type == "skill"


def test_gemini_analyze_schema_accepts_skill_candidates():
    from ai_server.schemas import GeminiAnalyzeSchema, GeminiSkillCandidate

    schema = GeminiAnalyzeSchema(
        hook_candidates=[],
        claude_md_candidates=[],
        skill_candidates=[
            GeminiSkillCandidate(
                skill_name="run-migrations",
                skill_description="설명",
                suggested_steps="단계",
                reason="이유",
                confidence="high",
            )
        ],
    )
    assert schema.skill_candidates[0].skill_name == "run-migrations"
