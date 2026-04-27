"""MemPalace — long-term memory layer for per-repo knowledge.

Stores bugs, decisions, failures, ownership notes, and historical context
in `.scope-intelligence/mempalace.jsonl`. Every entry is scoped to the
files/features/symbols it concerns.

The fetch path deliberately routes through the Phase 1-3 scope engine:
  fetch(feature="auth")
    → get_feature_scope("auth")         # resolves exact files
    → find_impacted_files(file=...)     # expands to affected neighbours
    → filter mempalace entries by overlap
    → log as query_log entry            # feeds scope report

This means every mem fetch exercises and validates the full pipeline.
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

VALID_TYPES = ("bug", "decision", "failure", "ownership", "note", "fix")


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
) -> dict:
    """Append one memory entry to mempalace.jsonl and return it."""
    if not store.is_initialized(repo_root):
        return {"error": "repo not indexed — run scope init first"}
    if kind not in VALID_TYPES:
        return {"error": f"type must be one of: {', '.join(VALID_TYPES)}"}

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
    store.append_mempalace(repo_root, entry)
    return entry


# ---------------------------------------------------------------------------
# Fetch — Phase 1-3 integration is here
# ---------------------------------------------------------------------------

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
    """Return memory entries relevant to the requested scope.

    Uses Phase 1-3 scope engine to resolve the full set of related
    files/features/symbols before filtering mempalace entries.
    """
    if not store.is_initialized(repo_root):
        return {"error": "repo not indexed — run scope init first"}

    scope_files: set = set()
    scope_features: set = set()
    scope_symbols: set = set()
    scope_errors: list = []

    # --- resolve scope using Phase 1-3 queries ---

    if feature:
        result = get_feature_scope(repo_root, feature)
        if "error" in result:
            scope_errors.append(f"feature '{feature}': {result['error']}")
        else:
            scope_files.update(result.get("files", []))
            feat = result.get("feature", {})
            scope_features.add(feat.get("id", feature))
            scope_features.update(feat.get("aliases", []))
            # also pull files from related tests
            for t in result.get("tests", []):
                scope_files.add(t["file"])

    if file:
        scope_files.add(file)
        # expand to direct neighbours via impacted
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
                # callers and callees files
                for c in m.get("callers", []) + m.get("callees", []):
                    if c.get("file"):
                        scope_files.add(c["file"])

    if not feature and not file and not symbol:
        # no scope filter — return everything
        pass

    # --- filter mempalace ---

    all_entries = store.read_mempalace(repo_root)
    matched: list = []

    for e in all_entries:
        if e.get("resolved") and not include_resolved:
            continue
        if kind and e.get("type") != kind:
            continue

        e_scope = e.get("scope", {})
        e_files = set(e_scope.get("files", []))
        e_feats = set(e_scope.get("features", []))
        e_syms = set(e_scope.get("symbols", []))

        # match if any scope dimension overlaps, OR no scope filter was given
        if not (feature or file or symbol):
            matched.append(e)
        elif (e_files & scope_files
              or e_feats & scope_features
              or e_syms & scope_symbols):
            matched.append(e)

    # newest first
    matched.sort(key=lambda x: x.get("ts", ""), reverse=True)
    matched = matched[:limit]

    # log as a scope query so it feeds the token savings report
    log_query(
        repo_root,
        "mem_fetch",
        {"feature": feature, "file": file, "symbol": symbol, "kind": kind},
        list(scope_files),
    )

    result: dict = {
        "query": {"feature": feature, "file": file, "symbol": symbol, "kind": kind},
        "resolved_scope": {
            "files":    sorted(scope_files),
            "features": sorted(scope_features),
            "symbols":  sorted(scope_symbols),
        },
        "matches": matched,
        "total": len(matched),
    }
    if scope_errors:
        result["warnings"] = scope_errors
    return result


# ---------------------------------------------------------------------------
# List — unfiltered view with optional type/tag filter
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
# Resolve — mark a memory entry as resolved
# ---------------------------------------------------------------------------

def resolve_memory(repo_root: Path, mem_id: str) -> dict:
    """Rewrite mempalace.jsonl with the target entry marked resolved."""
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

    # rewrite the file
    path = store.mempalace_path(repo_root)
    import json as _json
    with path.open("w", encoding="utf-8") as f:
        for e in updated:
            f.write(_json.dumps(e, ensure_ascii=False) + "\n")
    return {"resolved": mem_id}


# ---------------------------------------------------------------------------
# Churn — git-based change frequency (uses git, graceful fallback)
# ---------------------------------------------------------------------------

def compute_churn(repo_root: Path, days: int = 90) -> dict:
    """Count how often each file changed in the last N days via git log.

    Cross-references with the scope feature map to surface high-churn features.
    Falls back gracefully if git is unavailable.
    """
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

    # count appearances
    churn: dict = {}
    for line in result.stdout.splitlines():
        f = line.strip()
        if f:
            churn[f] = churn.get(f, 0) + 1

    if not churn:
        return {"days": days, "files": {}, "features": {},
                "note": "no changes found in git log for this period"}

    # cross-reference with feature map
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
        "features": {
            fid: v for fid, v in top_features
        },
    }


# ---------------------------------------------------------------------------
# Summary stats (used by scope report)
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
