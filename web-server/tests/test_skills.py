from .conftest import auth_headers, make_user_and_token, models


def _create_project(client, owner_token: str) -> str:
    resp = client.post(
        "/projects", json={"name": "test"}, headers=auth_headers(owner_token)
    )
    return resp.json()["id"]


def _create_skill_directly(db_session, project_id: str) -> str:
    skill = models.Skill(
        project_id=project_id,
        name="run-migrations",
        description="마이그레이션을 실행한다",
        steps_content="1. migrate\n2. seed\n3. restart",
    )
    db_session.add(skill)
    db_session.commit()
    db_session.refresh(skill)
    return skill.id


def test_list_skills_returns_project_skills(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)
    _create_skill_directly(db_session, project_id)

    resp = client.get(f"/projects/{project_id}/skills", headers=auth_headers(owner_token))
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["name"] == "run-migrations"


def test_non_member_cannot_list_skills(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    outsider, outsider_token = make_user_and_token(db_session, "outsider")
    project_id = _create_project(client, owner_token)

    resp = client.get(
        f"/projects/{project_id}/skills", headers=auth_headers(outsider_token)
    )
    assert resp.status_code == 403


def test_get_single_skill(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)
    skill_id = _create_skill_directly(db_session, project_id)

    resp = client.get(
        f"/projects/{project_id}/skills/{skill_id}", headers=auth_headers(owner_token)
    )
    assert resp.status_code == 200
    assert resp.json()["steps_content"] == "1. migrate\n2. seed\n3. restart"


def test_update_skill_creates_skill_revision(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)
    skill_id = _create_skill_directly(db_session, project_id)

    resp = client.put(
        f"/projects/{project_id}/skills/{skill_id}",
        json={
            "name": "run-migrations",
            "description": "수정된 설명",
            "steps_content": "1. migrate\n2. seed",
        },
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "수정된 설명"

    revisions_resp = client.get(
        f"/projects/{project_id}/revisions?target=skill", headers=auth_headers(owner_token)
    )
    assert revisions_resp.status_code == 200
    assert len(revisions_resp.json()) == 1


def test_non_member_cannot_update_skill(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    outsider, outsider_token = make_user_and_token(db_session, "outsider")
    project_id = _create_project(client, owner_token)
    skill_id = _create_skill_directly(db_session, project_id)

    resp = client.put(
        f"/projects/{project_id}/skills/{skill_id}",
        json={"name": "x", "description": "x", "steps_content": "x"},
        headers=auth_headers(outsider_token),
    )
    assert resp.status_code == 403


def test_delete_skill(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)
    skill_id = _create_skill_directly(db_session, project_id)

    resp = client.delete(
        f"/projects/{project_id}/skills/{skill_id}", headers=auth_headers(owner_token)
    )
    assert resp.status_code == 200

    list_resp = client.get(
        f"/projects/{project_id}/skills", headers=auth_headers(owner_token)
    )
    assert list_resp.json() == []


def test_get_nonexistent_skill_returns_404(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)

    resp = client.get(
        f"/projects/{project_id}/skills/does-not-exist", headers=auth_headers(owner_token)
    )
    assert resp.status_code == 404


def test_update_skill_rejects_invalid_name(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)
    skill_id = _create_skill_directly(db_session, project_id)

    resp = client.put(
        f"/projects/{project_id}/skills/{skill_id}",
        json={
            "name": "../../evil-path",
            "description": "설명",
            "steps_content": "steps",
        },
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 400


def test_update_skill_rejects_description_with_newline(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)
    skill_id = _create_skill_directly(db_session, project_id)

    resp = client.put(
        f"/projects/{project_id}/skills/{skill_id}",
        json={
            "name": "valid-name",
            "description": "line1\ninjected: value",
            "steps_content": "steps",
        },
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 400
