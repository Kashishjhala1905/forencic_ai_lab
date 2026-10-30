import time

import jwt

from app.core.config import get_settings


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok" and "ocr" in r.json()


def test_register_login_me(client, make_user):
    u = make_user(email="alice@example.com")
    r = client.post("/api/auth/login", json={"email": "ALICE@example.com", "password": u.password})
    assert r.status_code == 200
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"}).json()
    assert me["email"] == "alice@example.com" and "password" not in str(me)


def test_duplicate_email_and_weak_password(client, make_user):
    u = make_user()
    assert client.post("/api/auth/register", json={"email": u.email, "name": "x", "password": "longenough1"}).status_code == 409
    r = client.post("/api/auth/register", json={"email": "new@example.com", "name": "x", "password": "short"})
    assert r.status_code == 422 and "8 characters" in r.json()["error"]["message"]


def test_wrong_password_rejected(client, user):
    r = client.post("/api/auth/login", json={"email": user.email, "password": "wrong-password"})
    assert r.status_code == 401 and "access_token" not in r.text


def test_password_is_hashed_in_db(client, user):
    from app.core.db import db
    with db() as c:
        h = c.execute("SELECT password_hash FROM users WHERE id=?", (user.id,)).fetchone()[0]
    assert h.startswith("$2") and user.password not in h


def test_protected_endpoints_reject_anonymous(client):
    for method, url in [("get", "/api/auth/me"), ("get", "/api/documents"), ("post", "/api/documents/upload"), ("get", "/api/documents/abc"),
                        ("delete", "/api/documents/abc"), ("post", "/api/documents/abc/analyze"), ("get", "/api/analysis/abc"),
                        ("get", "/api/analysis/abc/report"), ("get", "/api/dashboard/stats"), ("get", "/api/dashboard/recent"), ("get", "/api/admin/overview")]:
        assert getattr(client, method)(url).status_code == 401, url


def test_expired_and_forged_tokens(client, user):
    s = get_settings()
    expired = jwt.encode({"sub": user.id, "role": "user", "exp": int(time.time()) - 10}, s.jwt_secret, algorithm="HS256")
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401 and "expired" in r.json()["error"]["message"].lower()
    forged = jwt.encode({"sub": user.id, "role": "admin", "exp": int(time.time()) + 600}, "wrong-secret-wrong-secret-wrong-1234", algorithm="HS256")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_login_throttle(client, make_user):
    u = make_user()
    codes = [client.post("/api/auth/login", json={"email": u.email, "password": "bad-password"}).status_code for _ in range(7)]
    assert codes[:5] == [401] * 5 and codes[5] == 429
    assert client.post("/api/auth/login", json={"email": u.email, "password": u.password}).status_code == 429  # even correct pw is blocked during lockout


def test_admin_role_only_via_allowlist(client, make_user):
    assert client.get("/api/admin/overview", headers=make_user().h).status_code == 403
    admin = make_user(email="admin@example.com")
    r = client.get("/api/admin/overview", headers=admin.h)
    assert r.status_code == 200 and "counts" in r.json()


def test_change_password(client, make_user):
    u = make_user()
    assert client.post("/api/auth/change-password", headers=u.h, json={"current_password": "nope-nope-1", "new_password": "brand-new-pass1"}).status_code == 400
    assert client.post("/api/auth/change-password", headers=u.h, json={"current_password": u.password, "new_password": "brand-new-pass1"}).status_code == 200
    assert client.post("/api/auth/login", json={"email": u.email, "password": "brand-new-pass1"}).status_code == 200
