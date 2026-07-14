from .conftest import auth_headers, make_user_and_token


def _create_project(client, owner_token: str) -> str:
    resp = client.post(
        "/projects", json={"name": "test"}, headers=auth_headers(owner_token)
    )
    return resp.json()["id"]


def test_save_hooks_content(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)

    new_hooks = '{"hooks": {"PostToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "npm test"}]}]}}'
    resp = client.put(
        f"/projects/{project_id}/hooks",
        json={"hooks_content": new_hooks},
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 200
    assert resp.json()["hooks_content"] == new_hooks

    get_resp = client.get(f"/projects/{project_id}", headers=auth_headers(owner_token))
    assert get_resp.json()["hooks_content"] == new_hooks


def test_non_member_cannot_save_hooks(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    outsider, outsider_token = make_user_and_token(db_session, "outsider")
    project_id = _create_project(client, owner_token)

    resp = client.put(
        f"/projects/{project_id}/hooks",
        json={"hooks_content": "{}"},
        headers=auth_headers(outsider_token),
    )
    assert resp.status_code == 403


def test_invalid_json_hooks_content_returns_400(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)

    resp = client.put(
        f"/projects/{project_id}/hooks",
        json={"hooks_content": "not valid json"},
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 400


def test_saving_hooks_creates_hooks_revision(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)

    client.put(
        f"/projects/{project_id}/hooks",
        json={"hooks_content": '{"hooks": {}}'},
        headers=auth_headers(owner_token),
    )

    resp = client.get(
        f"/projects/{project_id}/revisions?target=hooks", headers=auth_headers(owner_token)
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    content_resp = client.get(
        f"/projects/{project_id}/revisions?target=content", headers=auth_headers(owner_token)
    )
    assert content_resp.json() == []


def test_revisions_without_target_returns_both_kinds_with_target_label(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)

    client.put(
        f"/projects/{project_id}",
        json={"content": "hello"},
        headers=auth_headers(owner_token),
    )
    client.put(
        f"/projects/{project_id}/hooks",
        json={"hooks_content": '{"hooks": {}}'},
        headers=auth_headers(owner_token),
    )

    resp = client.get(f"/projects/{project_id}/revisions", headers=auth_headers(owner_token))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    targets = {r["target"] for r in body}
    assert targets == {"content", "hooks"}
