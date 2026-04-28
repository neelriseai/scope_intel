"""Pragya core engine."""
import os

MODEL_NAME = os.environ.get("PRAGYA_MODEL", "claude-sonnet-4-6")
MAX_TOKENS = int(os.environ.get("PRAGYA_MAX_TOKENS", "8192"))


class Engine:
    def __init__(self, model: str = MODEL_NAME):
        self.model = model

    def run(self, prompt: str) -> str:
        return f"[{self.model}] {prompt}"

    def validate(self, response: str) -> bool:
        return len(response) > 0
