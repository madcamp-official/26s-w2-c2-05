import io

from .conftest import auth_headers, make_user_and_token
from .test_sessions import _create_project, _jsonl_with_repeated_bash, ai_client


async def _fake_analyze_skill(pattern_summary, client=None):
    return {
        "candidates": [
            {
                "type": "skill",
                "skill_name": "run-migrations",
                "skill_description": "마이그레이션 후 시드와 재시작을 순서대로 진행한다",
                "suggested_steps": "1. migrate 실행\n2. seed 실행\n3. 서버 재시작",
                "reason": "매번 이 순서로 실행하셨어요.",
                "confidence": "high",
            }
        ],
        "remaining_rpd": 499,
    }


async def _fake_embed(text, client=None):
    return [0.1, 0.2, 0.3]


def _upload_and_get_recommendation_id(client, project_id, token) -> str:
    file_content = _jsonl_with_repeated_bash("npm test", 5)
    client.post(
        f"/projects/{project_id}/sessions",
        files={"file": ("s.jsonl", io.BytesIO(file_content), "application/jsonl")},
        headers=auth_headers(token),
    )
    resp = client.get(
        f"/projects/{project_id}/recommendations/me", headers=auth_headers(token)
    )
    return resp.json()[0]["id"]


def test_apply_personal_skill_recommendation_creates_skill(client, db_session, monkeypatch):
    monkeypatch.setattr(ai_client, "analyze", _fake_analyze_skill)
    monkeypatch.setattr(ai_client, "embed", _fake_embed)
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)
    rec_id = _upload_and_get_recommendation_id(client, project_id, owner_token)

    apply_resp = client.post(
        f"/projects/{project_id}/personal-recommendations/{rec_id}/apply",
        headers=auth_headers(owner_token),
    )
    assert apply_resp.status_code == 200

    skills_resp = client.get(
        f"/projects/{project_id}/skills", headers=auth_headers(owner_token)
    )
    assert skills_resp.status_code == 200
    assert len(skills_resp.json()) == 1
    assert skills_resp.json()[0]["name"] == "run-migrations"


def test_apply_team_skill_group_creates_skill(client, db_session, monkeypatch):
    monkeypatch.setattr(ai_client, "analyze", _fake_analyze_skill)
    monkeypatch.setattr(ai_client, "embed", _fake_embed)
    owner, owner_token = make_user_and_token(db_session, "owner")
    member, member_token = make_user_and_token(db_session, "member")
    project_id = _create_project(client, owner_token)
    client.post(
        f"/projects/{project_id}/invite",
        json={"username": member.username},
        headers=auth_headers(owner_token),
    )
    _upload_and_get_recommendation_id(client, project_id, owner_token)
    _upload_and_get_recommendation_id(client, project_id, member_token)

    team_resp = client.get(
        f"/projects/{project_id}/recommendations/team", headers=auth_headers(owner_token)
    )
    group_id = team_resp.json()[0]["id"]

    apply_resp = client.post(
        f"/projects/{project_id}/recommendation-groups/{group_id}/apply",
        headers=auth_headers(owner_token),
    )
    assert apply_resp.status_code == 200

    skills_resp = client.get(
        f"/projects/{project_id}/skills", headers=auth_headers(owner_token)
    )
    assert len(skills_resp.json()) == 1
    assert skills_resp.json()[0]["name"] == "run-migrations"


def test_apply_rejects_malicious_skill_name(client, db_session, monkeypatch):
    async def fake_analyze_malicious_skill(pattern_summary, client=None):
        return {
            "candidates": [
                {
                    "type": "skill",
                    "skill_name": "../../evil-path",
                    "skill_description": "마이그레이션 후 시드와 재시작을 순서대로 진행한다",
                    "suggested_steps": "1. migrate\n2. seed\n3. restart",
                    "reason": "매번 이 순서로 실행하셨어요.",
                    "confidence": "high",
                }
            ],
            "remaining_rpd": 499,
        }

    monkeypatch.setattr(ai_client, "analyze", fake_analyze_malicious_skill)
    monkeypatch.setattr(ai_client, "embed", _fake_embed)
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)
    rec_id = _upload_and_get_recommendation_id(client, project_id, owner_token)

    apply_resp = client.post(
        f"/projects/{project_id}/personal-recommendations/{rec_id}/apply",
        headers=auth_headers(owner_token),
    )
    assert apply_resp.status_code == 400

    skills_resp = client.get(
        f"/projects/{project_id}/skills", headers=auth_headers(owner_token)
    )
    assert skills_resp.json() == []
