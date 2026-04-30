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

import json
import re
import sys
import time
from pathlib import Path
from typing import Optional

from . import store
from .mempalace import add_memory, detect_conflicts

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


def _route_section(title: str, body_snippet: str) -> tuple[str | None, str | None, str | None]:
    """Decide where a section goes.

    Returns (dest_type, prefix, slug):
      dest_type : 'generated' | 'curated' | None
      prefix    : '001' … '009' | None
      slug      : filename stem (without extension)

    Curated routes are checked FIRST because they have very distinctive
    heading names (Constraints, Module Map, Current Phase) and rarely
    produce false positives.  Checking them first prevents generated routes
    from stealing a "Constraints" section just because its body happens to
    contain words like "validation" or "architecture".
    """
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
            if chunk["title"] and chunk["title"] != "(preamble)":
                unmatched.append(chunk["title"])
            continue

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
        buckets[target_file]["key_facts"].extend(
            classification.get("key_facts", [])
        )
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
    index_data = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source":       doc_path.name,
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
        # Collect + deduplicate key_facts (Swan: clean before storing)
        seen_facts: set[str] = set()
        for data in buckets.values():
            for kf in data["key_facts"]:
                fact_text = kf.get("fact", "") if isinstance(kf, dict) else str(kf)
                if not fact_text or fact_text.lower() in seen_facts:
                    continue
                seen_facts.add(fact_text.lower())
                conf = kf.get("conf", 0.75) if isinstance(kf, dict) else 0.75
                result = add_memory(
                    repo_root, "semantic", fact_text,
                    confidence=min(max(float(conf), 0.1), 1.0),
                    tags=["doc-ingest", "llm", doc_path.stem],
                )
                if "error" not in result:
                    memories_added.append(result["id"])

        # Also store constraints as high-confidence semantic memories
        for data in buckets.values():
            for c in data.get("constraints", []):
                if not c or c.lower() in seen_facts:
                    continue
                seen_facts.add(c.lower())
                result = add_memory(
                    repo_root, "semantic", f"Constraint: {c}",
                    confidence=0.90,
                    tags=["doc-ingest", "constraint", doc_path.stem],
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
        "global_context":        global_ctx,
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

    Returns a result dict summarising what was (or would be) generated.
    """
    from .llm_client import get_client

    repo_root = Path(repo_root)
    doc_path  = Path(doc_path)

    if not store.is_initialized(repo_root):
        return {"error": "repo not indexed — run `scope init` first"}
    if not doc_path.exists():
        return {"error": f"document not found: {doc_path}"}

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

    for s in sections:
        dest_type, prefix, slug = _route_section(
            s["title"], s.get("body_text", "")
        )
        if dest_type and slug:
            key = (dest_type, slug)
            if key not in buckets:
                buckets[key] = {
                    "dest": dest_type,
                    "prefix": prefix,
                    "slug": slug,
                    "primary_title": s["title"],
                    "sections": [],
                }
            buckets[key]["sections"].append(s)
        else:
            if s["title"] != "(preamble)" and s.get("body_text"):
                unmatched.append(s["title"])

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
    index_data = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": doc_path.name,
        "total_files": len(generated_files),
        "files": [
            {
                "id": f["path"].split("/")[-1].replace(".md", ""),
                "path": f["path"],
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

    # --- memories ---
    memories_added: list[str] = []
    if not dry_run:
        for m in _extract_memories(text, doc_path.stem):
            result = add_memory(
                repo_root,
                m["type"],
                m["note"],
                confidence=m.get("confidence", 0.75),
                tags=m.get("tags", ["doc-ingest"]),
            )
            if "error" not in result:
                memories_added.append(result["id"])

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
    return {
        "source": str(doc_path),
        "format": read_result.get("format", "?"),
        "mode":   "python",
        "dry_run": dry_run,
        "sections_parsed": len(sections),
        "sections_unmatched": len(unmatched),
        "files_written": written_count,
        "files_skipped": len(skipped_files),
        "memories_added": len(memories_added),
        "features_added": len(features_added),
        "generated": generated_files,
        "skipped": skipped_files,
        "unmatched_sections": unmatched,
        "conflicts_after_ingest": conflicts_after,
    }
