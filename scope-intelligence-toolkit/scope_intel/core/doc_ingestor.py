"""Document ingestion — parse design docs and auto-generate .ai-context/ files.

Two extraction modes (selected via mode= parameter):

  mode='python'  (default, Option C)
      Pure keyword routing — fast, no external dependencies.
      Splits by headings, routes sections by regex keyword matching.
      Memory extraction via regex patterns (uses/is/must/decided).
      Falls back gracefully on any doc format.

  mode='llm'  (Option B — LLM classifies, Python writes)
      5-step pipeline:
        1. Parse → plain text (doc_reader)
        2. Smart chunk with heading_path (doc_reader.read_document_structured)
        3. Global summary pass — single Qwen call → {project_name, components}
        4. Per-chunk classification — Qwen call per chunk
               → {target_file, key_facts, constraints, is_feature, feature_id}
           Python regex routing used as fallback if Qwen returns None.
        5. Aggregate chunks by target_file → write .ai-context/ files
        6. Optional second pass — Qwen synthesises module-map.md from summaries
      Post-ingest: Swan purity pass → detect_conflicts() on new memories.

Both modes write the same output structure.
Both modes produce comparable results — switch --mode to compare.

Architecture note (from framework discussion):
  Deterministic code is the substrate. Qwen is called AS A TOOL.
  Python handles chunking, routing, writing, and purity.
  Qwen handles classification and reasoning where it adds real value.
  If Ollama is unavailable in mode=llm, falls back to Python routing per chunk.

Reads a design document (PDF / DOCX / MD / TXT) and produces:

  .ai-context/
  ├── generated/
  │   ├── 001-project-overview.md
  │   ├── 002-system-architecture.md
  │   ├── 003-<component>.md  …  009-<component>.md
  │   ├── mcp-contract.md
  │   ├── roadmap.md
  │   ├── claude-code-integration.md
  │   ├── symbol-schema.md
  │   └── index.json              ← manifest consumed by MCP server
  └── curated/
      ├── current-phase.md
      ├── constraints.md
      └── module-map.md

Also populates:
  .scope-intelligence/mempalace.jsonl  ← semantic memories (confidence 0.7-0.85)
  .scope-intelligence/features.json   ← planned feature stubs (no files yet)
  CLAUDE.md at repo root              ← updated to reference generated docs

Routing works by matching each section header (and a snippet of its body)
against keyword patterns.  Unmatched sections are listed in the result so the
caller knows what was skipped.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Optional

from . import store
from .mempalace import add_memory, detect_conflicts


# ---------------------------------------------------------------------------
# Source document hash helper
# ---------------------------------------------------------------------------

def _doc_hash(doc_path: Path) -> str:
    """Compute a short SHA-256 fingerprint of the source document.

    Returns the first 16 hex characters (64-bit) — collision-safe for our use case.
    Used to detect when a source doc has changed since the last ingest run.
    """
    h = hashlib.sha256()
    try:
        with open(doc_path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()[:16]


def _read_index_hash(repo_root: Path) -> str:
    """Read the stored source_hash from .ai-context/generated/index.json (or '')."""
    index_path = repo_root / ".ai-context" / "generated" / "index.json"
    if not index_path.exists():
        return ""
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
        return data.get("source_hash", "")
    except Exception:  # noqa: BLE001
        return ""


# ---------------------------------------------------------------------------
# Memory dedup helper
# ---------------------------------------------------------------------------

def _existing_memory_notes(repo_root: Path) -> set[str]:
    """Return a set of lowercased note texts already in mempalace.jsonl.

    Used to skip memories that were stored in a previous ingest run so
    re-ingesting the same document doesn't create duplicate entries.
    Reads the JSONL file directly (no full list_memories() call) for speed.
    """
    mp_path = store.mempalace_path(repo_root)
    if not mp_path.exists():
        return set()
    notes: set[str] = set()
    try:
        for line in mp_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                note = entry.get("note", "")
                if note:
                    notes.add(note.lower())
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    return notes

# ---------------------------------------------------------------------------
# Progress helper — writes to stderr so JSON stdout stays clean
# ---------------------------------------------------------------------------

def _progress(msg: str, *, end: str = "\n") -> None:
    """Print a progress message to stderr.

    Uses end='\r' for in-place updates (chunk-by-chunk progress bar).
    Uses end='\n' (default) for milestone lines that should persist.
    Only writes when stderr is a real terminal — stays silent in CI/pipes.
    """
    if sys.stderr.isatty():
        # Pad to 80 chars so \r overwrites previous longer lines cleanly
        padded = msg.ljust(80) if end == "\r" else msg
        sys.stderr.write(padded + end)
        sys.stderr.flush()

# ---------------------------------------------------------------------------
# Routing tables
# ---------------------------------------------------------------------------

# Each entry: (regex_pattern, numbered_prefix_or_None, filename_slug)
#
# ROUTING ORDER MATTERS:
#   _route_section() checks CURATED routes FIRST (they have very distinctive
#   heading names and rarely produce false positives), then GENERATED.
#   This prevents generated routes from stealing a "Constraints" section just
#   because its body happens to mention "validation" or "architecture".
#
#   Within GENERATED_ROUTES: more specific patterns must come BEFORE broad ones.
#   '\blayer\b' is intentionally ABSENT from the architecture route — it is too
#   broad and would match "memory layer", "rag layer", etc.

GENERATED_ROUTES: list[tuple] = [
    # --- Highly specific / low false-positive risk — check first ---
    # Roadmap: "\broadmap\b" is unique; "milestone", "phase plan" are specific
    (r"\broadmap\b|\bphase plan\b|\bmilestone\b|\brelease plan\b|\bbacklog\b|\bsprint", None, "roadmap"),
    # RAG: very distinctive vocabulary
    (r"\brag\b|\bretrieval.augmented\b|\bvector store\b|\bembedding\b|\bsemantic search\b", "004", "rag-layer"),
    # Skills / playbooks
    (r"\bskill\b|\bplaybook\b|\bworkflow\b|\bprocedure\b|\brecipe\b|\bstep.by.step", "007", "skill-playbooks"),
    # Subagents: multi-agent is specific
    (r"\bsubagent\b|\bmulti.agent\b|\bdelegat\b|\bcoordinat\b|\borchestrat", "008", "subagent-strategy"),
    # Claude / MCP integration
    (r"\bclaude.code\b|\bclaude integration\b|\bslash command\b|\bhook\b|\bmcp server\b", None, "claude-code-integration"),
    # MCP contract / API — specific keywords
    (r"\bmcp contract\b|\bapi contract\b|\bjson.rpc\b|\brpc method\b|\bmethod signature\b|\btool schema\b", None, "mcp-contract"),
    # Symbol schema — very specific terms
    (r"\bsymbol schema\b|\btype definition\b|\bdata type system\b|\binterface definition\b", None, "symbol-schema"),
    # --- Moderately specific compound patterns ---
    (r"\boverview\b|\bintroduction\b|\babout\b|\bpurpose\b|\bwhat is\b|\bproject goal", "001", "project-overview"),
    (r"\barchitecture\b|\bsystem design\b|\bhigh.level\b|\bcomponent overview\b", "002", "system-architecture"),
    # Deterministic engine — require compound phrase or specific word, not bare "engine"
    (r"\bdeterministic engine\b|\bdeterministic layer\b|\bcore engine\b|\bdeterministic\b|\bprocessor\b", "003", "deterministic-engine"),
    # Memory layer — compound phrase first, then broad "memory"
    (r"\bmemory layer\b|\bmemory store\b|\bstorage layer\b|\bpersistence layer\b|\bmempalace\b|\bknowledge store\b|\bcache layer\b", "005", "memory-layer"),
    # Validation engine — compound phrase first
    (r"\bvalidation engine\b|\bvalidation layer\b|\bguardrail\b|\btesting strategy\b|\bverif", "006", "validation-engine"),
    # Schema design
    (r"\bschema\b|\bdata model\b|\bdata structure\b|\btype system\b|\bjson schema\b|\bpayload", "009", "schema-design"),
    # --- Broad single-word fallbacks (lowest priority) ---
    (r"\bmemory\b|\bstorage\b|\bpersistence\b|\bcache\b", "005", "memory-layer"),
    (r"\bvalidation\b", "006", "validation-engine"),
    (r"\bapi\b|\bcontract\b|\bmcp\b|\brpc\b|\bendpoint\b|\bprotocol", None, "mcp-contract"),
    (r"\bagent\b", "008", "subagent-strategy"),
    (r"\bengine\b|\bpipeline\b", "003", "deterministic-engine"),
    (r"\bsymbol\b|\bdata type\b", None, "symbol-schema"),
    (r"\bchunk\b|\bvector\b", "004", "rag-layer"),
]

CURATED_ROUTES: list[tuple] = [
    # constraints? — matches both "constraint" (singular) and "constraints" (plural)
    (r"\bconstraints?\b|\brules?\b|\bprinciples?\b|\bmust not\b|\bshould not\b|\bavoid\b|\bnever\b|\bgolden rule", "constraints"),
    (r"\bcurrent phase\b|\bactive phase\b|\bin progress\b|\bnow building\b|\bcurrent sprint\b|\bthis iteration\b", "current-phase"),
    (r"\bmodule map\b|\bfile structure\b|\bdirectory layout\b|\bfile map\b|\bcode map\b|\bmodule breakdown", "module-map"),
]

# ---------------------------------------------------------------------------
# Target file map — used by mode=llm to convert LLM target_file → disk path
# ---------------------------------------------------------------------------

# (dest_dir, numbered_prefix_or_None, slug)
TARGET_FILE_MAP: dict[str, tuple] = {
    "001-project-overview.md":       ("generated", "001", "project-overview"),
    "002-system-architecture.md":    ("generated", "002", "system-architecture"),
    "003-deterministic-engine.md":   ("generated", "003", "deterministic-engine"),
    "004-rag-layer.md":              ("generated", "004", "rag-layer"),
    "005-memory-layer.md":           ("generated", "005", "memory-layer"),
    "006-validation-engine.md":      ("generated", "006", "validation-engine"),
    "007-skill-playbooks.md":        ("generated", "007", "skill-playbooks"),
    "008-subagent-strategy.md":      ("generated", "008", "subagent-strategy"),
    "009-schema-design.md":          ("generated", "009", "schema-design"),
    "mcp-contract.md":               ("generated", None,  "mcp-contract"),
    "roadmap.md":                    ("generated", None,  "roadmap"),
    "claude-code-integration.md":    ("generated", None,  "claude-code-integration"),
    "symbol-schema.md":              ("generated", None,  "symbol-schema"),
    "constraints.md":                ("curated",   None,  "constraints"),
    "current-phase.md":              ("curated",   None,  "current-phase"),
    "module-map.md":                 ("curated",   None,  "module-map"),
}


# ---------------------------------------------------------------------------
# Memory extraction
# ---------------------------------------------------------------------------

_USES_RE = re.compile(
    r"([\w][\w\s\-]{2,30}?)\s+uses?\s+([\w][\w\s\-]{2,40}?)(?:[.,;\n]|$)", re.I
)
_IS_RE = re.compile(
    r"([\w][\w\s\-]{2,30}?)\s+is\s+(?:a\s+|an\s+)?([\w][\w\s\-,]{5,60}?)(?:[.,;\n]|$)", re.I
)
_MUST_RE = re.compile(
    r"\b(?:must|should|always|never)\s+([^.,;\n]{10,100}?)(?:[.,;\n]|$)", re.I
)
_DECISION_RE = re.compile(
    r"\b(?:we chose|we use|we decided|adopted|selected)\s+([^.,;\n]{5,80}?)(?:[.,;\n]|$)", re.I
)

_STOP_WORDS = {"the", "a", "an", "this", "that", "it", "is", "are", "was",
               "be", "been", "have", "has", "do", "does", "for", "of", "in",
               "to", "and", "or", "not", "no", "all", "each", "any", "its"}


def _extract_memories(text: str, source_tag: str) -> list[dict]:
    """Pull key facts from free text. Returns list of {type, note, confidence}."""
    memories: list[dict] = []
    seen: set[str] = set()

    def _add(note: str, conf: float, kind: str = "semantic") -> None:
        note = re.sub(r"\s+", " ", note).strip(" .,;")
        if len(note) < 12 or note.lower() in seen:
            return
        words = set(note.lower().split()) - _STOP_WORDS
        if len(words) < 2:
            return
        seen.add(note.lower())
        memories.append({"type": kind, "note": note, "confidence": conf,
                         "tags": ["doc-ingest", source_tag]})

    for m in _USES_RE.finditer(text):
        _add(f"{m.group(1).strip()} uses {m.group(2).strip()}", 0.75)

    for m in _IS_RE.finditer(text):
        _add(f"{m.group(1).strip()} is {m.group(2).strip()}", 0.70)

    for m in _MUST_RE.finditer(text):
        _add(f"Constraint: {m.group(1).strip()}", 0.85)

    for m in _DECISION_RE.finditer(text):
        _add(f"Decision: {m.group(1).strip()}", 0.80, "decision")

    return memories[:60]  # cap to keep mempalace clean


# ---------------------------------------------------------------------------
# Feature stub extraction
# ---------------------------------------------------------------------------

_SKIP_GENERIC = {
    "overview", "introduction", "about", "architecture", "constraints",
    "roadmap", "schema", "api", "contract", "summary", "conclusion",
    "module map", "appendix", "references", "background", "motivation",
    "current phase", "active phase", "glossary",
}


def _extract_features(sections: list[dict]) -> list[dict]:
    """Extract plausible feature/component names from section headers."""
    features: list[dict] = []
    seen: set[str] = set()

    for s in sections:
        title = s["title"].strip()
        title_lower = title.lower()

        if any(g in title_lower for g in _SKIP_GENERIC):
            continue
        if len(title) < 3 or len(title) > 60:
            continue
        # Only consider sections that look like component names
        # (have at least one content-bearing word)
        words = set(title_lower.split()) - _STOP_WORDS
        if not words:
            continue

        slug = re.sub(r"[^a-z0-9]+", "-", title_lower).strip("-")
        if slug and slug not in seen:
            seen.add(slug)
            features.append({
                "id": slug,
                "title": title,
                "source": "doc_ingest",
                "files": [],
                "file_count": 0,
                "symbol_count": 0,
                "languages": [],
                "symbols": [],
                "aliases": [slug],
                "depends_on_features": [],
                "entry_points": [],
            })

    return features


# ---------------------------------------------------------------------------
# Section parsing
# ---------------------------------------------------------------------------

def _split_sections(text: str) -> list[dict]:
    """Split document into sections by markdown-style headers (# / ## / ###)."""
    sections: list[dict] = []
    current: dict = {"level": 0, "title": "(preamble)", "body": []}

    for line in text.splitlines():
        m = re.match(r"^(#{1,4})\s+(.+)$", line)
        if m:
            body_text = "\n".join(current["body"]).strip()
            if current["title"] or body_text:
                current["body_text"] = body_text
                sections.append(current)
            current = {
                "level": len(m.group(1)),
                "title": m.group(2).strip(),
                "body": [],
            }
        else:
            current["body"].append(line)

    body_text = "\n".join(current["body"]).strip()
    if current["title"] or body_text:
        current["body_text"] = body_text
        sections.append(current)

    return sections


# Route override comment — <!-- route: constraints --> in the section body
# forces that section to go to the named target regardless of keyword routing.
_ROUTE_OVERRIDE_RE = re.compile(r"<!--\s*route:\s*([\w-]+)\s*-->", re.I)

# Build fast lookup tables from routes: slug → (dest_type, prefix, slug)
_SLUG_TO_CURATED:   dict[str, tuple] = {slug: ("curated",   None,   slug) for _, slug in CURATED_ROUTES}
_SLUG_TO_GENERATED: dict[str, tuple] = {slug: ("generated", prefix, slug) for _, prefix, slug in GENERATED_ROUTES}


def _route_section(title: str, body_snippet: str) -> tuple[str | None, str | None, str | None]:
    """Decide where a section goes.

    Returns (dest_type, prefix, slug):
      dest_type : 'generated' | 'curated' | None
      prefix    : '001' … '009' | None
      slug      : filename stem (without extension)

    Lookup order:
      0. Explicit <!-- route: slug --> comment in body  (user override)
      1. CURATED routes — distinctive headings, nearly zero false positives
      2. GENERATED routes — keyword regex, specific patterns first

    Curated routes checked before generated so a 'Constraints' section
    whose body mentions 'validation' isn't stolen by the validation route.
    """
    # 0. Manual override
    m = _ROUTE_OVERRIDE_RE.search(body_snippet[:500])
    if m:
        target = m.group(1).lower()
        if target in _SLUG_TO_CURATED:
            return _SLUG_TO_CURATED[target]
        if target in _SLUG_TO_GENERATED:
            return _SLUG_TO_GENERATED[target]
        # Unknown slug in override comment — fall through to normal routing

    combined = (title + " " + body_snippet[:300]).lower()

    # 1. Curated first — distinctive headings, nearly zero false positives
    for pattern, slug in CURATED_ROUTES:
        if re.search(pattern, combined, re.I):
            return "curated", None, slug

    # 2. Generated — longer list, some broad patterns at the end
    for pattern, prefix, slug in GENERATED_ROUTES:
        if re.search(pattern, combined, re.I):
            return "generated", prefix, slug

    return None, None, None


def _suggest_route(title: str, body_snippet: str) -> str | None:
    """For an unmatched section, find the closest route and return a hint.

    Counts how many alternates in each route pattern word-match the combined
    title+body text.  Returns a human-readable suggestion string or None.
    """
    combined = (title + " " + body_snippet[:300]).lower()
    best_score = 0
    best_hint: str | None = None

    for pattern, _, slug in GENERATED_ROUTES:
        alternates = [a.strip() for a in pattern.split(r"|")]
        hits = sum(1 for a in alternates if re.search(a, combined, re.I))
        if hits > best_score:
            best_score = hits
            # Pick first readable keyword (strip regex anchors)
            kw = re.sub(r"\\b|\\.|\^|\$|\(|\)", "", alternates[0]).strip()
            best_hint = f"add '{kw}' to the heading → routes to {slug}.md"

    for pattern, slug in CURATED_ROUTES:
        alternates = [a.strip() for a in pattern.split(r"|")]
        hits = sum(1 for a in alternates if re.search(a, combined, re.I))
        if hits > best_score:
            best_score = hits
            kw = re.sub(r"\\b|\\.|\^|\$|\(|\)", "", alternates[0]).strip()
            best_hint = f"add '{kw}' to the heading → routes to curated/{slug}.md"

    return best_hint if best_score > 0 else None


# ---------------------------------------------------------------------------
# Curated file templates
# ---------------------------------------------------------------------------

_CURATED_TEMPLATES: dict[str, str] = {
    "constraints.md": """\
# Constraints

<!-- scope-intel: curated — edit this file to define project rules for Claude. -->
<!-- Add <!-- route: constraints --> to any section in your design doc to auto-populate. -->

## Non-negotiable Rules

- TODO: List what Claude must NEVER do in this codebase
- Example: Never commit secrets or credentials to git
- Example: Always run tests before suggesting a file is complete

## Code Style

- TODO: Add language/style conventions
- Example: Python — PEP 8, type hints required on all public functions
- Example: Max line length 100 chars

## Architecture Constraints

- TODO: Add structural rules
- Example: No direct DB access outside the `repositories/` layer
- Example: All public API endpoints must be rate-limited

---
> Template created by `scope doc ingest`. Fill in your project constraints.
> Claude reads this file before every session to understand what to avoid.
""",

    "current-phase.md": """\
# Current Phase

<!-- scope-intel: curated — update this file whenever the active sprint changes. -->
<!-- Add <!-- route: current-phase --> to a section in your design doc to auto-populate. -->

## Now Building

- TODO: What feature/milestone is in active development right now?
- Example: Phase 2 — RAG layer with pdfplumber + Ollama embedding

## In Progress

- [ ] TODO: List active work items
- [ ] Example: Implement chunked PDF ingestion
- [ ] Example: Wire vector store to query engine

## Done This Phase

- TODO: What was completed recently?
- Example: Phase 1 — core scope index (files, symbols, features)

## Blocked / Waiting

- TODO: Any blockers or external dependencies?

## Next Up

- TODO: What comes after the current phase?

---
> Template created by `scope doc ingest`. Keep this file up to date as work progresses.
> Claude reads this to understand what you are currently building.
""",

    "module-map.md": """\
# Module Map

<!-- scope-intel: curated — document your file/module ownership map here. -->
<!-- Add <!-- route: module-map --> to a section in your design doc to auto-populate. -->

## Core Modules

| Module | Path | Owner | Purpose |
|--------|------|-------|---------|
| TODO   | src/ | team  | Main source |

## Layer Ownership

- **API layer** — `src/api/`  — handles HTTP requests, auth, rate limiting
- **Service layer** — `src/services/` — business logic, orchestration
- **Data layer** — `src/repositories/` — DB access, external APIs

## Key Files

- TODO: List files Claude should know about
- Example: `src/core/engine.py` — central processing pipeline

## File Naming Conventions

- TODO: How are files named in this project?
- Example: snake_case for Python, PascalCase for classes

---
> Template created by `scope doc ingest`. Fill in the module ownership map.
> Claude uses this to quickly find the right file to edit.
""",
}


def _ensure_curated_templates(
    cur_dir: Path,
    doc_name: str,
    dry_run: bool,
) -> list[str]:
    """Create starter template files for any curated/ files not yet written.

    Returns a list of relative paths for files that were templated.
    Only creates files that don't already exist (never overwrites curated content).
    """
    if dry_run:
        return []
    cur_dir.mkdir(parents=True, exist_ok=True)
    templated: list[str] = []
    for filename, content in _CURATED_TEMPLATES.items():
        out_path = cur_dir / filename
        if not out_path.exists():
            # Stamp with the source doc name so user knows the context
            stamped = content.replace(
                "> Template created by `scope doc ingest`.",
                f"> Template created by `scope doc ingest` from `{doc_name}`.",
            )
            out_path.write_text(stamped, encoding="utf-8")
            templated.append(str(out_path.relative_to(cur_dir.parent.parent)).replace("\\", "/"))
    return templated


# ---------------------------------------------------------------------------
# CLAUDE.md updater
# ---------------------------------------------------------------------------

def _update_claude_md(repo_root: Path, project_name: str, generated: list[dict]) -> None:
    """Append a scope-intel section to CLAUDE.md (or create it)."""
    claude_md = repo_root / "CLAUDE.md"

    marker = "<!-- scope-intel-doc-context -->"
    doc_lines = [
        f"\n{marker}",
        f"## AI Context — {project_name}",
        "",
        "Before touching any code, retrieve context with scope intelligence:",
        "```",
        "scope mem fetch --feature <feature-name>   # layered memory",
        "scope feature <feature-name>               # files + symbols",
        "scope impacted --file <path>               # blast radius",
        "```",
        "",
        "### Design Reference Docs (`.ai-context/generated/`)",
    ]
    for f in sorted(generated, key=lambda x: x.get("path", "")):
        doc_lines.append(f"- `{f['path']}`  — {f['title']}")

    doc_lines += [
        "",
        "### Curated State (`.ai-context/curated/`)",
        "- `curated/current-phase.md` — what is being built right now",
        "- `curated/constraints.md`   — rules Claude must follow",
        "- `curated/module-map.md`    — file/module ownership map",
        f"\n<!-- end scope-intel-doc-context -->",
    ]
    new_section = "\n".join(doc_lines)

    if claude_md.exists():
        content = claude_md.read_text(encoding="utf-8")
        # Replace existing marker block if present
        content = re.sub(
            rf"{re.escape(marker)}.*?<!-- end scope-intel-doc-context -->",
            new_section,
            content,
            flags=re.S,
        )
        if marker not in content:
            content += "\n" + new_section
        claude_md.write_text(content, encoding="utf-8")
    else:
        claude_md.write_text(
            f"# {project_name}\n\n_Auto-generated by scope doc ingest._\n" + new_section,
            encoding="utf-8",
        )


# ---------------------------------------------------------------------------
# LLM pipeline helpers (mode=llm)
# ---------------------------------------------------------------------------

def _write_bucket_file(
    out_path: Path,
    primary_title: str,
    sections: list[dict],
    doc_name: str,
    overwrite: bool,
    dry_run: bool,
    rel_root: Path,
) -> dict:
    """Write one .ai-context/ file from aggregated chunk data.

    Returns a file-entry dict: {path, title, sections, layer, status}.
    Shared by both mode=python and mode=llm.
    """
    rel = str(out_path.relative_to(rel_root)).replace("\\", "/")

    if out_path.exists() and not overwrite:
        return {"path": rel, "title": primary_title,
                "sections": len(sections), "layer": "?", "status": "skipped_existing"}

    lines: list[str] = [f"# {primary_title}\n"]
    for s in sections:
        heading = s.get("heading_path") or s.get("title", "")
        body    = s.get("text") or s.get("body_text", "")
        if heading and heading != primary_title:
            lines.append(f"\n## {heading}\n")
        if body:
            lines.append(body + "\n")

    lines.append(
        f"\n---\n> Auto-generated by `scope doc ingest` "
        f"from `{doc_name}` on {time.strftime('%Y-%m-%d')}.\n"
    )
    content = "\n".join(lines)

    if not dry_run:
        out_path.write_text(content, encoding="utf-8")

    return {"path": rel, "title": primary_title,
            "sections": len(sections), "layer": "?", "status": "written"}


def _ingest_with_llm(
    repo_root: Path,
    doc_path: Path,
    *,
    llm,
    overwrite: bool,
    dry_run: bool,
    update_claude_md: bool,
    second_pass: bool,
) -> dict:
    """5-step LLM ingest pipeline.

    Steps:
      1. read_document_structured → chunks with heading_path
      2. global_summary pass → {project_name, components} injected into all chunks
      3. per-chunk classify (Qwen) → {target_file, key_facts, constraints, feature_id}
         Python keyword routing used as fallback per chunk if Qwen returns None
      4. aggregate chunks by target_file → write .ai-context/ files
      5. (optional) second Qwen pass → module-map.md from all file summaries
      Swan: detect_conflicts() on newly written memories
    """
    from ..adapters.doc_reader import read_document_structured

    # --- Step 1: structured read ---
    struct = read_document_structured(doc_path)
    if "error" in struct:
        return struct

    chunks: list[dict] = struct["chunks"]
    full_text: str     = struct["full_text"]
    fmt: str           = struct["format"]

    if not chunks:
        return {"error": "document produced no sections after heading split"}

    # --- Step 2: global summary (single LLM call) ---
    _progress(f"Global summary pass… ({len(chunks)} chunks to classify)")
    global_ctx = llm.global_summary(full_text) or {
        "project_name": doc_path.stem,
        "purpose": "",
        "components": [],
        "tech_stack": [],
    }
    proj = global_ctx.get("project_name", doc_path.stem)
    _progress(f"Project: {proj}  |  classifying {len(chunks)} chunks…")

    # --- Step 3: per-chunk classification ---
    # Buckets: target_file_name → {title, sections[], all_key_facts[], constraints[]}
    buckets: dict[str, dict] = {}
    all_features: list[dict] = []
    llm_count = 0
    fallback_count = 0
    unmatched: list[str] = []
    routing_table: list[dict] = []  # {section, file, layer} — for dry-run display
    total_chunks = len(chunks)

    for i, chunk in enumerate(chunks, 1):
        _progress(
            f"[{i}/{total_chunks}] {chunk.get('heading_path', chunk['title'])[:60]}",
            end="\r",
        )
        classification = llm.classify_chunk(chunk, global_ctx)
        target_file = None

        if classification:
            llm_count += 1
            target_file = classification.get("target_file", "skip")
        else:
            # Fallback: Python keyword routing on this chunk's text
            fallback_count += 1
            dest_type, prefix, slug = _route_section(
                chunk["title"], chunk.get("text", "")[:300]
            )
            if dest_type and slug:
                filename = (f"{prefix}-{slug}.md" if prefix else f"{slug}.md")
                target_file = filename
            else:
                target_file = "skip"
            classification = {
                "target_file": target_file,
                "section_title": chunk["title"],
                "key_facts": [],
                "constraints": [],
                "is_feature": False,
                "feature_id": "",
                "summary": chunk.get("text", "")[:200],
                "tags": [],
            }

        if target_file == "skip" or target_file not in TARGET_FILE_MAP:
            # Preamble (text before first heading) defaults to project overview
            # instead of being silently discarded — it's often the executive summary.
            if chunk["title"] == "(preamble)" and chunk.get("text", "").strip():
                target_file = "001-project-overview.md"
                classification["target_file"] = target_file
            else:
                if chunk["title"] and chunk["title"] != "(preamble)":
                    unmatched.append(chunk["title"])
                    hint = _suggest_route(chunk["title"], chunk.get("text", ""))
                    routing_table.append({
                        "section": chunk["title"],
                        "file":    None,
                        "layer":   None,
                        "via":     "llm" if classification else "fallback",
                        "hint":    hint,
                    })
                continue

        # Record routing decision for dry-run table
        rt_layer = TARGET_FILE_MAP.get(target_file, ("generated",))[0]
        routing_table.append({
            "section": chunk.get("heading_path") or chunk["title"],
            "file":    target_file,
            "layer":   rt_layer,
            "via":     "llm" if (classification and classification.get("target_file")) else "fallback",
        })

        if target_file not in buckets:
            buckets[target_file] = {
                "title": classification.get("section_title") or chunk["title"],
                "sections": [],
                "key_facts": [],
                "constraints": [],
                "summaries": [],
                "tags": set(),
            }

        buckets[target_file]["sections"].append(chunk)

        # Map chunk-level importance → default confidence for key_facts that
        # lack an explicit 'conf' field.  high→0.85  medium→0.75  low→0.60
        _imp_conf = {"high": 0.85, "medium": 0.75, "low": 0.60}
        imp_default = _imp_conf.get(
            str(classification.get("importance", "medium")).lower(), 0.75
        )
        enriched_facts = []
        for kf in classification.get("key_facts", []):
            if isinstance(kf, dict) and "conf" not in kf:
                kf = dict(kf, conf=imp_default)   # inject default conf
            enriched_facts.append(kf)
        buckets[target_file]["key_facts"].extend(enriched_facts)

        buckets[target_file]["constraints"].extend(
            classification.get("constraints", [])
        )
        if classification.get("summary"):
            buckets[target_file]["summaries"].append(classification["summary"])
        buckets[target_file]["tags"].update(classification.get("tags", []))

        if classification.get("is_feature") and classification.get("feature_id"):
            all_features.append({
                "id": classification["feature_id"],
                "title": classification.get("section_title", chunk["title"]),
                "source": "doc_ingest_llm",
                "files": [],
                "file_count": 0,
                "symbol_count": 0,
                "languages": [],
                "symbols": [],
                "aliases": [classification["feature_id"]],
                "depends_on_features": [],
                "entry_points": [],
            })

    # Clear the \r progress line and print completion summary
    _progress(
        f"Classification done: {llm_count} by LLM, {fallback_count} fallback  "
        f"→ {len(buckets)} output files"
    )

    # --- Step 4: prepare output dirs ---
    ai_ctx  = repo_root / ".ai-context"
    gen_dir = ai_ctx / "generated"
    cur_dir = ai_ctx / "curated"

    if not dry_run:
        gen_dir.mkdir(parents=True, exist_ok=True)
        cur_dir.mkdir(parents=True, exist_ok=True)

    # --- Step 5: second pass — module-map.md (optional) ---
    if second_pass and "module-map.md" not in buckets:
        _progress("Second pass: synthesising module-map.md…")
        file_summaries = [
            {
                "title": data["title"],
                "summary": " ".join(data["summaries"][:3]),
            }
            for tf, data in buckets.items()
            if TARGET_FILE_MAP.get(tf, ("",))[0] == "generated" and data["summaries"]
        ]
        if file_summaries:
            module_map_content = llm.module_map_pass(file_summaries)
            if module_map_content:
                buckets["module-map.md"] = {
                    "title": "Module Map",
                    "sections": [{
                        "heading_path": "Module Map",
                        "title": "Module Map",
                        "text": module_map_content,
                    }],
                    "key_facts": [],
                    "constraints": [],
                    "summaries": [module_map_content[:300]],
                    "tags": set(),
                }

    # --- Write files ---
    generated_files: list[dict] = []

    for target_file, data in sorted(buckets.items()):
        dest_dir, prefix, slug = TARGET_FILE_MAP[target_file]
        base_dir = gen_dir if dest_dir == "generated" else cur_dir
        filename  = f"{prefix}-{slug}.md" if prefix else f"{slug}.md"
        out_path  = base_dir / filename

        entry = _write_bucket_file(
            out_path=out_path,
            primary_title=data["title"],
            sections=data["sections"],
            doc_name=doc_path.name,
            overwrite=overwrite,
            dry_run=dry_run,
            rel_root=repo_root,
        )
        entry["layer"] = dest_dir
        generated_files.append(entry)

    # --- index.json ---
    index_path = gen_dir / "index.json"
    source_hash = _doc_hash(doc_path)
    index_data = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source":       doc_path.name,
        "source_hash":  source_hash,
        "mode":         "llm",
        "llm_model":    getattr(llm, "model", "unknown"),
        "total_files":  len(generated_files),
        "files": [
            {
                "id":    f["path"].split("/")[-1].replace(".md", ""),
                "path":  f["path"],
                "title": f["title"],
                "layer": f["layer"],
            }
            for f in generated_files
        ],
    }
    if not dry_run:
        index_path.write_text(
            json.dumps(index_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # --- memories: all key_facts across all buckets ---
    memories_added: list[str] = []
    if not dry_run:
        # Seed seen_facts from existing mempalace so re-ingesting the same
        # document doesn't produce duplicate memory entries (Swan purity).
        seen_facts: set[str] = _existing_memory_notes(repo_root)
        for target_file, data in buckets.items():
            # Derive a feature-like tag from the target file (e.g. "memory-layer")
            tf_slug = TARGET_FILE_MAP.get(target_file, ("", None, target_file))[2]
            section_tag = tf_slug or doc_path.stem

            for kf in data["key_facts"]:
                fact_text = kf.get("fact", "") if isinstance(kf, dict) else str(kf)
                if not fact_text or fact_text.lower() in seen_facts:
                    continue
                seen_facts.add(fact_text.lower())
                conf = kf.get("conf", 0.75) if isinstance(kf, dict) else 0.75
                tags = list(dict.fromkeys(
                    ["doc-ingest", "llm", section_tag, doc_path.stem]
                    + list(data.get("tags", set()))
                ))
                result = add_memory(
                    repo_root, "semantic", fact_text,
                    confidence=min(max(float(conf), 0.1), 1.0),
                    tags=tags,
                )
                if "error" not in result:
                    memories_added.append(result["id"])

        # Also store constraints as high-confidence semantic memories
        for target_file, data in buckets.items():
            tf_slug = TARGET_FILE_MAP.get(target_file, ("", None, target_file))[2]
            for c in data.get("constraints", []):
                if not c or c.lower() in seen_facts:
                    continue
                seen_facts.add(c.lower())
                result = add_memory(
                    repo_root, "semantic", f"Constraint: {c}",
                    confidence=0.90,
                    tags=["doc-ingest", "constraint", tf_slug, doc_path.stem],
                )
                if "error" not in result:
                    memories_added.append(result["id"])

    # --- feature stubs ---
    features_added: list[str] = []
    if not dry_run and all_features:
        existing_data = store.read_json(repo_root, "features", {"features": []})
        existing_ids  = {f.get("id") for f in existing_data.get("features", [])}
        for feat in all_features:
            if feat["id"] not in existing_ids:
                existing_data.setdefault("features", []).append(feat)
                features_added.append(feat["id"])
        if features_added:
            store.write_json(repo_root, "features", existing_data)

    # --- Curated templates — create starters for any missing curated files ---
    templates_created = _ensure_curated_templates(cur_dir, doc_path.name, dry_run)

    # --- CLAUDE.md ---
    if not dry_run and update_claude_md:
        written = [f for f in generated_files if f.get("status") == "written"]
        project_name = global_ctx.get("project_name") or repo_root.name
        _update_claude_md(repo_root, project_name=project_name, generated=written)

    # --- Swan purity pass: detect conflicts in newly added memories ---
    conflicts_after = None
    if not dry_run and memories_added:
        conflict_result = detect_conflicts(repo_root)
        conflicts_after = conflict_result.get("total", 0)

    written_count  = sum(1 for f in generated_files if f.get("status") == "written")
    skipped_count  = sum(1 for f in generated_files if f.get("status") == "skipped_existing")

    return {
        "source":                str(doc_path),
        "format":                fmt,
        "mode":                  "llm",
        "dry_run":               dry_run,
        "source_hash":           source_hash,
        "sections_parsed":       len(chunks),
        "sections_unmatched":    len(set(unmatched)),
        "files_written":         written_count,
        "files_skipped":         skipped_count,
        "memories_added":        len(memories_added),
        "features_added":        len(features_added),
        "generated":             generated_files,
        "skipped":               [],
        "unmatched_sections":    list(set(unmatched)),
        "llm_chunks_classified": len(chunks),
        "llm_chunks_by_llm":     llm_count,
        "llm_chunks_fallback":   fallback_count,
        "conflicts_after_ingest": conflicts_after,
        "global_context":         global_ctx,
        "routing_table":          routing_table,
        "templates_created":      templates_created,
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def ingest_document(
    repo_root: Path,
    doc_path: Path,
    *,
    overwrite: bool = False,
    dry_run: bool = False,
    update_claude_md: bool = True,
    mode: str = "python",
    ollama_model: str = "qwen2.5:14b",
    ollama_url: str = "http://localhost:11434",
    second_pass: bool = False,
    if_changed: bool = False,
) -> dict:
    """Parse a design document and generate .ai-context/ files.

    Args:
        repo_root:        Root of the target repo (must be scope-initialised).
        doc_path:         Path to the design document (PDF/DOCX/MD/TXT).
        overwrite:        If True, regenerate files that already exist.
        dry_run:          Parse and report without writing anything.
        update_claude_md: Append scope-intel section to CLAUDE.md.
        mode:             'python' (fast, no LLM) or 'llm' (Qwen via Ollama).
        ollama_model:     Ollama model to use in mode='llm'.
        ollama_url:       Ollama server URL.
        second_pass:      Run second Qwen pass for module-map.md synthesis.
        if_changed:       Skip ingest if source doc hash matches stored hash.

    Returns a result dict summarising what was (or would be) generated.
    """
    from .llm_client import get_client

    repo_root = Path(repo_root)
    doc_path  = Path(doc_path)

    if not store.is_initialized(repo_root):
        return {"error": "repo not indexed — run `scope init` first"}
    if not doc_path.exists():
        return {"error": f"document not found: {doc_path}"}

    # --if-changed: skip if source hash matches what was stored from the last run
    if if_changed:
        current_hash  = _doc_hash(doc_path)
        stored_hash   = _read_index_hash(repo_root)
        if current_hash and stored_hash and current_hash == stored_hash:
            return {
                "source":          str(doc_path),
                "format":          doc_path.suffix.lstrip(".").lower() or "?",
                "mode":            mode,
                "dry_run":         False,
                "unchanged":       True,
                "source_hash":     current_hash,
                "sections_parsed": 0,
                "sections_unmatched": 0,
                "files_written":   0,
                "files_skipped":   0,
                "memories_added":  0,
                "features_added":  0,
                "generated":       [],
                "skipped":         [],
                "unmatched_sections": [],
                "routing_table":   [],
                "conflicts_after_ingest": None,
                "note": "Source document unchanged since last ingest — skipped.",
            }

    # --- LLM mode: dispatch to 5-step pipeline ---
    if mode == "llm":
        llm = get_client(mode="llm", model=ollama_model, url=ollama_url)
        if not llm.is_available():
            # Ollama not reachable — fall back gracefully with a warning
            result = _ingest_python_only(repo_root, doc_path,
                                         overwrite=overwrite,
                                         dry_run=dry_run,
                                         update_claude_md=update_claude_md)
            result["warning"] = (
                f"Ollama not available at {ollama_url} (model: {ollama_model}). "
                f"Fell back to mode=python. Start Ollama and retry with --mode llm."
            )
            result["mode"] = "python_fallback"
            return result
        return _ingest_with_llm(
            repo_root, doc_path,
            llm=llm,
            overwrite=overwrite,
            dry_run=dry_run,
            update_claude_md=update_claude_md,
            second_pass=second_pass,
        )

    # --- Python mode: existing keyword-routing pipeline ---
    return _ingest_python_only(repo_root, doc_path,
                                overwrite=overwrite,
                                dry_run=dry_run,
                                update_claude_md=update_claude_md)


def _ingest_python_only(
    repo_root: Path,
    doc_path: Path,
    *,
    overwrite: bool,
    dry_run: bool,
    update_claude_md: bool,
) -> dict:
    """Original Python-only pipeline (mode=python / Option C).

    Fast, no external dependencies. Uses regex keyword routing.
    Kept intact for comparison against mode=llm results.
    """
    from ..adapters.doc_reader import read_document

    read_result = read_document(doc_path)
    if "error" in read_result:
        return read_result

    text: str = read_result["text"]
    if not text.strip():
        return {"error": "document is empty or contains no extractable text"}

    # --- parse sections ---
    sections = _split_sections(text)

    # --- route sections to output files ---
    # bucket key: (dest_type, slug) → merged content
    buckets: dict[tuple, dict] = {}
    unmatched: list[str] = []
    routing_table: list[dict] = []  # {section, file, layer} — for dry-run display

    for s in sections:
        dest_type, prefix, slug = _route_section(
            s["title"], s.get("body_text", "")
        )
        if not (dest_type and slug):
            # Preamble with content → project overview (executive summary is valuable)
            if s["title"] == "(preamble)" and s.get("body_text", "").strip():
                dest_type, prefix, slug = "generated", "001", "project-overview"
            else:
                if s["title"] != "(preamble)" and s.get("body_text"):
                    unmatched.append(s["title"])
                    hint = _suggest_route(s["title"], s.get("body_text", ""))
                    routing_table.append({
                        "section": s["title"],
                        "level":   s.get("level", 1),
                        "file":    None,
                        "layer":   None,
                        "hint":    hint,
                    })
                continue
        filename = (f"{prefix}-{slug}.md" if prefix else f"{slug}.md")
        routing_table.append({
            "section": s["title"] if s["title"] != "(preamble)" else "(preamble → overview)",
            "level":   s.get("level", 1),
            "file":    filename,
            "layer":   dest_type,
        })
        key = (dest_type, slug)
        if key not in buckets:
            buckets[key] = {
                "dest": dest_type,
                "prefix": prefix,
                "slug": slug,
                "primary_title": s["title"] if s["title"] != "(preamble)" else "Project Overview",
                "sections": [],
            }
        buckets[key]["sections"].append(s)

    # --- prepare output dirs ---
    ai_ctx = repo_root / ".ai-context"
    gen_dir = ai_ctx / "generated"
    cur_dir = ai_ctx / "curated"

    if not dry_run:
        gen_dir.mkdir(parents=True, exist_ok=True)
        cur_dir.mkdir(parents=True, exist_ok=True)

    # --- write files ---
    generated_files: list[dict] = []
    skipped_files: list[str] = []

    for (dest_type, slug), bucket in sorted(buckets.items()):
        prefix = bucket["prefix"]
        if dest_type == "generated":
            filename = (f"{prefix}-{slug}.md" if prefix else f"{slug}.md")
            out_path = gen_dir / filename
        else:
            out_path = cur_dir / f"{slug}.md"

        rel = str(out_path.relative_to(repo_root)).replace("\\", "/")

        if out_path.exists() and not overwrite:
            skipped_files.append(rel)
            # Still include in manifest so index.json is complete
            generated_files.append({
                "path": rel,
                "title": bucket["primary_title"],
                "sections": len(bucket["sections"]),
                "layer": dest_type,
                "status": "skipped_existing",
            })
            continue

        # Build markdown content
        lines: list[str] = [f"# {bucket['primary_title']}\n"]
        for s in bucket["sections"]:
            if s["title"] != bucket["primary_title"]:
                h = "#" * min(s["level"] + 1, 4)
                lines.append(f"\n{h} {s['title']}\n")
            if s.get("body_text"):
                lines.append(s["body_text"] + "\n")
        lines.append(
            f"\n---\n"
            f"> Auto-generated by `scope doc ingest` "
            f"from `{doc_path.name}` on "
            f"{time.strftime('%Y-%m-%d')}.\n"
        )
        content = "\n".join(lines)

        if not dry_run:
            out_path.write_text(content, encoding="utf-8")

        generated_files.append({
            "path": rel,
            "title": bucket["primary_title"],
            "sections": len(bucket["sections"]),
            "layer": dest_type,
            "status": "written",
        })

    # --- index.json ---
    index_path = gen_dir / "index.json"
    source_hash = _doc_hash(doc_path)
    index_data = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source":       doc_path.name,
        "source_hash":  source_hash,
        "mode":         "python",
        "total_files":  len(generated_files),
        "files": [
            {
                "id":    f["path"].split("/")[-1].replace(".md", ""),
                "path":  f["path"],
                "title": f["title"],
                "layer": f["layer"],
            }
            for f in generated_files
        ],
    }
    if not dry_run:
        index_path.write_text(
            json.dumps(index_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # --- memories (per-section with section tag so mem-fetch works by feature) ---
    memories_added: list[str] = []
    if not dry_run:
        # Seed seen_notes from existing mempalace to avoid duplicate entries
        # on re-ingest of the same document.
        seen_notes: set[str] = _existing_memory_notes(repo_root)
        for s in sections:
            section_body = s.get("body_text", "")
            if not section_body.strip():
                continue
            section_slug = re.sub(r"[^a-z0-9]+", "-", s["title"].lower()).strip("-")
            section_tag  = section_slug or doc_path.stem

            for m in _extract_memories(section_body, section_tag):
                note_lower = m["note"].lower()
                if note_lower in seen_notes:
                    continue
                seen_notes.add(note_lower)

                # Merge tags: base doc-ingest + section slug + doc name
                tags = list(dict.fromkeys(
                    ["doc-ingest", section_tag, doc_path.stem]
                    + m.get("tags", [])
                ))
                result = add_memory(
                    repo_root,
                    m["type"],
                    m["note"],
                    confidence=m.get("confidence", 0.75),
                    tags=tags,
                )
                if "error" not in result:
                    memories_added.append(result["id"])

                if len(memories_added) >= 120:  # global cap
                    break
            if len(memories_added) >= 120:
                break

    # --- feature stubs ---
    features_added: list[str] = []
    if not dry_run:
        existing_data = store.read_json(repo_root, "features", {"features": []})
        existing_ids = {f.get("id") for f in existing_data.get("features", [])}
        new_stubs = _extract_features(sections)
        for feat in new_stubs:
            if feat["id"] not in existing_ids:
                existing_data.setdefault("features", []).append(feat)
                features_added.append(feat["id"])
        if features_added:
            store.write_json(repo_root, "features", existing_data)

    # --- Curated templates — create starters for any missing curated files ---
    templates_created = _ensure_curated_templates(cur_dir, doc_path.name, dry_run)

    # --- CLAUDE.md ---
    if not dry_run and update_claude_md:
        written = [f for f in generated_files if f["status"] == "written"]
        _update_claude_md(
            repo_root,
            project_name=repo_root.name,
            generated=written,
        )

    # Swan purity pass — detect conflicts after adding new memories
    conflicts_after = None
    if not dry_run and memories_added:
        conflict_result = detect_conflicts(repo_root)
        conflicts_after = conflict_result.get("total", 0)

    written_count = sum(1 for f in generated_files if f.get("status") == "written")
    result: dict = {
        "source":             str(doc_path),
        "format":             read_result.get("format", "?"),
        "mode":               "python",
        "dry_run":            dry_run,
        "source_hash":        _doc_hash(doc_path),
        "sections_parsed":    len(sections),
        "sections_unmatched": len(unmatched),
        "files_written":      written_count,
        "files_skipped":      len(skipped_files),
        "memories_added":     len(memories_added),
        "features_added":     len(features_added),
        "generated":          generated_files,
        "skipped":            skipped_files,
        "unmatched_sections": unmatched,
        "conflicts_after_ingest": conflicts_after,
        "routing_table":          routing_table,
        "templates_created":      templates_created,
    }
    # Pass through PDF reader info if available ("pdfplumber" or "pypdf")
    if read_result.get("reader"):
        result["pdf_reader"] = read_result["reader"]
    return result
