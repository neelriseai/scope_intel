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

Phase 5 additions:
  auto_capture_from_git() — scan git log, auto-create episodic memories
  decay_confidence()      — age semantic memories by half-life
  search_memories()       — TF-IDF free-text search over all memory notes
  export_memories()       — serialize mempalace to portable JSON
  import_memories()       — merge portable JSON back into mempalace
  detect_conflicts()      — flag contradicting semantic memories

Storage: .scope-intelligence/mempalace.jsonl (append-only JSONL)
"""
from __future__ import annotations

import hashlib
import json as _json
import math
import re
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
    half_life_days: Optional[int] = None,
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
        if half_life_days is not None and int(half_life_days) > 0:
            entry["half_life_days"] = int(half_life_days)
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


def _effective_confidence(entry: dict, default_half_life: int = 90) -> float:
    """Compute decayed confidence for a semantic entry without mutating it.

    Non-destructive: stored `confidence` is left alone. Effective value is
    derived at fetch time so reinforcement (`scope mem touch`) and config
    changes take effect immediately.

    formula: base * 0.5^(age_days / half_life)
    """
    base = float(entry.get("confidence", 1.0))
    half_life = int(entry.get("half_life_days") or default_half_life)
    if half_life <= 0:
        return base

    ts_str = entry.get("ts", "")
    try:
        import datetime
        ts_dt = datetime.datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ")
        ts_dt = ts_dt.replace(tzinfo=datetime.timezone.utc)
        age_days = max(0.0, (time.time() - ts_dt.timestamp()) / 86400.0)
    except (ValueError, TypeError):
        return base

    return round(base * (0.5 ** (age_days / half_life)), 4)


def _config_half_life(repo_root: Path) -> int:
    """Read semantic_half_life from config, defaulting to 90 days."""
    cfg = store.read_json(repo_root, "config", {})
    try:
        val = int(cfg.get("semantic_half_life", 90))
        return val if val > 0 else 90
    except (TypeError, ValueError):
        return 90


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

    # semantic: highest effective_confidence first (Phase 6.1 — exponential decay
    # applied at fetch time, original `confidence` is never overwritten).
    half_life = _config_half_life(repo_root)
    decayed: list = []
    for e in semantic_matches:
        eff = _effective_confidence(e, default_half_life=half_life)
        decayed_entry = dict(e)
        decayed_entry["effective_confidence"] = eff
        decayed.append(decayed_entry)
    decayed.sort(key=lambda x: -x["effective_confidence"])
    semantic_matches = decayed

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


# ---------------------------------------------------------------------------
# Phase 5 — Auto-episodic capture from git
# ---------------------------------------------------------------------------

_BUG_KEYWORDS = re.compile(
    r"\b(fix|bug|error|broken|crash|revert|regression|hotfix|patch|oops)\b", re.I
)
_DECISION_KEYWORDS = re.compile(
    r"\b(refactor|design|switch|migrate|choose|replace|adopt|deprecate|drop|upgrade)\b", re.I
)
_FEAT_KEYWORDS = re.compile(
    r"\b(feat|feature|add|implement|introduce|support|enable)\b", re.I
)


def auto_capture_from_git(
    repo_root: Path,
    *,
    days: int = 30,
    dry_run: bool = False,
    author: str = "auto-capture",
) -> dict:
    """Scan recent git log and create episodic memories for notable commits.

    Commit classification:
      bug/fix keywords  → type="fix"
      decision keywords → type="decision"
      feat keywords     → type="note"

    Already-captured commits (id contains commit hash) are skipped.
    Returns: {captured, skipped_existing, skipped_unclassified, dry_run, entries[]}
    """
    if not store.is_initialized(repo_root):
        return {"error": "repo not indexed — run scope init first"}

    try:
        result = subprocess.run(
            ["git", "log", f"--since={days} days ago",
             "--format=%H|%aI|%ae|%s", "--name-only", "--diff-filter=AM"],
            cwd=str(repo_root),
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return {"error": "git log failed — is this a git repo?"}
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {"error": str(exc)}

    # parse blocks separated by blank lines
    existing = store.read_mempalace(repo_root)
    existing_hashes = {
        e.get("git_hash") for e in existing if e.get("git_hash")
    }

    commits: list = []
    current: dict = {}
    for line in result.stdout.splitlines():
        if "|" in line and len(line.split("|")) >= 4:
            parts = line.split("|", 3)
            current = {
                "hash": parts[0].strip(),
                "ts": parts[1].strip(),
                "email": parts[2].strip(),
                "subject": parts[3].strip(),
                "files": [],
            }
            commits.append(current)
        elif line.strip() and current:
            current["files"].append(line.strip())

    captured, skipped_existing, skipped_unclassified = 0, 0, 0
    new_entries: list = []

    for c in commits:
        if c["hash"] in existing_hashes:
            skipped_existing += 1
            continue

        subject = c["subject"]
        if _BUG_KEYWORDS.search(subject):
            kind = "fix"
        elif _DECISION_KEYWORDS.search(subject):
            kind = "decision"
        elif _FEAT_KEYWORDS.search(subject):
            kind = "note"
        else:
            skipped_unclassified += 1
            continue

        # map changed files to known features
        features_data = store.read_json(repo_root, "features", {"features": []})
        touched_features: list = []
        for feat in features_data.get("features", []):
            feat_files = set(feat.get("files", []))
            if feat_files & set(c["files"]):
                touched_features.append(feat["id"])

        entry = add_memory(
            repo_root, kind,
            note=f"[git] {subject}",
            files=c["files"][:10],
            features=touched_features,
            author=c.get("email") or author,
        ) if not dry_run else {
            "id": "dry_run",
            "type": kind,
            "note": f"[git] {subject}",
            "git_hash": c["hash"],
            "files": c["files"][:10],
            "features": touched_features,
        }

        if not dry_run and "error" not in entry:
            # patch in git_hash for dedup on future runs
            existing_entries = store.read_mempalace(repo_root)
            last = existing_entries[-1] if existing_entries else {}
            if last.get("id") == entry.get("id"):
                last["git_hash"] = c["hash"]
                _rewrite_mempalace(repo_root, existing_entries[:-1] + [last])

        new_entries.append({**entry, "git_hash": c["hash"]})
        captured += 1

    return {
        "captured": captured,
        "skipped_existing": skipped_existing,
        "skipped_unclassified": skipped_unclassified,
        "dry_run": dry_run,
        "days_scanned": days,
        "entries": new_entries,
    }


def touch_memory(repo_root: Path, mem_id: str) -> dict:
    """Reinforce a memory by refreshing its ts; preserves prior ts in history.

    Effect: effective_confidence at next fetch jumps back to the base value.
    The previous ts is appended to `reinforced_at` so we keep the history.

    Returns the updated entry, or {error: ...} if not found.
    """
    if not store.is_initialized(repo_root):
        return {"error": "repo not indexed — run scope init first"}

    entries = store.read_mempalace(repo_root)
    target_idx: Optional[int] = None
    for i, e in enumerate(entries):
        if e.get("id") == mem_id:
            target_idx = i
            break
    if target_idx is None:
        return {"error": f"no memory with id '{mem_id}'"}

    entry = dict(entries[target_idx])
    old_ts = entry.get("ts", "")
    new_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    history = list(entry.get("reinforced_at", []))
    if old_ts:
        history.append(old_ts)
    entry["ts"] = new_ts
    entry["reinforced_at"] = history

    entries[target_idx] = entry
    _rewrite_mempalace(repo_root, entries)
    return entry


def prune_memories(
    repo_root: Path,
    *,
    below: float = 0.2,
    dry_run: bool = False,
    half_life_days: Optional[int] = None,
) -> dict:
    """Delete semantic memories whose *effective* confidence has dropped below a threshold.

    Unlike ``decay_confidence`` (which rewrites stored values), this removes
    entries entirely so the JSONL shrinks. Non-semantic entries are never pruned.

    Args:
        below:         Entries with effective_confidence < below are pruned.
        dry_run:       Preview only — nothing is deleted.
        half_life_days: Override the repo default (config.semantic_half_life).

    Returns {pruned, kept, dry_run, removed[{id, note, effective_confidence}]}
    """
    if not store.is_initialized(repo_root):
        return {"error": "repo not indexed — run scope init first"}

    hl = half_life_days if (half_life_days and half_life_days > 0) else _config_half_life(repo_root)

    entries = store.read_mempalace(repo_root)
    kept: list = []
    removed: list = []

    for e in entries:
        if e.get("type") != "semantic":
            kept.append(e)
            continue
        eff = _effective_confidence(e, default_half_life=hl)
        if eff < below:
            removed.append({
                "id":                    e["id"],
                "note":                  e.get("note", "")[:80],
                "effective_confidence":  eff,
                "confidence":            e.get("confidence", 1.0),
            })
        else:
            kept.append(e)

    if not dry_run and removed:
        _rewrite_mempalace(repo_root, kept)

    return {
        "pruned":   len(removed) if not dry_run else 0,
        "removed":  removed,
        "kept":     len(kept),
        "dry_run":  dry_run,
        "threshold": below,
    }


def _rewrite_mempalace(repo_root: Path, entries: list) -> None:
    path = store.mempalace_path(repo_root)
    with path.open("w", encoding="utf-8") as f:
        for e in entries:
            f.write(_json.dumps(e, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Phase 5 — Confidence decay
# ---------------------------------------------------------------------------

def decay_confidence(
    repo_root: Path,
    *,
    half_life_days: int = 90,
    floor: float = 0.1,
    dry_run: bool = False,
) -> dict:
    """Apply exponential confidence decay to all semantic memories.

    new_confidence = max(floor, original * 0.5^(age_days / half_life_days))

    Decay is applied relative to the memory's creation timestamp.
    Returns: {updated, unchanged, dry_run, changes[]}
    """
    if not store.is_initialized(repo_root):
        return {"error": "repo not indexed — run scope init first"}

    entries = store.read_mempalace(repo_root)
    now = time.time()
    updated_entries: list = []
    changes: list = []
    updated_count = 0
    unchanged_count = 0

    for e in entries:
        if e.get("type") != "semantic":
            updated_entries.append(e)
            continue

        ts_str = e.get("ts", "")
        try:
            import datetime
            ts_dt = datetime.datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ")
            ts_dt = ts_dt.replace(tzinfo=datetime.timezone.utc)
            age_days = (now - ts_dt.timestamp()) / 86400
        except (ValueError, OSError):
            updated_entries.append(e)
            unchanged_count += 1
            continue

        old_conf = e.get("confidence", 1.0)
        decay_factor = 0.5 ** (age_days / half_life_days)
        new_conf = round(max(floor, old_conf * decay_factor), 4)

        if abs(new_conf - old_conf) < 0.0001:
            updated_entries.append(e)
            unchanged_count += 1
            continue

        changes.append({
            "id": e["id"],
            "note": e.get("note", "")[:60],
            "age_days": round(age_days, 1),
            "old_confidence": old_conf,
            "new_confidence": new_conf,
        })

        new_e = dict(e)
        new_e["confidence"] = new_conf
        updated_entries.append(new_e)
        updated_count += 1

    if not dry_run and changes:
        _rewrite_mempalace(repo_root, updated_entries)

    return {
        "updated": updated_count,
        "unchanged": unchanged_count,
        "dry_run": dry_run,
        "half_life_days": half_life_days,
        "floor": floor,
        "changes": changes,
    }


# ---------------------------------------------------------------------------
# Phase 5 — TF-IDF semantic search
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list:
    return re.findall(r"[a-z0-9_]+", text.lower())


def search_memories(
    repo_root: Path,
    query: str,
    *,
    kind: Optional[str] = None,
    include_resolved: bool = False,
    limit: int = 10,
) -> dict:
    """Search all memory notes using TF-IDF similarity.

    Returns memories ranked by relevance to the free-text query.
    Falls back to substring match if TF-IDF yields no results.
    """
    if not store.is_initialized(repo_root):
        return {"error": "repo not indexed — run scope init first"}

    all_entries = store.read_mempalace(repo_root)
    candidates: list = []
    for e in all_entries:
        if e.get("resolved") and not include_resolved:
            continue
        if kind and e.get("type") != kind:
            continue
        candidates.append(e)

    if not candidates:
        return {"query": query, "results": [], "total": 0}

    # build corpus: note + step text + tags
    def _doc(e: dict) -> str:
        parts = [e.get("note", "")]
        parts.extend(e.get("steps", []))
        parts.extend(e.get("tags", []))
        return " ".join(parts)

    docs = [_doc(e) for e in candidates]
    query_tokens = set(_tokenize(query))

    # compute IDF across corpus
    N = len(docs)
    df: dict = {}
    tokenized_docs: list = []
    for doc in docs:
        tokens = _tokenize(doc)
        tokenized_docs.append(tokens)
        for tok in set(tokens):
            df[tok] = df.get(tok, 0) + 1

    idf: dict = {
        tok: math.log((N + 1) / (freq + 1)) + 1
        for tok, freq in df.items()
    }

    # score each document against query
    scored: list = []
    for i, (tokens, e) in enumerate(zip(tokenized_docs, candidates)):
        if not tokens:
            continue
        tf: dict = {}
        for tok in tokens:
            tf[tok] = tf.get(tok, 0) + 1
        score = 0.0
        for qtok in query_tokens:
            if qtok in tf:
                score += (tf[qtok] / len(tokens)) * idf.get(qtok, 1.0)
        if score > 0:
            scored.append((score, e))

    scored.sort(key=lambda x: -x[0])

    # fallback: substring match if TF-IDF returned nothing
    if not scored:
        ql = query.lower()
        for e in candidates:
            if ql in _doc(e).lower():
                scored.append((0.01, e))

    results = [
        {**e, "_score": round(s, 4)}
        for s, e in scored[:limit]
    ]

    return {
        "query": query,
        "results": results,
        "total": len(results),
    }


# ---------------------------------------------------------------------------
# Phase 5 — Export / Import
# ---------------------------------------------------------------------------

def export_memories(repo_root: Path, output_path: Path) -> dict:
    """Export all mempalace entries to a portable JSON file."""
    if not store.is_initialized(repo_root):
        return {"error": "repo not indexed — run scope init first"}

    entries = store.read_mempalace(repo_root)
    payload = {
        "version": 1,
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "repo": str(repo_root),
        "total": len(entries),
        "entries": entries,
    }
    output_path = Path(output_path)
    output_path.write_text(_json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "exported": len(entries),
        "output": str(output_path),
    }


def import_memories(
    repo_root: Path,
    input_path: Path,
    *,
    merge: bool = True,
) -> dict:
    """Import memories from a portable JSON file.

    merge=True (default): skip entries whose id already exists.
    merge=False: replace mempalace entirely with the imported set.
    """
    if not store.is_initialized(repo_root):
        return {"error": "repo not indexed — run scope init first"}

    input_path = Path(input_path)
    if not input_path.exists():
        return {"error": f"file not found: {input_path}"}

    try:
        payload = _json.loads(input_path.read_text(encoding="utf-8"))
    except _json.JSONDecodeError as exc:
        return {"error": f"invalid JSON: {exc}"}

    incoming = payload.get("entries", [])
    if not incoming:
        return {"imported": 0, "skipped": 0, "note": "no entries in file"}

    if not merge:
        _rewrite_mempalace(repo_root, incoming)
        return {"imported": len(incoming), "skipped": 0, "replaced": True}

    existing = store.read_mempalace(repo_root)
    existing_ids = {e.get("id") for e in existing}
    added: list = []
    skipped = 0
    for e in incoming:
        if e.get("id") in existing_ids:
            skipped += 1
            continue
        store.append_mempalace(repo_root, e)
        added.append(e)

    return {
        "imported": len(added),
        "skipped": skipped,
        "source": str(input_path),
    }


# ---------------------------------------------------------------------------
# Phase 5 — Conflict detection
# ---------------------------------------------------------------------------

_NEGATION_PATTERNS = [
    (re.compile(r"\buse[sd]?\b", re.I), re.compile(r"\bdoes not use\b|\bnot use\b|\bavoid\b|\bno longer\b", re.I)),
    (re.compile(r"\bJWT\b"), re.compile(r"\bsession\b|\bcookie\b", re.I)),
    (re.compile(r"\bsession\b", re.I), re.compile(r"\bJWT\b|\btoken\b", re.I)),
    (re.compile(r"\bPostgres\b", re.I), re.compile(r"\bMySQL\b|\bSQLite\b|\bMongo\b", re.I)),
    (re.compile(r"\bsync\b", re.I), re.compile(r"\basync\b|\bawait\b", re.I)),
    (re.compile(r"\bdeprecated\b", re.I), re.compile(r"\bactive\b|\bcurrent\b|\blatest\b", re.I)),
]


def _notes_conflict(note_a: str, note_b: str) -> bool:
    """Heuristic: do two notes appear to contradict each other?"""
    a, b = note_a.lower(), note_b.lower()
    for pos_pat, neg_pat in _NEGATION_PATTERNS:
        if pos_pat.search(a) and neg_pat.search(b):
            return True
        if pos_pat.search(b) and neg_pat.search(a):
            return True
    # direct negation: one note contains "not X" and the other contains "X"
    words_a = set(_tokenize(a))
    words_b = set(_tokenize(b))
    shared = words_a & words_b
    if not shared:
        return False
    neg_a = bool(re.search(r"\bnot\b|\bno\b|\bnever\b|\bremoved\b", a))
    neg_b = bool(re.search(r"\bnot\b|\bno\b|\bnever\b|\bremoved\b", b))
    return neg_a != neg_b and bool(shared - {"the", "a", "is", "in", "of", "and", "or"})


def detect_conflicts(
    repo_root: Path,
    *,
    include_resolved: bool = False,
) -> dict:
    """Detect potentially contradicting semantic memories.

    Checks pairs of semantic memories that share file/feature scope.
    Returns a list of conflict pairs with an explanation.
    """
    if not store.is_initialized(repo_root):
        return {"error": "repo not indexed — run scope init first"}

    entries = store.read_mempalace(repo_root)
    semantics = [
        e for e in entries
        if e.get("type") == "semantic"
        and (include_resolved or not e.get("resolved"))
    ]

    conflicts: list = []
    checked = set()

    for i, a in enumerate(semantics):
        a_files = set(a.get("scope", {}).get("files", []))
        a_feats = set(a.get("scope", {}).get("features", []))

        for j, b in enumerate(semantics):
            if j <= i:
                continue
            pair_key = (a["id"], b["id"])
            if pair_key in checked:
                continue
            checked.add(pair_key)

            b_files = set(b.get("scope", {}).get("files", []))
            b_feats = set(b.get("scope", {}).get("features", []))

            # only compare memories in overlapping scope
            scope_overlap = bool(
                (a_files & b_files) or (a_feats & b_feats)
                or (not a_files and not a_feats)  # global memories
                or (not b_files and not b_feats)
            )
            if not scope_overlap:
                continue

            if _notes_conflict(a.get("note", ""), b.get("note", "")):
                conflicts.append({
                    "memory_a": {"id": a["id"], "note": a.get("note"), "ts": a.get("ts"),
                                 "confidence": a.get("confidence", 1.0)},
                    "memory_b": {"id": b["id"], "note": b.get("note"), "ts": b.get("ts"),
                                 "confidence": b.get("confidence", 1.0)},
                    "shared_files": sorted(a_files & b_files),
                    "shared_features": sorted(a_feats & b_feats),
                    "suggestion": "Review both — resolve the outdated one with: scope mem resolve <id>",
                })

    return {
        "conflicts": conflicts,
        "total": len(conflicts),
        "semantic_checked": len(semantics),
    }


# ---------------------------------------------------------------------------
# Phase 6.2 — Agent-triggered capture
# ---------------------------------------------------------------------------

#: Valid signal types for capture().  Each maps to a memory type + confidence cap.
CAPTURE_SIGNALS: dict[str, dict] = {
    "repeated-error":   {"type": "failure",  "confidence": None,  "cap": 0.7},
    "surprising-fix":   {"type": "fix",      "confidence": None,  "cap": 0.7},
    "validated-claim":  {"type": "semantic", "confidence": 0.7,   "cap": 0.7},
    "repeated-lookup":  {"type": "procedure","confidence": None,   "cap": 0.7},
    "scope-mismatch":   {"type": "note",     "confidence": None,   "cap": 0.7},
}

#: Max captures per signal per hour (rate-limit)
_CAPTURE_RATE_LIMIT = 5


def capture_memory(
    repo_root: Path,
    signal: str,
    evidence: str,
    *,
    feature: Optional[str] = None,
    file: Optional[str] = None,
    symbol: Optional[str] = None,
    author: str = "agent",
    dry_run: bool = False,
) -> dict:
    """Record an agent-triggered memory capture.

    Agents call this when they detect a high-signal event during a session.
    Unlike ``add_memory`` (which is human-facing), capture:
      - Validates against known signal types
      - Caps confidence at 0.7 so agent entries never outrank human ones
      - Rate-limits to ``_CAPTURE_RATE_LIMIT`` per signal per hour to prevent spam
      - Tags the entry as source='agent' for filtering/pruning

    Args:
        signal:   One of CAPTURE_SIGNALS keys (repeated-error, validated-claim, etc.)
        evidence: The text to record (e.g. error message, assertion text).
        feature / file / symbol: Scope hints for routing.
        author:   Agent identifier (default: "agent").
        dry_run:  Preview without writing.

    Returns entry dict on success, or {error: ...}.
    """
    if not store.is_initialized(repo_root):
        return {"error": "repo not indexed — run scope init first"}

    if signal not in CAPTURE_SIGNALS:
        valid = ", ".join(CAPTURE_SIGNALS)
        return {"error": f"unknown signal '{signal}' — valid: {valid}"}

    sig_meta = CAPTURE_SIGNALS[signal]
    kind = sig_meta["type"]
    confidence = sig_meta.get("confidence") or 0.7

    # Rate-limit: count same-signal captures in the last hour
    cutoff_ts = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ",
        time.gmtime(time.time() - 3600),
    )
    existing = store.read_mempalace(repo_root)
    recent_same_signal = sum(
        1 for e in existing
        if e.get("tags") and f"signal:{signal}" in e["tags"]
        and e.get("ts", "") >= cutoff_ts
    )
    if recent_same_signal >= _CAPTURE_RATE_LIMIT:
        return {
            "error": (
                f"rate limit reached: {_CAPTURE_RATE_LIMIT} '{signal}' captures "
                f"in the last hour. Try again later or use `scope mem add` directly."
            ),
            "rate_limited": True,
        }

    tags = [f"signal:{signal}", "source:agent"]
    scope_files = [file] if file else []
    scope_features = [feature] if feature else []
    scope_symbols = [symbol] if symbol else []

    entry: dict = {
        "id":       _make_id(evidence, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
        "ts":       time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "type":     kind,
        "note":     evidence,
        "scope": {
            "files":    scope_files,
            "features": scope_features,
            "symbols":  scope_symbols,
        },
        "tags":    tags,
        "author":  author,
        "resolved": False,
    }
    if kind == "semantic":
        entry["confidence"] = confidence

    if dry_run:
        return {"dry_run": True, "would_capture": entry}

    store.append_mempalace(repo_root, entry)
    return entry
