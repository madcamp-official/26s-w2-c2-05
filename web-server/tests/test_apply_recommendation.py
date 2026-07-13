import io

from .conftest import auth_headers, make_user_and_token
from .test_sessions import _create_project, _fake_analyze, _jsonl_with_repeated_bash, ai_client


def _upload(client, project_id, token, filename="s.jsonl"):
    file_content = _jsonl_with_repeated_bash("npm test", 5)
    return client.post(
        f"/projects/{project_id}/sessions",
        files={"file": (filename, io.BytesIO(file_content), "application/jsonl")},
        headers=auth_headers(token),
    )


def _promoted_group_id(client, project_id, token) -> str:
    resp = client.get(
        f"/projects/{project_id}/recommendations/team", headers=auth_headers(token)
    )
    return resp.json()[0]["id"]


def test_non_member_cannot_apply_group(client, db_session, monkeypatch):
    monkeypatch.setattr(ai_client, "analyze", _fake_analyze)
    owner, owner_token = make_user_and_token(db_session, "owner")
    member, member_token = make_user_and_token(db_session, "member")
    outsider, outsider_token = make_user_and_token(db_session, "outsider")
    project_id = _create_project(client, owner_token)
    client.post(
        f"/projects/{project_id}/invite",
        json={"username": member.username},
        headers=auth_headers(owner_token),
    )
    _upload(client, project_id, owner_token, "s1.jsonl")
    _upload(client, project_id, member_token, "s2.jsonl")
    group_id = _promoted_group_id(client, project_id, owner_token)

    resp = client.post(
        f"/projects/{project_id}/recommendation-groups/{group_id}/apply",
        headers=auth_headers(outsider_token),
    )
    assert resp.status_code == 403


def test_apply_marks_group_applied_in_team_recommendations(client, db_session, monkeypatch):
    monkeypatch.setattr(ai_client, "analyze", _fake_analyze)
    owner, owner_token = make_user_and_token(db_session, "owner")
    member, member_token = make_user_and_token(db_session, "member")
    project_id = _create_project(client, owner_token)
    client.post(
        f"/projects/{project_id}/invite",
        json={"username": member.username},
        headers=auth_headers(owner_token),
    )
    _upload(client, project_id, owner_token, "s1.jsonl")
    _upload(client, project_id, member_token, "s2.jsonl")
    group_id = _promoted_group_id(client, project_id, owner_token)

    before = client.get(
        f"/projects/{project_id}/recommendations/team", headers=auth_headers(owner_token)
    )
    assert before.json()[0]["applied"] is False

    apply_resp = client.post(
        f"/projects/{project_id}/recommendation-groups/{group_id}/apply",
        headers=auth_headers(owner_token),
    )
    assert apply_resp.status_code == 200

    after = client.get(
        f"/projects/{project_id}/recommendations/team", headers=auth_headers(owner_token)
    )
    assert after.json()[0]["applied"] is True


def test_apply_nonexistent_group_returns_404(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)

    resp = client.post(
        f"/projects/{project_id}/recommendation-groups/does-not-exist/apply",
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 404
