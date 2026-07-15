import importlib
import io
import json

from sqlmodel import select

from .conftest import auth_headers, make_user_and_token, models

ai_client = importlib.import_module("web-server.ai_client")


def _create_project(client, owner_token: str) -> str:
    resp = client.post(
        "/projects", json={"name": "test"}, headers=auth_headers(owner_token)
    )
    return resp.json()["id"]


def _jsonl_with_repeated_bash(command: str, times: int) -> bytes:
    # 실제 Claude Code 세션 JSONL 구조: tool_use는 최상위가 아니라
    # assistant 이벤트의 message.content[] 안에 중첩됨 (2026-07-13 확인)
    event = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "toolu_test", "name": "Bash", "input": {"command": command}}
            ],
        },
    }
    lines = [json.dumps(event) for _ in range(times)]
    return "\n".join(lines).encode("utf-8")


async def _fake_analyze(pattern_summary, client=None):
    return {
        "candidates": [
            {
                "type": "hook",
                "event": "PostToolUse",
                "matcher": "Bash",
                "command": "npm test",
                "reason": "테스트를 항상 직접 실행하셨어요.",
                "confidence": "high",
            }
        ],
        "remaining_rpd": 499,
    }


def test_upload_with_patterns_returns_personal_recommendation(client, db_session, monkeypatch):
    monkeypatch.setattr(ai_client, "analyze", _fake_analyze)
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)
    file_content = _jsonl_with_repeated_bash("npm test", 5)

    resp = client.post(
        f"/projects/{project_id}/sessions",
        files={"file": ("session.jsonl", io.BytesIO(file_content), "application/jsonl")},
        headers=auth_headers(owner_token),
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "processed"
    assert body["personal_recommendations"][0]["payload"]["command"] == "npm test"


def test_upload_with_no_patterns_skips_ai_call(client, db_session, monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("Gemini를 호출하면 안 됨")

    monkeypatch.setattr(ai_client, "analyze", fail_if_called)
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)
    file_content = _jsonl_with_repeated_bash("ls", 1)  # 임계값(3회) 미달

    resp = client.post(
        f"/projects/{project_id}/sessions",
        files={"file": ("session.jsonl", io.BytesIO(file_content), "application/jsonl")},
        headers=auth_headers(owner_token),
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "no_patterns"
    assert resp.json()["personal_recommendations"] == []


async def _fake_analyze_lint(pattern_summary, client=None):
    return {
        "candidates": [
            {
                "type": "hook",
                "event": "PostToolUse",
                "matcher": "Bash",
                "command": "npm lint",
                "reason": "린트를 항상 직접 실행하셨어요.",
                "confidence": "high",
            }
        ],
        "remaining_rpd": 499,
    }


def test_reupload_with_same_pattern_updates_existing_recommendation_not_duplicate(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(ai_client, "analyze", _fake_analyze)
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)
    file_content = _jsonl_with_repeated_bash("npm test", 5)

    client.post(
        f"/projects/{project_id}/sessions",
        files={"file": ("s1.jsonl", io.BytesIO(file_content), "application/jsonl")},
        headers=auth_headers(owner_token),
    )
    client.post(
        f"/projects/{project_id}/sessions",
        files={"file": ("s2.jsonl", io.BytesIO(file_content), "application/jsonl")},
        headers=auth_headers(owner_token),
    )

    # 세션 기록 자체는 재업로드해도 지워지지 않고 쌓인다 (히스토리 보존)
    sessions = db_session.exec(
        select(models.Session).where(
            models.Session.project_id == project_id, models.Session.user_id == owner.user_id
        )
    ).all()
    assert len(sessions) == 2

    # 같은 그룹으로 매칭되는 추천은 새로 추가되지 않고 기존 row가 갱신된다
    recs = db_session.exec(select(models.PersonalRecommendation)).all()
    assert len(recs) == 1
    assert recs[0].session_id == sessions[-1].id


def test_reupload_with_different_pattern_keeps_prior_unmatched_recommendation(
    client, db_session, monkeypatch
):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)
    file_content = _jsonl_with_repeated_bash("npm test", 5)

    monkeypatch.setattr(ai_client, "analyze", _fake_analyze)
    client.post(
        f"/projects/{project_id}/sessions",
        files={"file": ("s1.jsonl", io.BytesIO(file_content), "application/jsonl")},
        headers=auth_headers(owner_token),
    )

    monkeypatch.setattr(ai_client, "analyze", _fake_analyze_lint)
    client.post(
        f"/projects/{project_id}/sessions",
        files={"file": ("s2.jsonl", io.BytesIO(file_content), "application/jsonl")},
        headers=auth_headers(owner_token),
    )

    me_resp = client.get(
        f"/projects/{project_id}/recommendations/me", headers=auth_headers(owner_token)
    )
    commands = {r["payload"]["command"] for r in me_resp.json()}
    assert commands == {"npm test", "npm lint"}


def test_upload_propagates_429_when_quota_exceeded(client, db_session, monkeypatch):
    async def fake_analyze_quota_exceeded(pattern_summary, client=None):
        raise ai_client.GeminiQuotaExceeded()

    monkeypatch.setattr(ai_client, "analyze", fake_analyze_quota_exceeded)
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)
    file_content = _jsonl_with_repeated_bash("npm test", 5)

    resp = client.post(
        f"/projects/{project_id}/sessions",
        files={"file": ("session.jsonl", io.BytesIO(file_content), "application/jsonl")},
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 429


def test_second_member_upload_promotes_team_group(client, db_session, monkeypatch):
    monkeypatch.setattr(ai_client, "analyze", _fake_analyze)
    owner, owner_token = make_user_and_token(db_session, "owner")
    member, member_token = make_user_and_token(db_session, "member")
    project_id = _create_project(client, owner_token)
    client.post(
        f"/projects/{project_id}/invite",
        json={"username": member.username},
        headers=auth_headers(owner_token),
    )
    file_content = _jsonl_with_repeated_bash("npm test", 5)

    first_resp = client.post(
        f"/projects/{project_id}/sessions",
        files={"file": ("s1.jsonl", io.BytesIO(file_content), "application/jsonl")},
        headers=auth_headers(owner_token),
    )
    assert first_resp.json()["updated_team_groups"][0]["promoted"] is False

    second_resp = client.post(
        f"/projects/{project_id}/sessions",
        files={"file": ("s2.jsonl", io.BytesIO(file_content), "application/jsonl")},
        headers=auth_headers(member_token),
    )
    groups = second_resp.json()["updated_team_groups"]
    assert groups[0]["promoted"] is True
    assert groups[0]["affected_members"] == 2


def test_non_member_cannot_upload(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    outsider, outsider_token = make_user_and_token(db_session, "outsider")
    project_id = _create_project(client, owner_token)
    file_content = _jsonl_with_repeated_bash("npm test", 5)

    resp = client.post(
        f"/projects/{project_id}/sessions",
        files={"file": ("session.jsonl", io.BytesIO(file_content), "application/jsonl")},
        headers=auth_headers(outsider_token),
    )
    assert resp.status_code == 403


def test_team_recommendations_empty_before_promotion(client, db_session, monkeypatch):
    monkeypatch.setattr(ai_client, "analyze", _fake_analyze)
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)
    file_content = _jsonl_with_repeated_bash("npm test", 5)
    client.post(
        f"/projects/{project_id}/sessions",
        files={"file": ("s1.jsonl", io.BytesIO(file_content), "application/jsonl")},
        headers=auth_headers(owner_token),
    )

    resp = client.get(
        f"/projects/{project_id}/recommendations/team", headers=auth_headers(owner_token)
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_team_recommendations_shown_with_evidence_after_promotion(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(ai_client, "analyze", _fake_analyze)
    owner, owner_token = make_user_and_token(db_session, "owner")
    member, member_token = make_user_and_token(db_session, "member")
    project_id = _create_project(client, owner_token)
    client.post(
        f"/projects/{project_id}/invite",
        json={"username": member.username},
        headers=auth_headers(owner_token),
    )
    file_content = _jsonl_with_repeated_bash("npm test", 5)
    client.post(
        f"/projects/{project_id}/sessions",
        files={"file": ("s1.jsonl", io.BytesIO(file_content), "application/jsonl")},
        headers=auth_headers(owner_token),
    )
    client.post(
        f"/projects/{project_id}/sessions",
        files={"file": ("s2.jsonl", io.BytesIO(file_content), "application/jsonl")},
        headers=auth_headers(member_token),
    )

    resp = client.get(
        f"/projects/{project_id}/recommendations/team", headers=auth_headers(owner_token)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["affected_members"] == 2
    assert len(body[0]["evidence"]) == 2
    assert body[0]["event"] == "PostToolUse"
    assert body[0]["matcher"] == "Bash"


def test_get_my_recommendations_only_shows_own(client, db_session, monkeypatch):
    monkeypatch.setattr(ai_client, "analyze", _fake_analyze)
    owner, owner_token = make_user_and_token(db_session, "owner")
    member, member_token = make_user_and_token(db_session, "member")
    project_id = _create_project(client, owner_token)
    client.post(
        f"/projects/{project_id}/invite",
        json={"username": member.username},
        headers=auth_headers(owner_token),
    )
    file_content = _jsonl_with_repeated_bash("npm test", 5)
    client.post(
        f"/projects/{project_id}/sessions",
        files={"file": ("session.jsonl", io.BytesIO(file_content), "application/jsonl")},
        headers=auth_headers(owner_token),
    )

    owner_resp = client.get(
        f"/projects/{project_id}/recommendations/me", headers=auth_headers(owner_token)
    )
    assert owner_resp.status_code == 200
    assert len(owner_resp.json()) == 1
    assert owner_resp.json()[0]["payload"]["command"] == "npm test"

    member_resp = client.get(
        f"/projects/{project_id}/recommendations/me", headers=auth_headers(member_token)
    )
    assert member_resp.json() == []


def test_skill_candidate_matches_and_promotes(client, db_session, monkeypatch):
    async def fake_analyze_skill(pattern_summary, client=None):
        return {
            "candidates": [
                {
                    "type": "skill",
                    "skill_name": "run-migrations",
                    "skill_description": "마이그레이션 후 시드와 재시작을 순서대로 진행한다",
                    "suggested_steps": "1. migrate\n2. seed\n3. restart",
                    "reason": "매번 이 순서로 실행하셨어요.",
                    "confidence": "high",
                }
            ],
            "remaining_rpd": 499,
        }

    async def fake_embed(text, client=None):
        return [0.1, 0.2, 0.3]

    monkeypatch.setattr(ai_client, "analyze", fake_analyze_skill)
    monkeypatch.setattr(ai_client, "embed", fake_embed)
    owner, owner_token = make_user_and_token(db_session, "owner")
    member, member_token = make_user_and_token(db_session, "member")
    project_id = _create_project(client, owner_token)
    client.post(
        f"/projects/{project_id}/invite",
        json={"username": member.username},
        headers=auth_headers(owner_token),
    )
    file_content = _jsonl_with_repeated_bash("npm test", 5)

    client.post(
        f"/projects/{project_id}/sessions",
        files={"file": ("s1.jsonl", io.BytesIO(file_content), "application/jsonl")},
        headers=auth_headers(owner_token),
    )
    second_resp = client.post(
        f"/projects/{project_id}/sessions",
        files={"file": ("s2.jsonl", io.BytesIO(file_content), "application/jsonl")},
        headers=auth_headers(member_token),
    )
    groups = second_resp.json()["updated_team_groups"]
    assert groups[0]["type"] == "skill"
    assert groups[0]["promoted"] is True
