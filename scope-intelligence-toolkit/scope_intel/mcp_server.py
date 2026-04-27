"""MCP stdio server — JSON-RPC 2.0 over stdin/stdout.

Exposes all scope query operations as MCP tools. Zero external dependencies.

Protocol flow:
  client → initialize        server → result (capabilities)
  client → initialized       (notification, no response)
  client → tools/list        server → result (tool schemas)
  client → tools/call        server → result (tool output)

Each JSON-RPC message is a single newline-terminated line.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .core.diff import compute_diff_scope
from .core.mempalace import (
    add_memory,
    compute_churn,
    fetch_relevant,
    list_memories,
)
from .core.query_engine import (
    find_impacted_files,
    get_callees,
    get_callers,
    get_feature_scope,
    get_related_tests,
    get_repo_summary,
    get_symbol_context,
    get_touchpoints,
)
from .core.tracker import compute_savings_summary

SERVER_INFO = {"name": "scope-intelligence", "version": "1.0.0"}

# ---------------------------------------------------------------------------
# Tool definitions (JSON Schema for each MCP tool)
# ---------------------------------------------------------------------------

_REPO_PROP = {
    "repo": {
        "type": "string",
        "description": "Absolute path to the repository root (default: cwd).",
    }
}

TOOLS: list[dict] = [
    {
        "name": "scope_summary",
        "description": "Repo-wide overview: file counts, languages, top features, most-imported files.",
        "inputSchema": {
            "type": "object",
            "properties": _REPO_PROP,
        },
    },
    {
        "name": "scope_features",
        "description": "List all detected features (directory-inferred logical modules).",
        "inputSchema": {
            "type": "object",
            "properties": _REPO_PROP,
        },
    },
    {
        "name": "scope_feature",
        "description": "Full scope for a single feature: files, symbols, tests, dependencies.",
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "name": {"type": "string", "description": "Feature id or alias."},
            },
            "required": ["name"],
        },
    },
    {
        "name": "scope_impacted",
        "description": "Files transitively impacted by changing a file, feature, or symbol.",
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "file": {"type": "string", "description": "Repo-relative file path."},
                "feature": {"type": "string", "description": "Feature id or alias."},
                "symbol": {"type": "string", "description": "Symbol name or qualified id."},
            },
        },
    },
    {
        "name": "scope_tests",
        "description": "Test files covering a given source file or feature.",
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "file": {"type": "string", "description": "Repo-relative file path."},
                "feature": {"type": "string", "description": "Feature id or alias."},
            },
        },
    },
    {
        "name": "scope_symbol",
        "description": "Full context for a symbol: kind, params, reads, writes, callers, callees.",
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "name": {"type": "string", "description": "Symbol name or qualified id."},
            },
            "required": ["name"],
        },
    },
    {
        "name": "scope_callers",
        "description": "All symbols that call a given symbol (cross-file resolved).",
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "name": {"type": "string", "description": "Symbol name or qualified id."},
            },
            "required": ["name"],
        },
    },
    {
        "name": "scope_callees",
        "description": "All symbols called by a given symbol (cross-file resolved).",
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "name": {"type": "string", "description": "Symbol name or qualified id."},
            },
            "required": ["name"],
        },
    },
    {
        "name": "scope_touchpoints",
        "description": "Routes, config keys, DB models, and events found in the repo.",
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "type": {
                    "type": "string",
                    "enum": ["routes", "configs", "db_models", "events"],
                    "description": "Filter to one touchpoint category.",
                },
                "feature": {"type": "string", "description": "Filter by feature id."},
                "file": {"type": "string", "description": "Filter by file path."},
            },
        },
    },
    {
        "name": "scope_diff",
        "description": "Files changed vs a git ref and their transitive impact scope.",
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "ref": {
                    "type": "string",
                    "description": "Git ref to diff against (default: HEAD~1).",
                    "default": "HEAD~1",
                },
            },
        },
    },
    {
        "name": "scope_report",
        "description": "Token savings summary across all past scope queries in the repo.",
        "inputSchema": {
            "type": "object",
            "properties": _REPO_PROP,
        },
    },
    # --- Phase 4: MemPalace tools ---
    {
        "name": "mem_add",
        "description": "Record a long-term memory (bug, decision, failure, ownership, note, fix) scoped to files/features/symbols.",
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "type": {
                    "type": "string",
                    "enum": ["bug", "decision", "failure", "ownership", "note", "fix"],
                    "description": "Memory type.",
                },
                "note": {"type": "string", "description": "The memory text."},
                "files": {"type": "array", "items": {"type": "string"},
                          "description": "Repo-relative file paths this concerns."},
                "features": {"type": "array", "items": {"type": "string"},
                             "description": "Feature ids this concerns."},
                "symbols": {"type": "array", "items": {"type": "string"},
                            "description": "Symbol names this concerns."},
                "tags": {"type": "array", "items": {"type": "string"}},
                "author": {"type": "string"},
                "resolved": {"type": "boolean", "default": False},
            },
            "required": ["note"],
        },
    },
    {
        "name": "mem_fetch",
        "description": "Fetch memories relevant to a feature/file/symbol. Uses the scope engine to resolve related files before filtering.",
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "feature": {"type": "string", "description": "Feature id or alias."},
                "file": {"type": "string", "description": "Repo-relative file path."},
                "symbol": {"type": "string", "description": "Symbol name."},
                "type": {
                    "type": "string",
                    "enum": ["bug", "decision", "failure", "ownership", "note", "fix"],
                    "description": "Filter to one memory type.",
                },
                "include_resolved": {"type": "boolean", "default": False},
                "limit": {"type": "integer", "default": 20},
            },
        },
    },
    {
        "name": "mem_list",
        "description": "List all MemPalace entries with optional type/tag filter.",
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "type": {
                    "type": "string",
                    "enum": ["bug", "decision", "failure", "ownership", "note", "fix"],
                },
                "tag": {"type": "string"},
                "include_resolved": {"type": "boolean", "default": True},
            },
        },
    },
    {
        "name": "mem_churn",
        "description": "Analyse git history to find high-churn files and features (change frequency).",
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "days": {"type": "integer", "default": 90,
                         "description": "Look-back window in days."},
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def _repo(args: dict) -> Path:
    return Path(args.get("repo", ".")).resolve()


def _call_tool(name: str, arguments: dict) -> dict:
    repo = _repo(arguments)

    if name == "scope_summary":
        return get_repo_summary(repo)
    if name == "scope_features":
        from .core import store
        return store.read_json(repo, "features", {"features": []})
    if name == "scope_feature":
        return get_feature_scope(repo, arguments["name"])
    if name == "scope_impacted":
        return find_impacted_files(
            repo,
            file=arguments.get("file"),
            feature=arguments.get("feature"),
            symbol=arguments.get("symbol"),
        )
    if name == "scope_tests":
        return get_related_tests(
            repo,
            file=arguments.get("file"),
            feature=arguments.get("feature"),
        )
    if name == "scope_symbol":
        return get_symbol_context(repo, arguments["name"])
    if name == "scope_callers":
        return get_callers(repo, arguments["name"])
    if name == "scope_callees":
        return get_callees(repo, arguments["name"])
    if name == "scope_touchpoints":
        return get_touchpoints(
            repo,
            kind=arguments.get("type"),
            feature=arguments.get("feature"),
            file=arguments.get("file"),
        )
    if name == "scope_diff":
        return compute_diff_scope(repo, arguments.get("ref", "HEAD~1"))
    if name == "scope_report":
        return compute_savings_summary(repo)

    # --- Phase 4: MemPalace ---
    if name == "mem_add":
        return add_memory(
            repo,
            kind=arguments.get("type", "note"),
            note=arguments["note"],
            files=arguments.get("files", []),
            features=arguments.get("features", []),
            symbols=arguments.get("symbols", []),
            tags=arguments.get("tags", []),
            author=arguments.get("author", ""),
            resolved=arguments.get("resolved", False),
        )
    if name == "mem_fetch":
        return fetch_relevant(
            repo,
            feature=arguments.get("feature"),
            file=arguments.get("file"),
            symbol=arguments.get("symbol"),
            kind=arguments.get("type"),
            include_resolved=arguments.get("include_resolved", False),
            limit=arguments.get("limit", 20),
        )
    if name == "mem_list":
        return list_memories(
            repo,
            kind=arguments.get("type"),
            tag=arguments.get("tag"),
            include_resolved=arguments.get("include_resolved", True),
        )
    if name == "mem_churn":
        return compute_churn(repo, days=arguments.get("days", 90))

    return {"error": f"unknown tool: {name}"}


# ---------------------------------------------------------------------------
# JSON-RPC layer
# ---------------------------------------------------------------------------

def _ok(req_id, result: object) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _err(req_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _handle(msg: dict) -> None:
    req_id = msg.get("id")
    method = msg.get("method", "")

    # Notifications (no id) — acknowledge silently
    if req_id is None:
        return

    if method == "initialize":
        _send(_ok(req_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
        }))

    elif method == "tools/list":
        _send(_ok(req_id, {"tools": TOOLS}))

    elif method == "tools/call":
        params = msg.get("params", {})
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        try:
            result = _call_tool(tool_name, arguments)
            text = json.dumps(result, indent=2, ensure_ascii=False)
            _send(_ok(req_id, {"content": [{"type": "text", "text": text}]}))
        except Exception as exc:  # noqa: BLE001
            _send(_err(req_id, -32603, str(exc)))

    elif method == "ping":
        _send(_ok(req_id, {}))

    else:
        _send(_err(req_id, -32601, f"method not found: {method}"))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def serve() -> None:
    """Read newline-delimited JSON-RPC from stdin, write responses to stdout."""
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except ValueError as exc:
            _send(_err(None, -32700, f"parse error: {exc}"))
            continue
        try:
            _handle(msg)
        except Exception as exc:  # noqa: BLE001
            _send(_err(msg.get("id"), -32603, f"internal error: {exc}"))
