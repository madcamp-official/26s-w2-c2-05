from .conftest import auth_headers, make_user_and_token


def _create_project(client, owner_token: str) -> str:
    resp = client.post(
        "/projects", json={"name": "test"}, headers=auth_headers(owner_token)
    )
    return resp.json()["id"]


def test_member_can_leave_project(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    member, member_token = make_user_and_token(db_session, "member")
    project_id = _create_project(client, owner_token)
    client.post(
        f"/projects/{project_id}/invite",
        json={"username": member.username},
        headers=auth_headers(owner_token),
    )

    resp = client.post(
        f"/projects/{project_id}/leave", headers=auth_headers(member_token)
    )
    assert resp.status_code == 200

    get_resp = client.get(f"/projects/{project_id}", headers=auth_headers(member_token))
    assert get_resp.status_code == 403


def test_owner_cannot_leave_project(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)

    resp = client.post(
        f"/projects/{project_id}/leave", headers=auth_headers(owner_token)
    )
    assert resp.status_code == 400


def test_non_member_cannot_leave_project(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    outsider, outsider_token = make_user_and_token(db_session, "outsider")
    project_id = _create_project(client, owner_token)

    resp = client.post(
        f"/projects/{project_id}/leave", headers=auth_headers(outsider_token)
    )
    assert resp.status_code == 403
