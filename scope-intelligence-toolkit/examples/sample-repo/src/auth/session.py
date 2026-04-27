"""Session creation + lookup."""
import secrets

_SESSIONS: dict = {}


def create_session(user_id: str) -> str:
    token = secrets.token_hex(16)
    _SESSIONS[token] = user_id
    return token


def get_user_for_token(token: str) -> str | None:
    return _SESSIONS.get(token)
