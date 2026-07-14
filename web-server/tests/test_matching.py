import importlib

import pytest

from .conftest import auth_headers, make_user_and_token, models

matching = importlib.import_module("web-server.matching")


def _create_project(client, owner_token: str) -> str:
    resp = client.post(
        "/projects", json={"name": "test"}, headers=auth_headers(owner_token)
    )
    return resp.json()["id"]


def _make_session(db_session, project_id: str, user_id: int) -> str:
    session = models.Session(project_id=project_id, user_id=user_id, status="processed")
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session.id


def test_cosine_similarity_identical_vectors_is_one():
    assert matching.cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_vectors_is_zero():
    assert matching.cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_hook_group_not_promoted_with_one_member(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)
    session_id = _make_session(db_session, project_id, owner.user_id)

    group = matching.match_hook_candidate(
        db_session, project_id, owner.user_id, session_id,
        "PostToolUse", "Bash", "npm test", "매번 실행함", "high",
    )
    assert group.promoted is False


def test_hook_group_promoted_at_two_distinct_members(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    member, member_token = make_user_and_token(db_session, "member")
    project_id = _create_project(client, owner_token)
    client.post(
        f"/projects/{project_id}/invite",
        json={"username": member.username},
        headers=auth_headers(owner_token),
    )
    session1 = _make_session(db_session, project_id, owner.user_id)
    session2 = _make_session(db_session, project_id, member.user_id)

    matching.match_hook_candidate(
        db_session, project_id, owner.user_id, session1,
        "PostToolUse", "Bash", "npm test", "r1", "high",
    )
    group = matching.match_hook_candidate(
        db_session, project_id, member.user_id, session2,
        "PostToolUse", "Bash", "npm  test", "r2", "high",  # 공백 차이는 정규화로 흡수
    )
    assert group.promoted is True
    assert group.event == "PostToolUse"
    assert group.matcher == "Bash"


def test_different_event_does_not_merge(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    member, member_token = make_user_and_token(db_session, "member")
    project_id = _create_project(client, owner_token)
    client.post(
        f"/projects/{project_id}/invite",
        json={"username": member.username},
        headers=auth_headers(owner_token),
    )
    session1 = _make_session(db_session, project_id, owner.user_id)
    session2 = _make_session(db_session, project_id, member.user_id)

    matching.match_hook_candidate(
        db_session, project_id, owner.user_id, session1,
        "PostToolUse", "Bash", "npm test", "r1", "high",
    )
    group2 = matching.match_hook_candidate(
        db_session, project_id, member.user_id, session2,
        "PreToolUse", "Bash", "npm test", "r2", "high",  # event가 다름 → 다른 그룹
    )
    assert group2.promoted is False


def test_same_user_reupload_does_not_double_count(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)
    session1 = _make_session(db_session, project_id, owner.user_id)
    session2 = _make_session(db_session, project_id, owner.user_id)

    matching.match_hook_candidate(
        db_session, project_id, owner.user_id, session1,
        "PostToolUse", "Bash", "npm test", "r1", "high",
    )
    group = matching.match_hook_candidate(
        db_session, project_id, owner.user_id, session2,
        "PostToolUse", "Bash", "npm test", "r2 (갱신됨)", "high",
    )
    assert group.promoted is False  # 여전히 1명


def test_claude_md_groups_by_similarity_not_exact_text(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    member, member_token = make_user_and_token(db_session, "member")
    project_id = _create_project(client, owner_token)
    client.post(
        f"/projects/{project_id}/invite",
        json={"username": member.username},
        headers=auth_headers(owner_token),
    )
    session1 = _make_session(db_session, project_id, owner.user_id)
    session2 = _make_session(db_session, project_id, member.user_id)

    vector = [1.0, 0.0, 0.0]
    similar_vector = [0.99, 0.01, 0.0]

    matching.match_claude_md_candidate(
        db_session, project_id, owner.user_id, session1,
        "스페이스로 들여쓰기 통일", vector, "r1", "high",
    )
    group = matching.match_claude_md_candidate(
        db_session, project_id, member.user_id, session2,
        "탭 대신 스페이스 써주세요", similar_vector, "r2", "medium",
    )
    assert group.promoted is True


def test_skill_groups_by_similarity_not_exact_text(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    member, member_token = make_user_and_token(db_session, "member")
    project_id = _create_project(client, owner_token)
    client.post(
        f"/projects/{project_id}/invite",
        json={"username": member.username},
        headers=auth_headers(owner_token),
    )
    session1 = _make_session(db_session, project_id, owner.user_id)
    session2 = _make_session(db_session, project_id, member.user_id)

    vector = [1.0, 0.0, 0.0]
    similar_vector = [0.99, 0.01, 0.0]

    matching.match_skill_candidate(
        db_session, project_id, owner.user_id, session1,
        "마이그레이션 후 시드와 재시작을 순서대로 진행한다", vector, "r1", "high",
    )
    group = matching.match_skill_candidate(
        db_session, project_id, member.user_id, session2,
        "DB 마이그레이션하고 시드 넣은 다음 서버를 재시작한다", similar_vector, "r2", "medium",
    )
    assert group.promoted is True
    assert group.type == "skill"


def test_skill_group_not_promoted_with_one_member(client, db_session):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project(client, owner_token)
    session_id = _make_session(db_session, project_id, owner.user_id)

    group = matching.match_skill_candidate(
        db_session, project_id, owner.user_id, session_id,
        "마이그레이션 후 시드와 재시작을 순서대로 진행한다", [1.0, 0.0], "r1", "high",
    )
    assert group.promoted is False
