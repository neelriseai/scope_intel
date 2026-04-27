"""Billing — payment processing."""
import os

from src.auth.login import validate_token

PAYMENT_TIMEOUT_MS = int(os.environ.get("PAYMENT_TIMEOUT_MS", "5000"))
MAX_AMOUNT = float(os.environ.get("PAYMENT_MAX_AMOUNT", "10000"))


class PaymentService:
    def charge(self, token: str, amount: float) -> dict:
        if not validate_token(token):
            raise ValueError("invalid token")
        if amount > MAX_AMOUNT:
            raise ValueError(f"amount exceeds limit {MAX_AMOUNT}")
        return {"status": "charged", "amount": amount}

    def refund(self, token: str, charge_id: str) -> dict:
        if not validate_token(token):
            raise ValueError("invalid token")
        return {"status": "refunded", "charge_id": charge_id}


def get_payment_service() -> PaymentService:
    return PaymentService()
