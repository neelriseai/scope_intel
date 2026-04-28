"""Frontend API client."""
import os

API_BASE = os.environ.get("API_BASE", "http://localhost:8000")
API_TIMEOUT_MS = int(os.environ.get("API_TIMEOUT_MS", "3000"))


def post_login(username: str, password: str) -> dict:
    import urllib.request, json
    body = json.dumps({"username": username, "password": password}).encode()
    req = urllib.request.Request(f"{API_BASE}/api/login", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=API_TIMEOUT_MS / 1000) as r:
        return json.loads(r.read())


def post_charge(token: str, amount: float) -> dict:
    import urllib.request, json
    body = json.dumps({"token": token, "amount": amount}).encode()
    req = urllib.request.Request(f"{API_BASE}/api/billing/charge", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=API_TIMEOUT_MS / 1000) as r:
        return json.loads(r.read())
