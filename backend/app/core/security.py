import time
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import get_settings

ALGO = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def create_token(user_id: str, role: str) -> tuple[str, int]:
    s = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(minutes=s.jwt_expire_minutes)
    token = jwt.encode({"sub": user_id, "role": role, "exp": exp}, s.jwt_secret, algorithm=ALGO)
    return token, s.jwt_expire_minutes * 60


def decode_token(token: str) -> dict:
    return jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGO], options={"require": ["exp", "sub"]})


class LoginThrottle:
    """In-memory throttle: max N failed logins per key within a window (single-process only)."""

    def __init__(self):
        self.fails: dict[str, list[float]] = {}

    def _recent(self, key):
        w = get_settings().login_window_seconds
        t = time.time()
        self.fails[key] = [x for x in self.fails.get(key, []) if t - x < w]
        return self.fails[key]

    def blocked(self, key: str) -> bool:
        return len(self._recent(key)) >= get_settings().login_max_attempts

    def fail(self, key: str):
        self._recent(key).append(time.time())

    def reset(self, key: str):
        self.fails.pop(key, None)


throttle = LoginThrottle()
