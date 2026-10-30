import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..core.db import db, row_to_dict
from ..core.security import decode_token

bearer = HTTPBearer(auto_error=False)


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if not creds:
        raise HTTPException(401, "Authentication required.", headers={"WWW-Authenticate": "Bearer"})
    try:
        claims = decode_token(creds.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Session expired. Please log in again.", headers={"WWW-Authenticate": "Bearer"})
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid authentication token.", headers={"WWW-Authenticate": "Bearer"})
    with db() as c:
        u = row_to_dict(c.execute("SELECT id, email, name, role, created_at FROM users WHERE id=?", (claims["sub"],)).fetchone())
    if not u:
        raise HTTPException(401, "Account no longer exists.")
    return u


def admin_user(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(403, "Administrator access required.")
    return user


def owned_document(conn, document_id: str, user: dict) -> dict:
    """Return the document only if it belongs to the user. 404 (not 403) avoids revealing other users' IDs."""
    d = row_to_dict(conn.execute("SELECT * FROM documents WHERE id=? AND user_id=?", (document_id, user["id"])).fetchone())
    if not d:
        raise HTTPException(404, "Document not found.")
    return d


def owned_analysis(conn, analysis_id: str, user: dict) -> dict:
    a = row_to_dict(conn.execute("SELECT * FROM analyses WHERE id=? AND user_id=?", (analysis_id, user["id"])).fetchone())
    if not a:
        raise HTTPException(404, "Analysis not found.")
    return a


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"
