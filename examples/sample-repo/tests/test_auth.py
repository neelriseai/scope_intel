"""Tests for auth feature."""
import pytest

from src.auth.login import _issue_token, validate_token, login


def test_issue_token_returns_hex():
    token = _issue_token("alice")
    assert len(token) == 64
    assert all(c in "0123456789abcdef" for c in token)


def test_validate_token_accepts_valid():
    token = _issue_token("bob")
    assert validate_token(token) is True


def test_validate_token_rejects_short():
    assert validate_token("short") is False
