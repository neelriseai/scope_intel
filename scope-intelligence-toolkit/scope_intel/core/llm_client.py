"""LLM client — thin Ollama wrapper for structured extraction.

No external dependencies. Uses stdlib urllib only.

Design principle (from architecture discussion):
  Deterministic code is the substrate. LLM is the reasoning layer called AS A TOOL.
  Python does chunking, routing, writing, purity.
  Qwen is called only where classification or reasoning adds value.

Pluggable interface: replace OllamaClient with any class that implements:
    global_summary(excerpt: str) -> dict | None
    classify_chunk(chunk: dict, global_ctx: dict) -> dict | None
    module_map_pass(file_summaries: list[dict]) -> str | None
    is_available() -> bool

Both Mode B (LLM classifies, Python routes) and Mode A (full LLM) use this client.
Mode C (Python-only) does not use it at all.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Optional

# ---------------------------------------------------------------------------
# Prompt schemas — fixed JSON structures the LLM must produce
# ---------------------------------------------------------------------------

_GLOBAL_SUMMARY_SCHEMA = """\
{
  "project_name": "<name of the project>",
  "purpose": "<one sentence: what this system does>",
  "components": ["<component1>", "<component2>"],
  "tech_stack": ["<technology1>", "<technology2>"]
}"""

# Valid target_file values the LLM may choose:
_VALID_TARGETS = (
    "001-project-overview.md",
    "002-system-architecture.md",
    "003-deterministic-engine.md",
    "004-rag-layer.md",
    "005-memory-layer.md",
    "006-validation-engine.md",
    "007-skill-playbooks.md",
    "008-subagent-strategy.md",
    "009-schema-design.md",
    "mcp-contract.md",
    "roadmap.md",
    "constraints.md",
    "current-phase.md",
    "module-map.md",
    "skip",
)

_CHUNK_CLASSIFY_SCHEMA = """\
{
  "section_title": "<concise title for this section>",
  "category": "<one of: overview|module|constraint|decision|flow|roadmap|schema|current|api|skip>",
  "target_file": "<one of: 001-project-overview.md | 002-system-architecture.md | 003-deterministic-engine.md | 004-rag-layer.md | 005-memory-layer.md | 006-validation-engine.md | 007-skill-playbooks.md | 008-subagent-strategy.md | 009-schema-design.md | mcp-contract.md | roadmap.md | constraints.md | current-phase.md | module-map.md | skip>",
  "summary": "<1-2 sentence summary of what this section covers>",
  "tags": ["<tag1>", "<tag2>"],
  "importance": "<high | medium | low>",
  "key_facts": [
    {"fact": "<a concrete factual statement from this section>", "conf": 0.9}
  ],
  "constraints": ["<a must/should/never/always rule stated in this section>"],
  "is_feature": false,
  "feature_id": ""
}"""

# ---------------------------------------------------------------------------
# JSON extraction helper
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict | None:
    """Extract a JSON object from LLM response text.

    LLMs sometimes wrap JSON in markdown code fences or add commentary.
    We try direct parse first, then extract the outermost { } block.
    """
    if not text:
        return None
    # Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Strip markdown fences
    clean = re.sub(r"```(?:json)?\s*", "", text).strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass
    # Find outermost { } block
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return None


# ---------------------------------------------------------------------------
# Ollama client
# ---------------------------------------------------------------------------

class OllamaClient:
    """Calls a local Ollama instance for structured JSON extraction.

    Constructor args:
        model      — Ollama model tag, e.g. "qwen2.5:14b"
        url        — Ollama server base URL (default: http://localhost:11434)
        timeout    — HTTP timeout in seconds per request (default: 120)
        temperature — Sampling temperature (default: 0.1 — near-deterministic)
    """

    def __init__(
        self,
        model: str = "qwen2.5:14b",
        url: str = "http://localhost:11434",
        timeout: int = 120,
        temperature: float = 0.1,
    ) -> None:
        self.model = model
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.temperature = temperature

    # ------------------------------------------------------------------
    # Low-level generate
    # ------------------------------------------------------------------

    def _generate(self, prompt: str, system: str = "") -> str | None:
        """Send a generate request to Ollama. Returns response text or None."""
        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": 1024,
            },
        }
        if system:
            payload["system"] = system
        # Ask Ollama to return structured JSON when possible
        payload["format"] = "json"

        try:
            req = urllib.request.Request(
                f"{self.url}/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("response", "")
        except urllib.error.URLError:
            return None  # Ollama not reachable
        except Exception:  # noqa: BLE001
            return None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def global_summary(self, excerpt: str) -> dict | None:
        """Step 3A — Extract project-level metadata from the document intro.

        Feed the first ~3000 chars (title + TOC + intro section).
        Returns: {project_name, purpose, components[], tech_stack[]}
        or None if LLM call fails.
        """
        system = (
            "You extract structured metadata from technical design documents. "
            "Respond with valid JSON only. No commentary, no markdown fences."
        )
        prompt = (
            "Read this document excerpt and extract project metadata.\n\n"
            f"Document excerpt:\n{excerpt[:3000]}\n\n"
            f"Respond with this exact JSON structure:\n{_GLOBAL_SUMMARY_SCHEMA}"
        )
        response = self._generate(prompt, system)
        return _extract_json(response)

    def classify_chunk(self, chunk: dict, global_ctx: dict) -> dict | None:
        """Step 3B — Classify a single document chunk.

        chunk keys: heading_path, title, text, token_estimate
        global_ctx: output of global_summary() or fallback defaults

        Returns a dict matching _CHUNK_CLASSIFY_SCHEMA, or None on failure.
        The caller falls back to Python keyword routing on None.
        """
        project = global_ctx.get("project_name", "this project")
        components = ", ".join(global_ctx.get("components", [])) or "not specified"

        system = (
            f"You extract structured data from design documents. "
            f"Project: {project}. Known components: {components}. "
            f"Respond with valid JSON only. No commentary, no markdown fences."
        )
        # Inject heading_path so the model knows where in the doc this chunk lives
        prompt = (
            f"Classify this section from the design document.\n\n"
            f"Document location: {chunk.get('heading_path', chunk.get('title', ''))}\n\n"
            f"Section text:\n{chunk['text'][:2000]}\n\n"
            f"Respond with this exact JSON structure:\n{_CHUNK_CLASSIFY_SCHEMA}"
        )
        response = self._generate(prompt, system)
        result = _extract_json(response)
        if result is None:
            return None

        # Validate target_file is a known value — reject unknown to avoid junk files
        target = result.get("target_file", "skip")
        if target not in _VALID_TARGETS:
            # Best-effort: try to find the closest match
            result["target_file"] = "skip"
            result["_target_rejected"] = target

        return result

    def module_map_pass(self, file_summaries: list[dict]) -> str | None:
        """Step 5 (optional second pass) — Synthesise module-map.md.

        file_summaries: list of {title, summary} dicts from generated files.
        Returns markdown text for module-map.md, or None on failure.

        This is the only call that returns prose markdown rather than JSON.
        The format flag is NOT set here — we want markdown output.
        """
        if not file_summaries:
            return None

        summaries_text = "\n\n".join(
            f"### {s['title']}\n{s['summary']}"
            for s in file_summaries
        )
        system = (
            "You synthesise design documents into structured markdown. "
            "Respond with clean markdown only. No JSON, no commentary."
        )
        prompt = (
            "Based on these component summaries from a design document, "
            "generate a module-map.md that shows:\n"
            "1. Each module and its single-line responsibility\n"
            "2. Which modules depend on which (→ arrows)\n"
            "3. Any integration points (shared APIs, event buses, data stores)\n"
            "4. Any gaps or unclear ownership you notice\n\n"
            f"Component summaries:\n{summaries_text[:4000]}\n\n"
            "Generate the module map as clean markdown:"
        )
        # No format=json here — we want freeform markdown
        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": 2048},
        }
        try:
            req = urllib.request.Request(
                f"{self.url}/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("response", "").strip() or None
        except Exception:  # noqa: BLE001
            return None

    def is_available(self) -> bool:
        """Check Ollama is reachable and this model is loaded."""
        try:
            req = urllib.request.Request(
                f"{self.url}/api/tags",
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name", "") for m in data.get("models", [])]
                # Match by prefix (qwen2.5:14b matches "qwen2.5:14b-instruct-q4")
                return any(self.model.split(":")[0] in m for m in models)
        except Exception:  # noqa: BLE001
            return False


# ---------------------------------------------------------------------------
# Null client — used when mode=python or Ollama unavailable
# ---------------------------------------------------------------------------

class NullLLMClient:
    """Drop-in replacement that always returns None.

    Used when mode='python' is selected or Ollama is not available.
    The caller falls back to Python keyword routing on None.
    """

    def global_summary(self, excerpt: str) -> dict | None:  # noqa: ARG002
        return None

    def classify_chunk(self, chunk: dict, global_ctx: dict) -> dict | None:  # noqa: ARG002
        return None

    def module_map_pass(self, file_summaries: list[dict]) -> str | None:  # noqa: ARG002
        return None

    def is_available(self) -> bool:
        return False


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_client(
    mode: str = "python",
    model: str = "qwen2.5:14b",
    url: str = "http://localhost:11434",
) -> OllamaClient | NullLLMClient:
    """Return the right client for the requested mode.

    mode='python' → NullLLMClient (no LLM calls, zero overhead)
    mode='llm'    → OllamaClient (Qwen via Ollama)

    The caller should check client.is_available() if it needs to know
    whether the LLM is actually reachable.
    """
    if mode == "llm":
        return OllamaClient(model=model, url=url)
    return NullLLMClient()
