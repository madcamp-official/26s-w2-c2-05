from ai_server.schemas import (
    AnalyzeResponse,
    HookCandidate,
    ClaudeMdCandidate,
)


def test_analyze_response_holds_mixed_candidates():
    resp = AnalyzeResponse(
        candidates=[
            HookCandidate(
                event="PostToolUse",
                matcher="Edit",
                command="npm test",
                reason="테스트 파일을 수정할 때마다 항상 npm test를 실행했습니다.",
                confidence="high",
            ),
            ClaudeMdCandidate(
                suggested_text="들여쓰기는 탭 대신 스페이스를 사용합니다.",
                reason="탭 대신 스페이스를 써달라고 여러 번 다시 알려주셨습니다.",
                confidence="medium",
            ),
        ]
    )
    assert resp.candidates[0].type == "hook"
    assert resp.candidates[1].type == "claude_md"

    # 직렬화 후 역직렬화해도 discriminated union이 올바르게 복원되는지 확인
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
