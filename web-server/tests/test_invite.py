from .conftest import auth_headers, make_user_and_token


def _create_project(client, owner_token: str) -> str:
    resp = client.post(
        "/projects", json={"name": "test"}, headers=auth_headers(owner_token)
    )
    return resp.json()["id"]


def test_non_owner_cannot_invite(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    member, member_token = make_user_and_token(db_session, "member")
    target, _ = make_user_and_token(db_session, "target")
    project_id = _create_project(client, owner_token)
    client.post(
        f"/projects/{project_id}/invite",
        json={"username": member.username},
        headers=auth_headers(owner_token),
    )

    resp = client.post(
        f"/projects/{project_id}/invite",
        json={"username": target.username},
        headers=auth_headers(member_token),
    )
    assert resp.status_code == 403


def test_invite_nonexistent_user_returns_404(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)

    resp = client.post(
        f"/projects/{project_id}/invite",
        json={"username": "no-such-user"},
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 404


def test_invite_existing_member_returns_400(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    target, _ = make_user_and_token(db_session, "target")
    project_id = _create_project(client, owner_token)
    client.post(
        f"/projects/{project_id}/invite",
        json={"username": target.username},
        headers=auth_headers(owner_token),
    )

    resp = client.post(
        f"/projects/{project_id}/invite",
        json={"username": target.username},
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 400


def test_owner_invites_user_by_username(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    target, target_token = make_user_and_token(db_session, "target")
    project_id = _create_project(client, owner_token)

    resp = client.post(
        f"/projects/{project_id}/invite",
        json={"username": target.username},
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 200

    get_resp = client.get(
        f"/projects/{project_id}", headers=auth_headers(target_token)
    )
    assert get_resp.status_code == 200
