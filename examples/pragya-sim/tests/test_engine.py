"""Tests for Pragya engine."""
import pytest
from src.core.engine import Engine


def test_run_returns_string():
    e = Engine()
    assert isinstance(e.run("hello"), str)


def test_validate_nonempty():
    e = Engine()
    assert e.validate("some output") is True


def test_validate_empty():
    e = Engine()
    assert e.validate("") is False
