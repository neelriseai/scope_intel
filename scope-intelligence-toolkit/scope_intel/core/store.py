"""Read/write helpers for the per-repo `.scope-intelligence/` folder.

The folder layout is intentionally flat and JSON-only so it stays diff-friendly
and tool-agnostic.

  .scope-intelligence/
    config.json           # user-editable: feature overrides, ignore globs, aliases
    repo_summary.json     # cached compact repo overview
    features.json         # feature index (see schemas/feature_map_schema.json)
    symbols.json          # symbol index   (see schemas/symbol_schema.json)
    dependencies.json     # file + external deps  (see schemas/dependency_schema.json)
    tests.json            # test mapping
    aliases.json          # feature aliases
    packages.json         # logical package roster
    summaries/            # per-feature one-liner descriptions (optional)
    state.json            # last index timestamp / file hashes
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

INDEX_DIR_NAME = ".scope-intelligence"
SCHEMA_VERSION = "1.0"

FILES = {
    "config":       "config.json",
    "summary":      "repo_summary.json",
    "features":     "features.json",
    "symbols":      "symbols.json",
    "dependencies": "dependencies.json",
    "tests":        "tests.json",
    "aliases":      "aliases.json",
    "packages":     "packages.json",
    "touchpoints":  "touchpoints.json",
    "state":        "state.json",
}

QUERY_LOG_NAME = "query_log.jsonl"
MEMPALACE_NAME = "mempalace.jsonl"


def query_log_path(repo_root: Path) -> Path:
    return index_dir(repo_root) / QUERY_LOG_NAME


def append_query_log(repo_root: Path, entry: dict) -> None:
    import json as _json
    path = query_log_path(repo_root)
    with path.open("a", encoding="utf-8") as f:
        f.write(_json.dumps(entry, ensure_ascii=False) + "\n")


def read_query_log(repo_root: Path) -> list:
    import json as _json
    path = query_log_path(repo_root)
    if not path.exists():
        return []
    entries: list = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(_json.loads(line))
        except ValueError:
            pass
    return entries


def mempalace_path(repo_root: Path) -> Path:
    return index_dir(repo_root) / MEMPALACE_NAME


def append_mempalace(repo_root: Path, entry: dict) -> None:
    import json as _json
    path = mempalace_path(repo_root)
    with path.open("a", encoding="utf-8") as f:
        f.write(_json.dumps(entry, ensure_ascii=False) + "\n")


def read_mempalace(repo_root: Path) -> list:
    import json as _json
    path = mempalace_path(repo_root)
    if not path.exists():
        return []
    entries: list = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(_json.loads(line))
        except ValueError:
            pass
    return entries


def index_dir(repo_root: Path) -> Path:
    return repo_root / INDEX_DIR_NAME


def ensure_index_dir(repo_root: Path) -> Path:
    d = index_dir(repo_root)
    d.mkdir(parents=True, exist_ok=True)
    (d / "summaries").mkdir(exist_ok=True)
    return d


def write_json(repo_root: Path, key: str, payload: Any) -> Path:
    d = ensure_index_dir(repo_root)
    target = d / FILES[key]
    target.write_text(
        json.dumps(payload, indent=2, sort_keys=False, ensure_ascii=False),
        encoding="utf-8",
    )
    return target


def read_json(repo_root: Path, key: str, default: Any = None) -> Any:
    target = index_dir(repo_root) / FILES[key]
    if not target.exists():
        return default
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def is_initialized(repo_root: Path) -> bool:
    return index_dir(repo_root).exists()


def write_summary_md(repo_root: Path, feature_id: str, body: str) -> Path:
    d = ensure_index_dir(repo_root)
    target = d / "summaries" / f"{feature_id}.md"
    target.write_text(body, encoding="utf-8")
    return target


def default_config() -> dict:
    return {
        "version": SCHEMA_VERSION,
        "ignore_globs": [
            ".git/**", "node_modules/**", "venv/**", ".venv/**",
            "__pycache__/**", "dist/**", "build/**", "target/**",
            "out/**", ".scope-intelligence/**", ".idea/**", ".vscode/**",
            "*.min.js", "*.lock",
        ],
        "feature_roots": [
            "src", "app", "lib", "packages", "modules", "services",
        ],
        "feature_overrides": {},
        "aliases": {},
        "max_file_size_kb": 512,
    }
