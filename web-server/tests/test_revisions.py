from sqlmodel import select

from .conftest import auth_headers, make_user_and_token, models


def _create_project(client, owner_token: str) -> str:
    resp = client.post(
        "/projects", json={"name": "test"}, headers=auth_headers(owner_token)
    )
    return resp.json()["id"]


def test_save_creates_revision(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)

    resp = client.put(
        f"/projects/{project_id}",
        json={"content": "# hello"},
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 200

    revisions = db_session.exec(
        select(models.ProjectRevision).where(
            models.ProjectRevision.project_id == project_id
        )
    ).all()
    assert len(revisions) == 1
    assert revisions[0].content == "# hello"
    assert revisions[0].user_id == owner.user_id


def test_each_save_adds_a_new_revision(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)

    client.put(
        f"/projects/{project_id}", json={"content": "v1"}, headers=auth_headers(owner_token)
    )
    client.put(
        f"/projects/{project_id}", json={"content": "v2"}, headers=auth_headers(owner_token)
    )

    revisions = db_session.exec(
        select(models.ProjectRevision).where(
            models.ProjectRevision.project_id == project_id
        )
    ).all()
    assert len(revisions) == 2


def test_non_member_cannot_list_revisions(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    outsider, outsider_token = make_user_and_token(db_session, "outsider")
    project_id = _create_project(client, owner_token)

    resp = client.get(
        f"/projects/{project_id}/revisions", headers=auth_headers(outsider_token)
    )
    assert resp.status_code == 403


def test_revision_list_is_newest_first_and_excludes_content(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)

    client.put(
        f"/projects/{project_id}", json={"content": "v1"}, headers=auth_headers(owner_token)
    )
    client.put(
        f"/projects/{project_id}", json={"content": "v2"}, headers=auth_headers(owner_token)
    )

    resp = client.get(
        f"/projects/{project_id}/revisions", headers=auth_headers(owner_token)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert "content" not in body[0]
    assert body[0]["username"] == "owner"
    assert body[0]["created_at"] >= body[1]["created_at"]


def test_get_single_revision_includes_content(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)

    client.put(
        f"/projects/{project_id}", json={"content": "v1"}, headers=auth_headers(owner_token)
    )
    list_resp = client.get(
        f"/projects/{project_id}/revisions", headers=auth_headers(owner_token)
    )
    revision_id = list_resp.json()[0]["id"]

    resp = client.get(
        f"/projects/{project_id}/revisions/{revision_id}", headers=auth_headers(owner_token)
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == "v1"
