from sqlmodel import select

from .conftest import auth_headers, make_user_and_token, models


def _create_project(client, owner_token: str) -> str:
    resp = client.post(
        "/projects", json={"name": "test"}, headers=auth_headers(owner_token)
    )
    return resp.json()["id"]


def test_non_owner_cannot_delete_project(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    member, member_token = make_user_and_token(db_session, "member")
    project_id = _create_project(client, owner_token)
    client.post(
        f"/projects/{project_id}/invite",
        json={"username": member.username},
        headers=auth_headers(owner_token),
    )

    resp = client.delete(f"/projects/{project_id}", headers=auth_headers(member_token))
    assert resp.status_code == 403


def test_owner_can_delete_project(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)

    resp = client.delete(f"/projects/{project_id}", headers=auth_headers(owner_token))
    assert resp.status_code == 200

    get_resp = client.get(f"/projects/{project_id}", headers=auth_headers(owner_token))
    assert get_resp.status_code == 404


def test_delete_removes_members_and_revisions(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    member, member_token = make_user_and_token(db_session, "member")
    project_id = _create_project(client, owner_token)
    client.post(
        f"/projects/{project_id}/invite",
        json={"username": member.username},
        headers=auth_headers(owner_token),
    )
    client.put(
        f"/projects/{project_id}", json={"content": "v1"}, headers=auth_headers(owner_token)
    )

    client.delete(f"/projects/{project_id}", headers=auth_headers(owner_token))

    members = db_session.exec(
        select(models.ProjectMember).where(models.ProjectMember.project_id == project_id)
    ).all()
    revisions = db_session.exec(
        select(models.ProjectRevision).where(
            models.ProjectRevision.project_id == project_id
        )
    ).all()
    assert members == []
    assert revisions == []
