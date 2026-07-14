import importlib

from .conftest import auth_headers, make_user_and_token

ai_client = importlib.import_module("web-server.ai_client")


def test_get_quota_returns_remaining_rpd(client, db_session, monkeypatch):
    async def fake_get_remaining_rpd(client=None):
        return 342

    monkeypatch.setattr(ai_client, "get_remaining_rpd", fake_get_remaining_rpd)
    _, token = make_user_and_token(db_session, "owner")

    resp = client.get("/quota", headers=auth_headers(token))

    assert resp.status_code == 200
    assert resp.json() == {"remaining_rpd": 342}


def test_get_quota_requires_login(client, db_session):
    resp = client.get("/quota")
    assert resp.status_code == 401
