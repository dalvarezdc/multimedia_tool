"""Accounts, optional TOTP, OAuth start, and persistent generation history."""

import pyotp
import pytest
from starlette.testclient import TestClient
from src.server import create_app
from src.auth.store import AuthStore, is_proton_email


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MULTIMEDIA_UPLOADS_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("MULTIMEDIA_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("GITHUB_CLIENT_ID", raising=False)
    monkeypatch.delenv("GITHUB_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("PROTON_CLIENT_ID", raising=False)
    monkeypatch.delenv("PROTON_CLIENT_SECRET", raising=False)
    (tmp_path / "uploads").mkdir()
    (tmp_path / "data").mkdir()
    return TestClient(create_app())


def test_proton_email_domains():
    assert is_proton_email("ada@proton.me")
    assert is_proton_email("ada@pm.me")
    assert not is_proton_email("ada@gmail.com")


def test_register_login_logout_and_me(client):
    assert client.get("/api/auth/me").json()["authenticated"] is False
    res = client.post("/api/auth/register", json={
        "email": "ada@example.com",
        "password": "correct-horse",
        "display_name": "Ada",
    })
    assert res.status_code == 200
    assert res.json()["user"]["email"] == "ada@example.com"
    assert client.get("/api/auth/me").json()["authenticated"] is True
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").json()["authenticated"] is False
    bad = client.post("/api/auth/login", json={"email": "ada@example.com", "password": "nope-nope"})
    assert bad.status_code == 401
    ok = client.post("/api/auth/login", json={"email": "ada@example.com", "password": "correct-horse"})
    assert ok.status_code == 200
    assert ok.json()["status"] == "ok"


def test_register_rejects_short_password_and_duplicate(client):
    assert client.post("/api/auth/register", json={"email": "a@b.co", "password": "short"}).status_code == 422
    client.post("/api/auth/register", json={"email": "a@b.co", "password": "longenough"})
    dup = client.post("/api/auth/register", json={"email": "a@b.co", "password": "longenough"})
    assert dup.status_code == 400


def test_optional_totp_login(client):
    client.post("/api/auth/register", json={"email": "twofa@example.com", "password": "longenough"})
    setup = client.post("/api/auth/2fa/setup")
    assert setup.status_code == 200
    secret = setup.json()["secret"]
    assert setup.json()["qr_data_uri"].startswith("data:image/png")
    code = pyotp.TOTP(secret).now()
    assert client.post("/api/auth/2fa/enable", json={"code": code}).status_code == 200
    client.post("/api/auth/logout")
    first = client.post("/api/auth/login", json={"email": "twofa@example.com", "password": "longenough"})
    assert first.json()["status"] == "needs_2fa"
    assert client.get("/api/auth/me").json()["authenticated"] is False
    done = client.post("/api/auth/login/2fa", json={"code": pyotp.TOTP(secret).now()})
    assert done.status_code == 200
    assert client.get("/api/auth/me").json()["authenticated"] is True


def test_oauth_start_requires_config(client, monkeypatch):
    assert client.get("/api/auth/providers").json() == {"google": False, "github": False, "proton": False}
    assert client.get("/api/auth/oauth/google/start", follow_redirects=False).status_code == 400
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "gid")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "gsecret")
    res = client.get("/api/auth/oauth/google/start", follow_redirects=False)
    assert res.status_code == 302
    assert "accounts.google.com" in res.headers["location"]
    monkeypatch.setenv("GITHUB_CLIENT_ID", "gh")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "ghs")
    gh = client.get("/api/auth/oauth/github/start", follow_redirects=False)
    assert gh.status_code == 302
    assert "github.com/login/oauth/authorize" in gh.headers["location"]
    monkeypatch.setenv("PROTON_CLIENT_ID", "pr")
    monkeypatch.setenv("PROTON_CLIENT_SECRET", "prs")
    pr = client.get("/api/auth/oauth/proton/start", follow_redirects=False)
    assert pr.status_code == 302
    assert "proton.me" in pr.headers["location"]


def test_history_persists_for_user(tmp_path, monkeypatch):
    monkeypatch.setenv("MULTIMEDIA_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("MULTIMEDIA_UPLOADS_DIR", str(tmp_path / "uploads"))
    (tmp_path / "data").mkdir()
    (tmp_path / "uploads").mkdir()
    store = AuthStore(str(tmp_path / "data"))
    user = store.create_user("hist@example.com", "longenough")
    store.add_history(user["id"], {
        "title": "Hermes running",
        "prompt": "Hermes running",
        "model": "grok-imagine-image-quality",
        "mode": "image_generation",
        "media_type": "image",
        "path": "/renders/images/img_1.png",
        "elapsed_seconds": 12,
    })
    app = create_app()
    c1 = TestClient(app)
    c1.post("/api/auth/login", json={"email": "hist@example.com", "password": "longenough"})
    recs = c1.get("/api/history").json()["records"]
    assert recs[0]["elapsed_seconds"] == 12
    assert recs[0]["model"] == "grok-imagine-image-quality"
    c2 = TestClient(app)
    c2.post("/api/auth/login", json={"email": "hist@example.com", "password": "longenough"})
    recs2 = c2.get("/api/history").json()["records"]
    assert len(recs2) == 1


def test_guest_history_is_empty(client):
    data = client.get("/api/history").json()
    assert data["authenticated"] is False
    assert data["records"] == []


def test_ui_has_account_controls(client):
    html = client.get("/app").text
    assert "header-btn-account" in html
    assert "account-modal" in html
    assert "data-oauth=\"google\"" in html
    assert "data-oauth=\"github\"" in html
    assert "data-oauth=\"proton\"" in html
    assert "btn-2fa-setup" in html
