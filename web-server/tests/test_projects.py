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
