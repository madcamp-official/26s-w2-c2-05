from .conftest import auth_headers, make_user_and_token


def _create_project(client, owner_token: str) -> str:
    resp = client.post(
        "/projects", json={"name": "test"}, headers=auth_headers(owner_token)
    )
    return resp.json()["id"]


def test_save_without_expected_updated_at_still_works(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)

    resp = client.put(
        f"/projects/{project_id}",
        json={"content": "hello"},
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == "hello"


def test_save_with_matching_expected_updated_at_succeeds(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)
    current_updated_at = client.get(
        f"/projects/{project_id}", headers=auth_headers(owner_token)
    ).json()["updated_at"]

    resp = client.put(
        f"/projects/{project_id}",
        json={"content": "hello", "expected_updated_at": current_updated_at},
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 200


def test_save_with_stale_expected_updated_at_returns_409_and_does_not_overwrite(
    client, db_session
):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)
    stale_updated_at = client.get(
        f"/projects/{project_id}", headers=auth_headers(owner_token)
    ).json()["updated_at"]

    client.put(
        f"/projects/{project_id}",
        json={"content": "first save"},
        headers=auth_headers(owner_token),
    )

    resp = client.put(
        f"/projects/{project_id}",
        json={"content": "stale save", "expected_updated_at": stale_updated_at},
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 409

    get_resp = client.get(f"/projects/{project_id}", headers=auth_headers(owner_token))
    assert get_resp.json()["content"] == "first save"


def test_hooks_save_also_enforces_optimistic_lock(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)
    stale_updated_at = client.get(
        f"/projects/{project_id}", headers=auth_headers(owner_token)
    ).json()["updated_at"]

    client.put(
        f"/projects/{project_id}/hooks",
        json={"hooks_content": '{"hooks": {}}'},
        headers=auth_headers(owner_token),
    )

    resp = client.put(
        f"/projects/{project_id}/hooks",
        json={
            "hooks_content": '{"hooks": {"x": []}}',
            "expected_updated_at": stale_updated_at,
        },
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 409

    get_resp = client.get(f"/projects/{project_id}", headers=auth_headers(owner_token))
    assert get_resp.json()["hooks_content"] == '{"hooks": {}}'


def test_updated_at_changes_after_successful_save(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)
    before = client.get(
        f"/projects/{project_id}", headers=auth_headers(owner_token)
    ).json()["updated_at"]

    resp = client.put(
        f"/projects/{project_id}",
        json={"content": "hello"},
        headers=auth_headers(owner_token),
    )
    assert resp.json()["updated_at"] != before
