import json
import re
from collections import Counter

# 3회 미만 반복은 노이즈로 간주하고 버린다 (DESIGN.md "판단 기준" 절)
REPEAT_THRESHOLD = 3

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
