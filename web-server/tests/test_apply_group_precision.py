import io

from sqlmodel import select

from .conftest import auth_headers, make_user_and_token, models
from .test_sessions import _create_project, _jsonl_with_repeated_bash, ai_client


async def _fake_analyze_two_hooks(pattern_summary, client=None):
    return {
        "candidates": [
            {
                "type": "hook",
                "event": "PostToolUse",
                "matcher": "Bash",
                "command": "npm test",
                "reason": "테스트를 항상 직접 실행하셨어요.",
                "confidence": "high",
            },
            {
                "type": "hook",
                "event": "PostToolUse",
                "matcher": "Bash",
                "command": "npm lint",
                "reason": "린트를 항상 직접 실행하셨어요.",
                "confidence": "high",
            },
        ],
        "remaining_rpd": 499,
    }


def test_personal_recommendations_are_linked_to_distinct_groups(client, db_session, monkeypatch):
    monkeypatch.setattr(ai_client, "analyze", _fake_analyze_two_hooks)
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)
    file_content = _jsonl_with_repeated_bash("npm test", 5)

    resp = client.post(
        f"/projects/{project_id}/sessions",
        files={"file": ("s.jsonl", io.BytesIO(file_content), "application/jsonl")},
        headers=auth_headers(owner_token),
    )
    body = resp.json()
    assert len(body["personal_recommendations"]) == 2

    recs = db_session.exec(select(models.PersonalRecommendation)).all()
    group_ids = {r.group_id for r in recs}
    assert None not in group_ids
    assert len(group_ids) == 2  # 서로 다른 그룹에 연결됨


def test_applying_one_groups_personal_rec_does_not_apply_sibling_in_same_session(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(ai_client, "analyze", _fake_analyze_two_hooks)
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)
    file_content = _jsonl_with_repeated_bash("npm test", 5)

    client.post(
        f"/projects/{project_id}/sessions",
        files={"file": ("s.jsonl", io.BytesIO(file_content), "application/jsonl")},
        headers=auth_headers(owner_token),
    )

    me_resp = client.get(
        f"/projects/{project_id}/recommendations/me", headers=auth_headers(owner_token)
    )
    recs = me_resp.json()
    npm_test_rec = next(r for r in recs if r["payload"]["command"] == "npm test")
    npm_lint_rec = next(r for r in recs if r["payload"]["command"] == "npm lint")

    client.post(
        f"/projects/{project_id}/personal-recommendations/{npm_test_rec['id']}/apply",
        headers=auth_headers(owner_token),
    )

    me_resp_after = client.get(
        f"/projects/{project_id}/recommendations/me", headers=auth_headers(owner_token)
    )
    recs_after = {r["id"]: r["applied"] for r in me_resp_after.json()}
    assert recs_after[npm_test_rec["id"]] is True
    assert recs_after[npm_lint_rec["id"]] is False
