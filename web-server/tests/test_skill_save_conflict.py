from .conftest import auth_headers, make_user_and_token
from .test_apply_skill import _fake_analyze_skill, _fake_embed, _upload_and_get_recommendation_id
from .test_sessions import _create_project, ai_client


def _create_skill(client, project_id, token) -> str:
    rec_id = _upload_and_get_recommendation_id(client, project_id, token)
    client.post(
        f"/projects/{project_id}/personal-recommendations/{rec_id}/apply",
        headers=auth_headers(token),
    )
    resp = client.get(f"/projects/{project_id}/skills", headers=auth_headers(token))
    return resp.json()[0]["id"]


def test_skill_update_without_expected_updated_at_still_works(client, db_session, monkeypatch):
    monkeypatch.setattr(ai_client, "analyze", _fake_analyze_skill)
    monkeypatch.setattr(ai_client, "embed", _fake_embed)
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)
    skill_id = _create_skill(client, project_id, owner_token)

    resp = client.put(
        f"/projects/{project_id}/skills/{skill_id}",
        json={"name": "run-migrations", "description": "new desc", "steps_content": "1. a"},
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "new desc"


def test_skill_update_with_stale_expected_updated_at_returns_409(client, db_session, monkeypatch):
    monkeypatch.setattr(ai_client, "analyze", _fake_analyze_skill)
    monkeypatch.setattr(ai_client, "embed", _fake_embed)
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)
    skill_id = _create_skill(client, project_id, owner_token)

    stale = client.get(
        f"/projects/{project_id}/skills/{skill_id}", headers=auth_headers(owner_token)
    ).json()["updated_at"]

    client.put(
        f"/projects/{project_id}/skills/{skill_id}",
        json={"name": "run-migrations", "description": "first update", "steps_content": "1. a"},
        headers=auth_headers(owner_token),
    )

    resp = client.put(
        f"/projects/{project_id}/skills/{skill_id}",
        json={
            "name": "run-migrations",
            "description": "stale update",
            "steps_content": "1. b",
            "expected_updated_at": stale,
        },
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 409

    current = client.get(
        f"/projects/{project_id}/skills/{skill_id}", headers=auth_headers(owner_token)
    ).json()
    assert current["description"] == "first update"


def test_skill_update_broadcasts_skill_changed_event(client, db_session, monkeypatch):
    monkeypatch.setattr(ai_client, "analyze", _fake_analyze_skill)
    monkeypatch.setattr(ai_client, "embed", _fake_embed)
    owner, owner_token = make_user_and_token(db_session, "owner")
    member, member_token = make_user_and_token(db_session, "member")
    project_id = _create_project(client, owner_token)
    client.post(
        f"/projects/{project_id}/invite",
        json={"username": member.username},
        headers=auth_headers(owner_token),
    )
    skill_id = _create_skill(client, project_id, owner_token)

    with client.websocket_connect(f"/ws/projects/{project_id}?token={owner_token}") as ws1:
        ws1.receive_json()
        with client.websocket_connect(f"/ws/projects/{project_id}?token={member_token}") as ws2:
            ws2.receive_json()
            ws1.receive_json()

            client.put(
                f"/projects/{project_id}/skills/{skill_id}",
                json={
                    "name": "run-migrations",
                    "description": "updated",
                    "steps_content": "1. a",
                },
                headers=auth_headers(owner_token),
            )

            event = ws2.receive_json()
            assert event == {
                "type": "skill_changed",
                "action": "updated",
                "skill_id": skill_id,
                "updated_by": "owner",
            }


def test_skill_delete_broadcasts_skill_changed_event(client, db_session, monkeypatch):
    monkeypatch.setattr(ai_client, "analyze", _fake_analyze_skill)
    monkeypatch.setattr(ai_client, "embed", _fake_embed)
    owner, owner_token = make_user_and_token(db_session, "owner")
    member, member_token = make_user_and_token(db_session, "member")
    project_id = _create_project(client, owner_token)
    client.post(
        f"/projects/{project_id}/invite",
        json={"username": member.username},
        headers=auth_headers(owner_token),
    )
    skill_id = _create_skill(client, project_id, owner_token)

    with client.websocket_connect(f"/ws/projects/{project_id}?token={owner_token}") as ws1:
        ws1.receive_json()
        with client.websocket_connect(f"/ws/projects/{project_id}?token={member_token}") as ws2:
            ws2.receive_json()
            ws1.receive_json()

            client.delete(
                f"/projects/{project_id}/skills/{skill_id}",
                headers=auth_headers(owner_token),
            )

            event = ws2.receive_json()
            assert event == {
                "type": "skill_changed",
                "action": "deleted",
                "skill_id": skill_id,
                "updated_by": "owner",
            }


def test_creating_skill_via_apply_broadcasts_skill_changed_event(client, db_session, monkeypatch):
    monkeypatch.setattr(ai_client, "analyze", _fake_analyze_skill)
    monkeypatch.setattr(ai_client, "embed", _fake_embed)
    owner, owner_token = make_user_and_token(db_session, "owner")
    member, member_token = make_user_and_token(db_session, "member")
    project_id = _create_project(client, owner_token)
    client.post(
        f"/projects/{project_id}/invite",
        json={"username": member.username},
        headers=auth_headers(owner_token),
    )
    rec_id = _upload_and_get_recommendation_id(client, project_id, owner_token)

    with client.websocket_connect(f"/ws/projects/{project_id}?token={owner_token}") as ws1:
        ws1.receive_json()
        with client.websocket_connect(f"/ws/projects/{project_id}?token={member_token}") as ws2:
            ws2.receive_json()
            ws1.receive_json()

            client.post(
                f"/projects/{project_id}/personal-recommendations/{rec_id}/apply",
                headers=auth_headers(owner_token),
            )

            event = ws2.receive_json()
            assert event["type"] == "skill_changed"
            assert event["action"] == "created"
            assert event["updated_by"] == "owner"
            assert event["skill_id"]
