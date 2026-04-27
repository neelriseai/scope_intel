"""MemPalace — long-term memory layer for per-repo knowledge.

Four memory types, each serving a distinct cognitive role:

  semantic   — Timeless facts about the codebase. Always surfaced first,
                ranked by confidence, never aged out by recency.
                E.g. "auth uses HS256 JWT signing", "billing is PCI-scoped".

  procedure  — Repo-specific step-by-step workflows discovered from real work.
                Structured as ordered steps[], not free text.
                E.g. "how to add a new API endpoint in this repo".

  episodic   — Specific past incidents: bugs, decisions, failures, fixes.
                Ranked by recency — what happened recently matters most.
                E.g. "float rounding broke currency in charge(), use Decimal".

  scope      — Structural memory. This is handled entirely by the Phase 1-3
                index (.scope-intelligence/). NOT stored in mempalace.jsonl.
                fetch_relevant() injects a live structural slice into results.

Fetch layering (what Claude sees before touching a file):
  1. structural  — live scope slice from Phase 1-3 engine (always injected)
  2. semantic    — timeless facts sorted by confidence desc
  3. procedural  — step-by-step workflows for this scope
  4. episodic    — past incidents newest-first

Storage: .scope-intelligence/mempalace.jsonl (append-only JSONL)
"""
from __future__ import annotations

import hashlib
import subprocess
import time
from pathlib import Path
from typing import Optional

from . import store
from .query_engine import (
    find_impacted_files,
    get_feature_scope,
    get_symbol_context,
)
from .tracker import log_query

# episodic subtypes + the two new first-class types
EPISODIC_TYPES = ("bug", "decision", "failure", "ownership", "note", "fix")
VALID_TYPES = ("semantic", "procedure") + EPISODIC_TYPES


# ---------------------------------------------------------------------------
# Entry construction
# ---------------------------------------------------------------------------

def _make_id(note: str, ts: str) -> str:
    raw = f"{ts}:{note}"
    return "mp_" + hashlib.sha1(raw.encode()).hexdigest()[:12]


def add_memory(
    repo_root: Path,
    kind: str,
    note: str,
    *,
    files: Optional[list] = None,
    features: Optional[list] = None,
    symbols: Optional[list] = None,
    tags: Optional[list] = None,
    author: str = "",
    resolved: bool = False,
    # semantic-only
    confidence: float = 1.0,
    # procedure-only
    steps: Optional[list] = None,
) -> dict:
    """Append one memory entry to mempalace.jsonl and return it."""
    if not store.is_initialized(repo_root):
        return {"error": "repo not indexed — run scope init first"}
    if kind not in VALID_TYPES:
        return {"error": f"type must be one of: {', '.join(VALID_TYPES)}"}
    if kind == "procedure" and not steps:
        return {"error": "procedure memories require --step entries"}
    if kind == "semantic" and not (0.0 <= confidence <= 1.0):
        return {"error": "confidence must be between 0.0 and 1.0"}

    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    entry: dict = {
        "id":       _make_id(note, ts),
        "ts":       ts,
        "type":     kind,
        "note":     note,
        "scope": {
            "files":    list(files or []),
            "features": list(features or []),
            "symbols":  list(symbols or []),
        },
        "tags":     list(tags or []),
        "author":   author,
        "resolved": resolved,
    }
    if kind == "semantic":
        entry["confidence"] = round(float(confidence), 2)
    if kind == "procedure":
        entry["steps"] = list(steps or [])

    store.append_mempalace(repo_root, entry)
    return entry


# ---------------------------------------------------------------------------
# Fetch — Phase 1-3 integration + four-layer result
# ---------------------------------------------------------------------------

def _structural_slice(
    repo_root: Path,
    scope_files: set,
    scope_features: set,
    scope_symbols: set,
) -> dict:
    """Build a compact structural summary from the live Phase 1-3 index."""
    deps = store.read_json(repo_root, "dependencies", {"files": {}})
    files_index = deps.get("files", {})

    feature_summaries: list = []
    features_data = store.read_json(repo_root, "features", {"features": []})
    for feat in features_data.get("features", []):
        if feat.get("id") in scope_features:
            feature_summaries.append({
                "id":          feat["id"],
                "file_count":  feat.get("file_count", 0),
                "symbol_count": feat.get("symbol_count", 0),
                "languages":   feat.get("languages", []),
                "depends_on":  feat.get("depends_on_features", []),
            })

    file_details: list = []
    for f in sorted(scope_files):
        meta = files_index.get(f, {})
        file_details.append({
            "file":     f,
            "loc":      meta.get("loc", 0),
            "language": meta.get("language", "?"),
            "symbols":  len(meta.get("symbols", [])),
        })

    return {
        "features": feature_summaries,
        "files":    file_details,
        "symbols":  sorted(scope_symbols),
    }


