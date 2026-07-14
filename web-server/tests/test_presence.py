import pytest
from starlette.testclient import WebSocketDisconnect

from .conftest import auth_headers, make_user_and_token


def _create_project(client, owner_token: str) -> str:
    resp = client.post(
        "/projects", json={"name": "test"}, headers=auth_headers(owner_token)
    )
    return resp.json()["id"]


def test_non_member_connection_rejected(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    outsider, outsider_token = make_user_and_token(db_session, "outsider")
    project_id = _create_project(client, owner_token)

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/projects/{project_id}?token={outsider_token}"):
            pass


def test_invalid_token_rejected(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/projects/{project_id}?token=garbage"):
            pass


def test_two_members_see_each_other_online_and_offline(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    member, member_token = make_user_and_token(db_session, "member")
    project_id = _create_project(client, owner_token)
    client.post(
        f"/projects/{project_id}/invite",
        json={"username": member.username},
        headers=auth_headers(owner_token),
    )

    with client.websocket_connect(f"/ws/projects/{project_id}?token={owner_token}") as ws1:
        data1 = ws1.receive_json()
        assert {u["username"] for u in data1["online_users"]} == {"owner"}

        with client.websocket_connect(f"/ws/projects/{project_id}?token={member_token}") as ws2:
            data2 = ws2.receive_json()
            assert {u["username"] for u in data2["online_users"]} == {"owner", "member"}

            data1_updated = ws1.receive_json()
            assert {u["username"] for u in data1_updated["online_users"]} == {
                "owner",
                "member",
            }

        data1_after_disconnect = ws1.receive_json()
        assert {u["username"] for u in data1_after_disconnect["online_users"]} == {"owner"}


def test_second_connection_from_same_user_replaces_first(client, db_session):
    # StrictMode 이중 마운트 레이스 재현: 같은 유저의 이전 연결이 아직 서버에
    # 끊긴 것으로 처리되기 전에 같은 유저가 새 연결을 또 연 상황.
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)

    with client.websocket_connect(f"/ws/projects/{project_id}?token={owner_token}") as ws1:
        data1 = ws1.receive_json()
        assert len(data1["online_users"]) == 1

        with client.websocket_connect(f"/ws/projects/{project_id}?token={owner_token}") as ws2:
            data2 = ws2.receive_json()
            assert len(data2["online_users"]) == 1
            assert data2["online_users"][0]["username"] == "owner"
