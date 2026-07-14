import io

from .conftest import auth_headers, make_user_and_token
from .test_sessions import _create_project, _fake_analyze, _jsonl_with_repeated_bash, ai_client


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


def test_my_recommendations_include_id_and_applied_false_by_default(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(ai_client, "analyze", _fake_analyze)
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)
    _upload_and_get_recommendation_id(client, project_id, owner_token)

    resp = client.get(
        f"/projects/{project_id}/recommendations/me", headers=auth_headers(owner_token)
    )
    body = resp.json()[0]
    assert body["id"]
    assert body["applied"] is False


def test_apply_marks_personal_recommendation_applied(client, db_session, monkeypatch):
    monkeypatch.setattr(ai_client, "analyze", _fake_analyze)
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)
    rec_id = _upload_and_get_recommendation_id(client, project_id, owner_token)

    apply_resp = client.post(
        f"/projects/{project_id}/personal-recommendations/{rec_id}/apply",
        headers=auth_headers(owner_token),
    )
    assert apply_resp.status_code == 200

    resp = client.get(
        f"/projects/{project_id}/recommendations/me", headers=auth_headers(owner_token)
    )
    assert resp.json()[0]["applied"] is True


def test_cannot_apply_another_users_recommendation(client, db_session, monkeypatch):
    monkeypatch.setattr(ai_client, "analyze", _fake_analyze)
    owner, owner_token = make_user_and_token(db_session, "owner")
    member, member_token = make_user_and_token(db_session, "member")
    project_id = _create_project(client, owner_token)
    client.post(
        f"/projects/{project_id}/invite",
        json={"username": member.username},
        headers=auth_headers(owner_token),
    )
    rec_id = _upload_and_get_recommendation_id(client, project_id, owner_token)

    resp = client.post(
        f"/projects/{project_id}/personal-recommendations/{rec_id}/apply",
        headers=auth_headers(member_token),
    )
    assert resp.status_code == 404


def test_apply_nonexistent_personal_recommendation_returns_404(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)

    resp = client.post(
        f"/projects/{project_id}/personal-recommendations/does-not-exist/apply",
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 404


def test_applying_team_group_reflects_as_applied_in_my_recommendations(
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
    _upload_and_get_recommendation_id(client, project_id, owner_token)
    _upload_and_get_recommendation_id(client, project_id, member_token)

    team_resp = client.get(
        f"/projects/{project_id}/recommendations/team", headers=auth_headers(owner_token)
    )
    group_id = team_resp.json()[0]["id"]
    client.post(
        f"/projects/{project_id}/recommendation-groups/{group_id}/apply",
        headers=auth_headers(owner_token),
    )

    owner_me = client.get(
        f"/projects/{project_id}/recommendations/me", headers=auth_headers(owner_token)
    )
    assert owner_me.json()[0]["applied"] is True

    member_me = client.get(
        f"/projects/{project_id}/recommendations/me", headers=auth_headers(member_token)
    )
    assert member_me.json()[0]["applied"] is True


def test_applying_personal_recommendation_reflects_as_applied_in_team_recommendations(
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
    owner_rec_id = _upload_and_get_recommendation_id(client, project_id, owner_token)
    _upload_and_get_recommendation_id(client, project_id, member_token)

    client.post(
        f"/projects/{project_id}/personal-recommendations/{owner_rec_id}/apply",
        headers=auth_headers(owner_token),
    )

    team_resp = client.get(
        f"/projects/{project_id}/recommendations/team", headers=auth_headers(owner_token)
    )
    assert team_resp.json()[0]["applied"] is True