def fetch_relevant(
    repo_root: Path,
    *,
    feature: Optional[str] = None,
    file: Optional[str] = None,
    symbol: Optional[str] = None,
    kind: Optional[str] = None,
    include_resolved: bool = False,
    limit: int = 20,
) -> dict:
    """Return a four-layer memory response for the given scope.

    Layers returned (in priority order):
      structural — live Phase 1-3 scope slice (always present)
      semantic   — timeless facts, confidence desc
      procedural — step-by-step workflows
      episodic   — past incidents, newest first

    Phase 1-3 queries used internally:
      get_feature_scope()    → resolves files + feature metadata
      find_impacted_files()  → expands to affected neighbours
      get_symbol_context()   → expands via call graph
    """
    if not store.is_initialized(repo_root):
        return {"error": "repo not indexed — run scope init first"}

    scope_files: set = set()
    scope_features: set = set()
    scope_symbols: set = set()
    scope_errors: list = []

    # --- Phase 1-3 scope resolution ---

    if feature:
        result = get_feature_scope(repo_root, feature)
        if "error" in result:
            scope_errors.append(f"feature '{feature}': {result['error']}")
        else:
            scope_files.update(result.get("files", []))
            feat = result.get("feature", {})
            scope_features.add(feat.get("id", feature))
            scope_features.update(feat.get("aliases", []))
            for t in result.get("tests", []):
                scope_files.add(t["file"])

    if file:
        scope_files.add(file)
        impact = find_impacted_files(repo_root, file=file)
        if "error" not in impact:
            scope_files.update(impact.get("direct", []))
            scope_features.update(impact.get("features", []))

    if symbol:
        scope_symbols.add(symbol)
        sym_result = get_symbol_context(repo_root, symbol)
        if "error" not in sym_result:
            for m in sym_result.get("matches", []):
                sym = m["symbol"]
                if sym.get("file"):
                    scope_files.add(sym["file"])
                if sym.get("feature"):
                    scope_features.add(sym["feature"])
                for c in m.get("callers", []) + m.get("callees", []):
                    if c.get("file"):
                        scope_files.add(c["file"])

    # --- filter mempalace entries ---

    all_entries = store.read_mempalace(repo_root)
    has_scope_filter = bool(feature or file or symbol)

    semantic_matches: list = []
    procedure_matches: list = []
    episodic_matches: list = []

    for e in all_entries:
        if e.get("resolved") and not include_resolved:
            continue
        if kind and e.get("type") != kind:
            continue

        e_scope = e.get("scope", {})
        e_files = set(e_scope.get("files", []))
        e_feats = set(e_scope.get("features", []))
        e_syms = set(e_scope.get("symbols", []))

        relevant = (
            not has_scope_filter
            or e_files & scope_files
            or e_feats & scope_features
            or e_syms & scope_symbols
        )
        if not relevant:
            continue

        etype = e.get("type", "note")
        if etype == "semantic":
            semantic_matches.append(e)
        elif etype == "procedure":
            procedure_matches.append(e)
        else:
            episodic_matches.append(e)

    # semantic: highest confidence first (timeless facts don't age)
    semantic_matches.sort(key=lambda x: -x.get("confidence", 1.0))

    # procedure: most recently updated first
    procedure_matches.sort(key=lambda x: x.get("ts", ""), reverse=True)

    # episodic: newest first (recent incidents are most relevant)
    episodic_matches.sort(key=lambda x: x.get("ts", ""), reverse=True)

    # apply per-layer limits (semantic: all, procedure: all, episodic: capped)
    episodic_matches = episodic_matches[:limit]

    # inject structural layer from live Phase 1-3 index
    structural = _structural_slice(
        repo_root, scope_files, scope_features, scope_symbols
    )

    # log as scope query for token savings report
    log_query(
        repo_root,
        "mem_fetch",
        {"feature": feature, "file": file, "symbol": symbol, "kind": kind},
        list(scope_files),
    )

    total = len(semantic_matches) + len(procedure_matches) + len(episodic_matches)
    result: dict = {
        "query": {
            "feature": feature,
            "file":    file,
            "symbol":  symbol,
            "kind":    kind,
        },
        "resolved_scope": {
            "files":    sorted(scope_files),
            "features": sorted(scope_features),
            "symbols":  sorted(scope_symbols),
        },
        "layers": {
            "structural": structural,
            "semantic":   semantic_matches,
            "procedural": procedure_matches,
            "episodic":   episodic_matches,
        },
        "total": total,
    }
    if scope_errors:
        result["warnings"] = scope_errors
    return result


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

