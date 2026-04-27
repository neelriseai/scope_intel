"""Query tracking and token-savings estimation.

Every scope query logs a compact entry to `.scope-intelligence/query_log.jsonl`.
Savings are estimated by comparing:
  - "naive" approach: reading every file in the repo (sum of all LOC)
  - "scope" approach: reading only the files surfaced by the query

Tokens are estimated at a conservative 10 tokens / line-of-code (≈ 50 chars/line,
4–5 chars/token).  This deliberately under-counts to avoid inflated claims.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from . import store

TOKENS_PER_LOC = 10          # conservative: 50 chars/line ÷ 5 chars/token
GLOB_OVERHEAD = 500          # tokens a naive Glob(*) scan costs regardless
READ_OVERHEAD = 50           # tokens per Read call overhead


def _loc_for(files: list, files_index: dict) -> int:
    return sum(files_index.get(f, {}).get("loc") or 0 for f in files)


def _estimate_tokens(loc: int) -> int:
    return loc * TOKENS_PER_LOC


def log_query(
    repo_root: Path,
    command: str,
    query_args: dict,
    result_files: list,
    *,
    latency_ms: int = 0,
    extra: Optional[dict] = None,
) -> dict:
    """Build a log entry and append it to query_log.jsonl.

    Returns the entry dict so the caller can use it (e.g. for the report).
    """
    if not store.is_initialized(repo_root):
        return {}

    deps = store.read_json(repo_root, "dependencies", {"files": {}})
    files_index: dict = deps.get("files", {})
    all_files = list(files_index.keys())
    total_files = len(all_files)
    total_loc = _loc_for(all_files, files_index)

    scope_files = list(result_files)
    scope_loc = _loc_for(scope_files, files_index)
    avoided_files = total_files - len(scope_files)
    avoided_loc = total_loc - scope_loc

    naive_tokens = _estimate_tokens(total_loc) + GLOB_OVERHEAD
    scope_tokens = _estimate_tokens(scope_loc) + READ_OVERHEAD * max(len(scope_files), 1)
    tokens_saved = max(naive_tokens - scope_tokens, 0)

    entry: dict = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "cmd": command,
        "args": query_args,
        "result_files": len(scope_files),
        "result_loc": scope_loc,
        "total_repo_files": total_files,
        "total_repo_loc": total_loc,
        "avoided_files": avoided_files,
        "avoided_loc": avoided_loc,
        "naive_tokens_est": naive_tokens,
        "scope_tokens_est": scope_tokens,
        "tokens_saved_est": tokens_saved,
        "latency_ms": latency_ms,
    }
    if extra:
        entry.update(extra)
    store.append_query_log(repo_root, entry)
    return entry


def compute_savings_summary(repo_root: Path) -> dict:
    """Aggregate all query log entries into a savings report dict."""
    entries = store.read_query_log(repo_root)
    if not entries:
        return {
            "total_queries": 0,
            "note": "No queries logged yet. Run some scope commands first.",
        }

    total_saved = sum(e.get("tokens_saved_est", 0) for e in entries)
    total_naive = sum(e.get("naive_tokens_est", 0) for e in entries)
    total_scope = sum(e.get("scope_tokens_est", 0) for e in entries)
    total_avoided_files = sum(e.get("avoided_files", 0) for e in entries)
    total_avoided_loc = sum(e.get("avoided_loc", 0) for e in entries)
    avg_latency = (sum(e.get("latency_ms", 0) for e in entries) / len(entries)) if entries else 0

    by_cmd: dict = {}
    for e in entries:
        cmd = e.get("cmd", "?")
        if cmd not in by_cmd:
            by_cmd[cmd] = {"queries": 0, "tokens_saved": 0}
        by_cmd[cmd]["queries"] += 1
        by_cmd[cmd]["tokens_saved"] += e.get("tokens_saved_est", 0)

    savings_pct = round(100 * total_saved / total_naive, 1) if total_naive else 0

    return {
        "total_queries": len(entries),
        "total_tokens_saved_est": total_saved,
        "total_naive_tokens_est": total_naive,
        "total_scope_tokens_est": total_scope,
        "savings_percent": savings_pct,
        "total_files_avoided": total_avoided_files,
        "total_loc_avoided": total_avoided_loc,
        "avg_latency_ms": round(avg_latency, 1),
        "by_command": dict(sorted(by_cmd.items(), key=lambda kv: -kv[1]["tokens_saved"])),
        "recent_queries": entries[-20:][::-1],
    }
