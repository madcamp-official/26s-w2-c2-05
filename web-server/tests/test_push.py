from .conftest import auth_headers, make_user_and_token, models

import importlib

github_client = importlib.import_module("web-server.github_client")


def _create_project_with_repo_and_token(client, db_session, owner_token: str, owner) -> str:
    resp = client.post(
        "/projects", json={"name": "test"}, headers=auth_headers(owner_token)
    )
    project_id = resp.json()["id"]
    client.put(
        f"/projects/{project_id}/github",
        json={"repo": "octocat/hello-world"},
        headers=auth_headers(owner_token),
    )
    owner.github_token_encrypted = github_client.encrypt_token("gh-token")
    db_session.add(owner)
    db_session.commit()
    return project_id


def test_push_sends_both_claude_md_and_hooks(client, db_session, monkeypatch):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project_with_repo_and_token(client, db_session, owner_token, owner)

    calls = []

    def fake_push_file(token, repo, path, content, message):
        calls.append(path)

    monkeypatch.setattr(github_client, "push_file", fake_push_file)

    resp = client.post(f"/projects/{project_id}/push", headers=auth_headers(owner_token))
    assert resp.status_code == 200
    assert calls == ["CLAUDE.md", ".claude/settings.json"]


def test_push_with_invalid_hooks_json_returns_400_and_skips_push(
    client, db_session, monkeypatch
):
    owner, owner_token = make_user_and_token(db_session, "owner")
    project_id = _create_project_with_repo_and_token(client, db_session, owner_token, owner)

    project = db_session.get(models.Project, project_id)
    project.hooks_content = "not valid json"
    db_session.add(project)
    db_session.commit()

    calls = []

    def fake_push_file(token, repo, path, content, message):
        calls.append(path)

    monkeypatch.setattr(github_client, "push_file", fake_push_file)

    resp = client.post(f"/projects/{project_id}/push", headers=auth_headers(owner_token))
    assert resp.status_code == 400
    assert calls == []


def test_push_without_repo_still_returns_400(client, db_session, monkeypatch):
    owner, owner_token = make_user_and_token(db_session, "owner")
    resp = client.post(
        "/projects", json={"name": "test"}, headers=auth_headers(owner_token)
    )
    project_id = resp.json()["id"]

    calls = []
    monkeypatch.setattr(
        github_client, "push_file", lambda **kwargs: calls.append(kwargs)
    )

    resp = client.post(f"/projects/{project_id}/push", headers=auth_headers(owner_token))
    assert resp.status_code == 400
    assert calls == []