def list_memories(
    repo_root: Path,
    *,
    kind: Optional[str] = None,
    tag: Optional[str] = None,
    include_resolved: bool = True,
) -> dict:
    entries = store.read_mempalace(repo_root)
    out: list = []
    for e in entries:
        if not include_resolved and e.get("resolved"):
            continue
        if kind and e.get("type") != kind:
            continue
        if tag and tag not in e.get("tags", []):
            continue
        out.append(e)
    out.sort(key=lambda x: x.get("ts", ""), reverse=True)
    return {
        "total": len(out),
        "filters": {"type": kind, "tag": tag, "include_resolved": include_resolved},
        "entries": out,
    }


# ---------------------------------------------------------------------------
# Resolve
# ---------------------------------------------------------------------------

def resolve_memory(repo_root: Path, mem_id: str) -> dict:
    entries = store.read_mempalace(repo_root)
    found = False
    updated: list = []
    for e in entries:
        if e.get("id") == mem_id:
            e = dict(e)
            e["resolved"] = True
            e["resolved_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            found = True
        updated.append(e)

    if not found:
        return {"error": f"no entry with id '{mem_id}'"}

    import json as _json
    path = store.mempalace_path(repo_root)
    with path.open("w", encoding="utf-8") as f:
        for e in updated:
            f.write(_json.dumps(e, ensure_ascii=False) + "\n")
    return {"resolved": mem_id}


# ---------------------------------------------------------------------------
# Churn
# ---------------------------------------------------------------------------

def compute_churn(repo_root: Path, days: int = 90) -> dict:
    try:
        result = subprocess.run(
            ["git", "log", f"--since={days} days ago",
             "--name-only", "--format=", "--diff-filter=AM"],
            cwd=str(repo_root),
            capture_output=True, text=True, timeout=20,
        )
        if result.returncode != 0:
            return {"error": "git log failed — is this a git repo?"}
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return {"error": str(e)}

    churn: dict = {}
    for line in result.stdout.splitlines():
        f = line.strip()
        if f:
            churn[f] = churn.get(f, 0) + 1

    if not churn:
        return {"days": days, "files": {}, "features": {},
                "note": "no changes found in git log for this period"}

    features_data = store.read_json(repo_root, "features", {"features": []})
    feat_churn: dict = {}
    for feat in features_data.get("features", []):
        feat_id = feat.get("id", "")
        feat_files = set(feat.get("files", []))
        total = sum(churn.get(f, 0) for f in feat_files)
        if total > 0:
            feat_churn[feat_id] = {
                "total_changes": total,
                "files": {f: churn[f] for f in feat_files if f in churn},
            }

    top_files = sorted(churn.items(), key=lambda kv: -kv[1])[:20]
    top_features = sorted(feat_churn.items(),
                          key=lambda kv: -kv[1]["total_changes"])

    return {
        "days": days,
        "total_changed_files": len(churn),
        "top_files": [{"file": f, "changes": n} for f, n in top_files],
        "features": {fid: v for fid, v in top_features},
    }


# ---------------------------------------------------------------------------
# Summary stats
# ---------------------------------------------------------------------------

def memory_stats(repo_root: Path) -> dict:
    entries = store.read_mempalace(repo_root)
    if not entries:
        return {"total": 0}

    by_type: dict = {}
    open_count = 0
    for e in entries:
        t = e.get("type", "note")
        by_type[t] = by_type.get(t, 0) + 1
        if not e.get("resolved"):
            open_count += 1

    top_files: dict = {}
    for e in entries:
        for f in e.get("scope", {}).get("files", []):
            top_files[f] = top_files.get(f, 0) + 1

    most_noted = sorted(top_files.items(), key=lambda kv: -kv[1])[:5]

    return {
        "total": len(entries),
        "open": open_count,
        "resolved": len(entries) - open_count,
        "by_type": by_type,
        "most_noted_files": [{"file": f, "entries": n} for f, n in most_noted],
    }
