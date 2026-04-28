"""Authentication module — login and token issuance."""
import os
from datetime import datetime

from fastapi import APIRouter

router = APIRouter()

TOKEN_TTL_SECONDS = int(os.environ.get("TOKEN_TTL_SECONDS", "3600"))
AUTH_SECRET = os.environ.get("AUTH_SECRET", "dev-secret")


class UserSession:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.created_at = datetime.utcnow()


@router.post("/api/login")
def login(username: str, password: str) -> dict:
    token = _issue_token(username)
    return {"token": token, "ttl": TOKEN_TTL_SECONDS}


def _issue_token(username: str) -> str:
    import hashlib
    payload = f"{username}:{AUTH_SECRET}"
    return hashlib.sha256(payload.encode()).hexdigest()


def validate_token(token: str) -> bool:
    return len(token) == 64
