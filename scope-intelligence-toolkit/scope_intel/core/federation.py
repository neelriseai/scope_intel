"""Phase 6.3 — Cross-repo memory federation.

Stores a federation manifest at ~/.scope-intelligence/federation.json
(user-global, not per-repo). Links let `mem fetch` pull in memories
from satellite repos without duplicating their JSONLs.

Federation manifest schema
--------------------------
{
  "repos": [
    {"path": "/abs/path/to/repo", "alias": "payments"},
    ...
  ],
  "links": [
    {"from": "billing", "to": "shared", "scope": "semantic+procedure"},
    ...
  ]
}

Scope values: "all" | "semantic" | "procedure" | "episodic"
              or "+"-joined combination, e.g. "semantic+procedure"
"""
from __future__ import annotations

import json as _json
import os
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Federation manifest location (user-global)
# ---------------------------------------------------------------------------

def _federation_path() -> Path:
    """Return the user-global federation manifest path."""
    base = Path.home() / ".scope-intelligence"
    base.mkdir(parents=True, exist_ok=True)
    return base / "federation.json"


def _load_manifest() -> dict:
    p = _federation_path()
    if not p.exists():
        return {"repos": [], "links": []}
    try:
        return _json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"repos": [], "links": []}


def _save_manifest(manifest: dict) -> None:
    _federation_path().write_text(
        _json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def federation_add(path: str, alias: str) -> dict:
    """Register a repo in the federation.

    Returns {ok, alias, path} or {error: ...}.
    """
    resolved = str(Path(path).expanduser().resolve())
    if not Path(resolved).is_dir():
        return {"error": f"path does not exist or is not a directory: {resolved}"}

    manifest = _load_manifest()
    # Reject duplicate aliases
    for r in manifest["repos"]:
        if r["alias"] == alias:
            if r["path"] == resolved:
                return {"ok": True, "alias": alias, "path": resolved,
                        "note": "already registered"}
            return {"error": f"alias '{alias}' already exists for a different path: {r['path']}"}
    manifest["repos"].append({"path": resolved, "alias": alias})
    _save_manifest(manifest)
    return {"ok": True, "alias": alias, "path": resolved}


def federation_remove(alias: str) -> dict:
    """Remove a repo and all its links from the federation."""
    manifest = _load_manifest()
    before = len(manifest["repos"])
    manifest["repos"] = [r for r in manifest["repos"] if r["alias"] != alias]
    manifest["links"] = [
        lk for lk in manifest["links"]
        if lk["from"] != alias and lk["to"] != alias
    ]
    if len(manifest["repos"]) == before:
        return {"error": f"no repo with alias '{alias}' found"}
    _save_manifest(manifest)
    return {"ok": True, "removed": alias}


def federation_link(from_alias: str, to_alias: str, scope: str = "all") -> dict:
    """Add a directional memory link: from_alias will pull memories from to_alias.

    scope: 'all' | 'semantic' | 'procedure' | 'episodic'
           or '+'-joined subset, e.g. 'semantic+procedure'
    """
    valid_scopes = {"all", "semantic", "procedure", "episodic"}
    parts = set(scope.split("+"))
    if not parts.issubset(valid_scopes):
        bad = parts - valid_scopes
        return {"error": f"unknown scope(s): {bad} — valid: {valid_scopes}"}

    manifest = _load_manifest()
    aliases = {r["alias"] for r in manifest["repos"]}
    for a in (from_alias, to_alias):
        if a not in aliases:
            return {"error": f"alias '{a}' not found — add it first with `scope mem federation add`"}

    # Avoid duplicates
    for lk in manifest["links"]:
        if lk["from"] == from_alias and lk["to"] == to_alias:
            lk["scope"] = scope  # update scope in place
            _save_manifest(manifest)
            return {"ok": True, "from": from_alias, "to": to_alias,
                    "scope": scope, "note": "updated existing link"}

    manifest["links"].append({"from": from_alias, "to": to_alias, "scope": scope})
    _save_manifest(manifest)
    return {"ok": True, "from": from_alias, "to": to_alias, "scope": scope}


def federation_list() -> dict:
    """Return the full federation manifest."""
    manifest = _load_manifest()
    return {
        "repos": manifest.get("repos", []),
        "links": manifest.get("links", []),
        "manifest_path": str(_federation_path()),
    }


def _alias_to_path(alias: str, manifest: dict) -> Optional[Path]:
    for r in manifest.get("repos", []):
        if r["alias"] == alias:
            return Path(r["path"])
    return None


def _scope_allows(entry_type: str, scope: str) -> bool:
    """Return True if the link scope allows this memory type."""
    if scope == "all":
        return True
    parts = scope.split("+")
    # Map memory types to scope words
    type_to_scope = {
        "semantic":  "semantic",
        "procedure": "procedure",
        "bug":       "episodic",
        "decision":  "episodic",
        "failure":   "episodic",
        "fix":       "episodic",
        "note":      "episodic",
        "ownership": "episodic",
    }
    return type_to_scope.get(entry_type, "episodic") in parts


def federated_fetch(
    repo_root: Path,
    *,
    feature: Optional[str] = None,
    file: Optional[str] = None,
    symbol: Optional[str] = None,
) -> dict:
    """Pull memories from linked repos.

    Finds which alias corresponds to repo_root, follows outbound links,
    reads mempalace.jsonl from each satellite, and returns merged memories
    annotated with their source alias.

    Returns:
        {
          "local_alias": str | None,
          "sources": [
            {"alias": str, "path": str, "entries": [...], "error": str|None}
          ],
          "total_remote": int
        }
    """
    from .store import read_mempalace as _read

    manifest = _load_manifest()
    resolved = str(repo_root.resolve())

    # Identify local alias
    local_alias: Optional[str] = None
    for r in manifest.get("repos", []):
        if r["path"] == resolved:
            local_alias = r["alias"]
            break

    if local_alias is None:
        return {
            "local_alias": None,
            "sources": [],
            "total_remote": 0,
            "note": "this repo is not in the federation — add with `scope mem federation add`",
        }

    # Find outbound links
    sources: list[dict] = []
    total_remote = 0

    for link in manifest.get("links", []):
        if link["from"] != local_alias:
            continue
        sat_alias = link["to"]
        sat_path = _alias_to_path(sat_alias, manifest)
        if sat_path is None:
            sources.append({"alias": sat_alias, "path": "?",
                            "entries": [], "error": "alias not found in manifest"})
            continue

        scope = link.get("scope", "all")
        try:
            raw = _read(sat_path)
        except Exception as exc:  # noqa: BLE001
            sources.append({"alias": sat_alias, "path": str(sat_path),
                            "entries": [], "error": str(exc)})
            continue

        # Filter by scope + basic relevance (feature/file/symbol match)
        matched: list[dict] = []
        for e in raw:
            if not _scope_allows(e.get("type", "note"), scope):
                continue
            # Relevance: no filter → all; otherwise scope-match
            if feature or file or symbol:
                e_feats = set(e.get("scope", {}).get("features", []))
                e_files = set(e.get("scope", {}).get("files", []))
                e_syms  = set(e.get("scope", {}).get("symbols", []))
                wanted_feats = {feature} if feature else set()
                wanted_files = {file}    if file    else set()
                wanted_syms  = {symbol}  if symbol  else set()
                if not (e_feats & wanted_feats or
                        e_files & wanted_files or
                        e_syms  & wanted_syms):
                    continue
            annotated = dict(e)
            annotated["_federation_source"] = sat_alias
            matched.append(annotated)

        sources.append({
            "alias":   sat_alias,
            "path":    str(sat_path),
            "entries": matched,
            "error":   None,
        })
        total_remote += len(matched)

    return {
        "local_alias":  local_alias,
        "sources":      sources,
        "total_remote": total_remote,
    }
