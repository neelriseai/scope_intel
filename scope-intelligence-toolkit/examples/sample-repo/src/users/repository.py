"""Users repository (in-memory mock for the sample)."""

_USERS = {
    "alice@example.com": {"id": "u1", "password_hash": "deadbeef"},
    "bob@example.com":   {"id": "u2", "password_hash": "cafef00d"},
}


def find_user_by_email(email: str) -> dict | None:
    return _USERS.get(email.lower())


def list_users() -> list:
    return list(_USERS.values())
