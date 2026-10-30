import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request

from ..core.config import get_settings
from ..core.db import db, new_id, now, row_to_dict
from ..core.security import create_token, hash_password, throttle, verify_password
from ..schemas.auth import ChangePasswordIn, LoginIn, RegisterIn
from ..services.audit import audit
from .deps import client_ip, current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _public(u): return {k: u[k] for k in ("id", "email", "name", "role", "created_at")}


@router.post("/register", status_code=201)
def register(body: RegisterIn):
    email = body.email.lower()
    role = "admin" if email in get_settings().admin_list else "user"
    uid = new_id()
    try:
        with db() as c:
            c.execute("INSERT INTO users(id,email,name,password_hash,role,created_at) VALUES (?,?,?,?,?,?)",
                      (uid, email, body.name.strip(), hash_password(body.password), role, now()))
            audit(c, uid, "user_registered")
    except sqlite3.IntegrityError:
        raise HTTPException(409, "An account with this email already exists.")
    token, ttl = create_token(uid, role)
    return {"access_token": token, "token_type": "bearer", "expires_in": ttl,
            "user": {"id": uid, "email": email, "name": body.name.strip(), "role": role}}


@router.post("/login")
def login(body: LoginIn, request: Request):
    email = body.email.lower()
    key = f"{email}|{client_ip(request)}"
    if throttle.blocked(key):
        raise HTTPException(429, "Too many failed attempts. Try again in a few minutes.")
    with db() as c:
        u = row_to_dict(c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone())
        if not u or not verify_password(body.password, u["password_hash"]):
            throttle.fail(key)
            audit(c, u["id"] if u else None, "login_failed")
            c.commit()
            raise HTTPException(401, "Incorrect email or password.")
        audit(c, u["id"], "login")
    throttle.reset(key)
    token, ttl = create_token(u["id"], u["role"])
    return {"access_token": token, "token_type": "bearer", "expires_in": ttl, "user": _public(u)}


@router.get("/me")
def me(user: dict = Depends(current_user)):
    return _public(user)


@router.post("/change-password")
def change_password(body: ChangePasswordIn, user: dict = Depends(current_user)):
    with db() as c:
        u = row_to_dict(c.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone())
        if not verify_password(body.current_password, u["password_hash"]):
            raise HTTPException(400, "Current password is incorrect.")
        c.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(body.new_password), user["id"]))
        audit(c, user["id"], "password_changed")
    return {"ok": True}
