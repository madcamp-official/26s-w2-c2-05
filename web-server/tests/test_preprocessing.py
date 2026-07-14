import importlib
import json

preprocessing = importlib.import_module("web-server.preprocessing")
extract_pattern_summary = preprocessing.extract_pattern_summary


def _line(event: dict) -> str:
    return json.dumps(event, ensure_ascii=False)


def _assistant_bash_event(command: str) -> dict:
    # 실제 Claude Code 세션 JSONL 구조 (2026-07-13, 실제 세션 파일로 확인):
    # 최상위 type은 "assistant"이고, tool_use는 message.content[] 안에 중첩됨.
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_test",
                    "name": "Bash",
                    "input": {"command": command},
                }
            ],
        },
    }


def test_extracts_repeated_bash_command():
    events = [_assistant_bash_event("npm test") for _ in range(4)]
    summary = extract_pattern_summary("\n".join(_line(e) for e in events))
    assert summary is not None
    assert "npm test" in summary
    assert "4번" in summary


def test_ignores_non_bash_tool_use():
    events = [
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_test",
                        "name": "Read",
                        "input": {"file_path": "/a.py"},
                    }
                ],
            },
        }
        for _ in range(4)
    ]
    summary = extract_pattern_summary("\n".join(_line(e) for e in events))
    assert summary is None


def test_extracts_repeated_user_correction():
    events = [
        {"type": "user", "message": {"role": "user", "content": "탭 말고 스페이스 써주세요"}}
        for _ in range(3)
    ]
    summary = extract_pattern_summary("\n".join(_line(e) for e in events))
    assert summary is not None
    assert "스페이스" in summary


def test_extracts_repeated_user_correction_when_content_is_block_list():
    # 실제 세션에선 user content가 문자열이 아니라 {"type": "text", "text": ...}
    # 블록 리스트인 경우도 많음 (2026-07-13 실측)
    events = [
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": "탭 말고 스페이스 써주세요"}],
            },
        }
        for _ in range(3)
    ]
    summary = extract_pattern_summary("\n".join(_line(e) for e in events))
    assert summary is not None
    assert "스페이스" in summary


def test_ignores_patterns_under_threshold():
    events = [_assistant_bash_event("ls") for _ in range(2)]
    summary = extract_pattern_summary("\n".join(_line(e) for e in events))
    assert summary is None


def test_ignores_malformed_lines():
    summary = extract_pattern_summary("not valid json\n{}\n")
    assert summary is None


def test_extracts_sequence_with_gap_between_steps():
    commands = ["migrate", "other", "seed", "migrate", "seed"]
    events = [_assistant_bash_event(c) for c in commands]
    summary = extract_pattern_summary("\n".join(_line(e) for e in events))
    assert summary is not None
    assert '"migrate" → "seed" 순서로 2번 반복 실행함' in summary


def test_sequence_below_threshold_not_extracted():
    events = [_assistant_bash_event(c) for c in ["migrate", "seed"]]
    summary = extract_pattern_summary("\n".join(_line(e) for e in events))
    assert summary is None


def test_sequence_extends_to_three_steps_and_drops_shorter_chain():
    events = []
    for _ in range(2):
        events.append(_assistant_bash_event("migrate"))
        events.append(_assistant_bash_event("seed"))
        events.append(_assistant_bash_event("restart"))
    summary = extract_pattern_summary("\n".join(_line(e) for e in events))
    assert summary is not None
    assert '"migrate" → "seed" → "restart" 순서로 2번 반복 실행함' in summary
    assert '"migrate" → "seed" 순서로' not in summary


def test_sequence_capped_at_four_steps():
    commands_cycle = ["a", "b", "c", "d", "e"]
    events = []
    for _ in range(2):
        for cmd in commands_cycle:
            events.append(_assistant_bash_event(cmd))
    summary = extract_pattern_summary("\n".join(_line(e) for e in events))
    assert summary is not None
    sequence_lines = [line for line in summary.splitlines() if "순서로" in line]
    assert sequence_lines
    for line in sequence_lines:
        assert line.count("→") <= 3
