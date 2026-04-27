"""Checkout service — top-level entry for placing an order."""
from src.checkout.cart import Cart
from src.auth.session import get_user_for_token


def run_checkout(token: str, cart: Cart) -> dict:
    user_id = get_user_for_token(token)
    if user_id is None:
        return {"ok": False, "reason": "not_authenticated"}
    if not cart.items:
        return {"ok": False, "reason": "empty_cart"}
    return {"ok": True, "order_id": f"ord_{user_id}", "amount": cart.total()}
