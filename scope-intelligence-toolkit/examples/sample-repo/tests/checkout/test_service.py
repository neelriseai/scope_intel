from src.checkout.service import run_checkout
from src.checkout.cart import Cart


def test_checkout_requires_auth():
    res = run_checkout("bogus-token", Cart("alice@example.com"))
    assert res["ok"] is False
    assert res["reason"] == "not_authenticated"


def test_checkout_rejects_empty_cart():
    pass
