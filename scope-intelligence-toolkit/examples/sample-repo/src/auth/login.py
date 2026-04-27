"""Login handler for the sample auth feature — Flask-style routes."""
import os
from src.auth.session import create_session
from src.users.repository import find_user_by_email

app = None  # injected by the app factory; defined here for decorator resolution

AUTH_SECRET = os.environ.get("AUTH_SECRET", "dev-secret")
TOKEN_TTL = int(os.environ.get("TOKEN_TTL_SECONDS", "3600"))


class LoginError(Exception):
    pass


# Simulate Flask-style route decorator
class _Router:
    def post(self, path):
        def deco(fn): return fn
        return deco
router = _Router()


@router.post("/api/login")
def handle_login(email: str, password: str) -> dict:
    user = find_user_by_email(email)
    if user is None:
        raise LoginError("unknown user")
    if not _check_password(user, password):
        raise LoginError("bad password")
    token = create_session(user["id"])
    return {"user_id": user["id"], "token": token}


@router.post("/api/logout")
def handle_logout(token: str) -> dict:
    return {"ok": True}


def _check_password(user: dict, password: str) -> bool:
    return user.get("password_hash") == _hash(password)


def _hash(value: str) -> str:
    import hashlib
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
