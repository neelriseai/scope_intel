"""Cart model for the checkout feature."""
from src.users.repository import find_user_by_email


class Cart:
    def __init__(self, user_email: str) -> None:
        self.user = find_user_by_email(user_email)
        self.items: list = []

    def add(self, sku: str, qty: int, price: float) -> None:
        self.items.append({"sku": sku, "qty": qty, "price": price})

    def total(self) -> float:
        return sum(it["qty"] * it["price"] for it in self.items)
