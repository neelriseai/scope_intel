"""Tests for billing feature."""
import pytest

from src.billing.payment import PaymentService, get_payment_service
from src.auth.login import _issue_token


@pytest.fixture
def svc():
    return get_payment_service()


def test_charge_valid(svc):
    token = _issue_token("alice")
    result = svc.charge(token, 100.0)
    assert result["status"] == "charged"


def test_charge_exceeds_limit(svc):
    token = _issue_token("bob")
    with pytest.raises(ValueError, match="exceeds limit"):
        svc.charge(token, 999_999.0)


def test_refund(svc):
    token = _issue_token("alice")
    result = svc.refund(token, "ch_123")
    assert result["status"] == "refunded"
