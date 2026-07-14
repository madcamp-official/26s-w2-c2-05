import json
import re
from collections import Counter

# 3회 미만 반복은 노이즈로 간주하고 버린다 (DESIGN.md "판단 기준" 절)
REPEAT_THRESHOLD = 3
MIN_SEQUENCE_REPEATS = 2  # skill 후보는 hook/claude_md보다 낮은 임계값 (DESIGN.md 결정)
MAX_SEQUENCE_LENGTH = 4

_CORRECTION_KEYWORDS = ["아니", "말고", "대신", "하지 마", "다시"]


def extract_pattern_summary(jsonl_text: str) -> str | None:
    bash_commands: list[str] = []
    user_corrections: list[str] = []

    for line in jsonl_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        if event.get("type") == "assistant":
            bash_commands.extend(_extract_bash_commands(event))

        if event.get("type") == "user":
            text = _extract_user_text(event)
            if text and _looks_like_correction(text):
                user_corrections.append(text.strip())

    summary_lines: list[str] = []

    for command, count in Counter(bash_commands).most_common():
        if count >= REPEAT_THRESHOLD:
            summary_lines.append(f'- bash 커맨드 "{command}"를 {count}번 반복 실행함')

    for text, count in Counter(user_corrections).most_common():
        if count >= REPEAT_THRESHOLD:
            summary_lines.append(f'- 유저가 "{text}"라고 {count}번 다시 알려줌')

    for sequence, count in _extract_sequences(bash_commands):
        arrow_chain = " → ".join(f'"{s}"' for s in sequence)
        summary_lines.append(f"- {arrow_chain} 순서로 {count}번 반복 실행함")

    if not summary_lines:
        return None
    return "\n".join(summary_lines)


def _extract_bash_commands(event: dict) -> list[str]:
    # tool_use는 최상위 이벤트가 아니라 assistant 이벤트의 message.content[] 안에
    # 중첩되어 있다 (2026-07-13, 실제 세션 JSONL로 확인 — 애초 가정이 틀렸었음).
    content = event.get("message", {}).get("content", [])
    if not isinstance(content, list):
        return []
    commands = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "tool_use" and item.get("name") == "Bash":
            command = item.get("input", {}).get("command", "").strip()
            if command:
                commands.append(_normalize_command(command))
    return commands


def _normalize_command(command: str) -> str:
    return re.sub(r"\s+", " ", command).strip()


def _extract_user_text(event: dict) -> str:
    content = event.get("message", {}).get("content", "")
    if isinstance(content, list):
        parts = [c.get("text", "") for c in content if isinstance(c, dict)]
        return " ".join(parts)
    if isinstance(content, str):
        return content
    return ""


def _looks_like_correction(text: str) -> bool:
    return any(keyword in text for keyword in _CORRECTION_KEYWORDS)


def _count_gapped_matches(commands: list[str], sequence: tuple[str, ...]) -> int:
    """sequence가 commands 안에서 순서대로(중간에 다른 커맨드가 껴도 됨) 몇 번
    겹치지 않게(non-overlapping) 나타나는지 센다."""
    count = 0
    pointer = 0
    for command in commands:
        if command == sequence[pointer]:
            pointer += 1
            if pointer == len(sequence):
                count += 1
                pointer = 0
    return count


def _extract_sequences(commands: list[str]) -> list[tuple[tuple[str, ...], int]]:
    """반복되는 순서 시퀀스(2~4단계)를 찾는다. Apriori 방식: 2단계 쌍부터
    임계값을 넘는 것을 찾고, 통과한 시퀀스를 한 단계씩 확장 시도한다 —
    확장에 성공하면(임계값 유지) 더 짧은 버전은 버리고 가장 긴 체인만 남긴다."""
    distinct = list(dict.fromkeys(commands))  # 등장 순서 유지한 채 중복 제거

    candidates: dict[tuple[str, ...], int] = {}
    for a in distinct:
        for b in distinct:
            if a == b:
                continue
            count = _count_gapped_matches(commands, (a, b))
            if count >= MIN_SEQUENCE_REPEATS:
                candidates[(a, b)] = count

    accepted: dict[tuple[str, ...], int] = dict(candidates)
    frontier = candidates

    while frontier:
        next_frontier: dict[tuple[str, ...], int] = {}
        for seq in frontier:
            if len(seq) >= MAX_SEQUENCE_LENGTH:
                continue
            for extra in distinct:
                if extra in seq:
                    continue
                extended = seq + (extra,)
                count = _count_gapped_matches(commands, extended)
                if count >= MIN_SEQUENCE_REPEATS:
                    next_frontier[extended] = count
                    accepted[extended] = count
                    accepted.pop(seq, None)
        frontier = next_frontier

    return sorted(accepted.items(), key=lambda item: (-len(item[0]), -item[1]))
