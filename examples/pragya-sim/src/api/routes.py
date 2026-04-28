"""Pragya API routes."""
import os
from src.core.engine import Engine

API_KEY = os.environ.get("PRAGYA_API_KEY", "")
engine = Engine()


def handle_prompt(prompt: str) -> dict:
    if not API_KEY:
        raise ValueError("PRAGYA_API_KEY not set")
    result = engine.run(prompt)
    return {"result": result, "model": engine.model}


def health() -> dict:
    return {"status": "ok", "model": engine.model}
