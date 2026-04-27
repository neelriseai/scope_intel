from src.auth.login import handle_login, LoginError
import pytest


def test_login_succeeds_for_known_user():
    res = handle_login("alice@example.com", "password")
    assert "token" in res or res["user_id"] == "u1"


def test_login_rejects_unknown_email():
    with pytest.raises(LoginError):
        handle_login("nobody@example.com", "x")
