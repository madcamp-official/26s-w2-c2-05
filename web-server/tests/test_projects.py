from .conftest import auth_headers, make_user_and_token


def _create_project(client, owner_token: str) -> str:
    resp = client.post(
        "/projects", json={"name": "test"}, headers=auth_headers(owner_token)
    )
    return resp.json()["id"]


def test_list_projects_returns_role_for_owner_and_member(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    member, member_token = make_user_and_token(db_session, "member")
    project_id = _create_project(client, owner_token)
    client.post(
        f"/projects/{project_id}/invite",
        json={"username": member.username},
        headers=auth_headers(owner_token),
    )

    owner_resp = client.get("/projects", headers=auth_headers(owner_token))
    assert owner_resp.json()[0]["role"] == "owner"

    member_resp = client.get("/projects", headers=auth_headers(member_token))
    assert member_resp.json()[0]["role"] == "member"


def test_get_project_returns_role(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    member, member_token = make_user_and_token(db_session, "member")
    project_id = _create_project(client, owner_token)
    client.post(
        f"/projects/{project_id}/invite",
        json={"username": member.username},
        headers=auth_headers(owner_token),
    )

    owner_resp = client.get(f"/projects/{project_id}", headers=auth_headers(owner_token))
    assert owner_resp.json()["role"] == "owner"

    member_resp = client.get(f"/projects/{project_id}", headers=auth_headers(member_token))
    assert member_resp.json()["role"] == "member"


def test_created_at_is_timezone_aware_in_response(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)

    resp = client.get(f"/projects/{project_id}", headers=auth_headers(owner_token))
    created_at = resp.json()["created_at"]
    assert created_at.endswith("Z") or "+00:00" in created_at


def test_non_owner_cannot_rename_project(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    member, member_token = make_user_and_token(db_session, "member")
    project_id = _create_project(client, owner_token)
    client.post(
        f"/projects/{project_id}/invite",
        json={"username": member.username},
        headers=auth_headers(owner_token),
    )

    resp = client.put(
        f"/projects/{project_id}/name",
        json={"name": "새 이름"},
        headers=auth_headers(member_token),
    )
    assert resp.status_code == 403


def test_owner_can_rename_project(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)

    resp = client.put(
        f"/projects/{project_id}/name",
        json={"name": "새 이름"},
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "새 이름"

    get_resp = client.get(f"/projects/{project_id}", headers=auth_headers(owner_token))
    assert get_resp.json()["name"] == "새 이름"


def test_create_project_response_includes_default_hooks_content(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")

    resp = client.post(
        "/projects", json={"name": "test"}, headers=auth_headers(owner_token)
    )
    assert resp.status_code == 200
    assert resp.json()["hooks_content"] == '{\n  "hooks": {}\n}'
