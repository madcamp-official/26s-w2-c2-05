from .conftest import auth_headers, make_user_and_token


def _create_project(client, owner_token: str) -> str:
    resp = client.post(
        "/projects", json={"name": "test"}, headers=auth_headers(owner_token)
    )
    return resp.json()["id"]


def _connect_owner_and_member(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    member, member_token = make_user_and_token(db_session, "member")
    project_id = _create_project(client, owner_token)
    client.post(
        f"/projects/{project_id}/invite",
        json={"username": member.username},
        headers=auth_headers(owner_token),
    )
    return project_id, owner_token, member_token


def test_saving_content_broadcasts_content_updated_to_other_connections(client, db_session):
    project_id, owner_token, member_token = _connect_owner_and_member(client, db_session)

    with client.websocket_connect(f"/ws/projects/{project_id}?token={owner_token}") as ws1:
        ws1.receive_json()  # owner sees itself online

        with client.websocket_connect(f"/ws/projects/{project_id}?token={member_token}") as ws2:
            ws2.receive_json()  # member sees online_users on connect
            ws1.receive_json()  # owner sees updated online_users (member joined)

            client.put(
                f"/projects/{project_id}",
                json={"content": "hello from owner"},
                headers=auth_headers(owner_token),
            )

            event = ws2.receive_json()
            assert event == {
                "type": "content_updated",
                "target": "content",
                "updated_by": "owner",
            }


def test_saving_hooks_broadcasts_content_updated_with_hooks_target(client, db_session):
    project_id, owner_token, member_token = _connect_owner_and_member(client, db_session)

    with client.websocket_connect(f"/ws/projects/{project_id}?token={owner_token}") as ws1:
        ws1.receive_json()

        with client.websocket_connect(f"/ws/projects/{project_id}?token={member_token}") as ws2:
            ws2.receive_json()
            ws1.receive_json()

            client.put(
                f"/projects/{project_id}/hooks",
                json={"hooks_content": '{"hooks": {}}'},
                headers=auth_headers(owner_token),
            )

            event = ws2.receive_json()
            assert event == {
                "type": "content_updated",
                "target": "hooks",
                "updated_by": "owner",
            }


def test_saving_content_does_not_break_when_no_one_else_connected(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)

    resp = client.put(
        f"/projects/{project_id}",
        json={"content": "solo edit"},
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 200


def test_sole_member_does_not_receive_own_save_as_content_updated_event(client, db_session):
    # 멤버가 한 명뿐인 프로젝트에서 본인이 저장해도 자기 자신에게는
    # "팀원이 저장했어요" 이벤트가 echo되면 안 된다 (혼자인데 "멤버가 업데이트
    # 중입니다" 안내가 뜨는 QA 버그 재현).
    owner, owner_token = make_user_and_token(db_session, "owner")
    member, member_token = make_user_and_token(db_session, "member")
    project_id = _create_project(client, owner_token)

    with client.websocket_connect(f"/ws/projects/{project_id}?token={owner_token}") as ws1:
        ws1.receive_json()  # owner sees itself online

        client.put(
            f"/projects/{project_id}",
            json={"content": "solo edit"},
            headers=auth_headers(owner_token),
        )

        # 저장 이벤트가 owner 자신에게 echo되지 않았다면, owner가 다음으로 받는
        # 메시지는 (뒤이어 member가 접속하며 발생하는) online_users 갱신이어야 한다.
        client.post(
            f"/projects/{project_id}/invite",
            json={"username": member.username},
            headers=auth_headers(owner_token),
        )
        with client.websocket_connect(
            f"/ws/projects/{project_id}?token={member_token}"
        ) as ws2:
            ws2.receive_json()  # member sees online_users on connect

            next_message = ws1.receive_json()
            assert next_message == {
                "online_users": [
                    {"user_id": owner.user_id, "username": "owner"},
                    {"user_id": member.user_id, "username": "member"},
                ]
            }
