"""`scope diff <git-ref>` — compute scope impact of a git change set.

Given a git ref (e.g. `HEAD~1`, `main`, a tag), shell out to git to find
which tracked files differ from the ref to the working tree, then run the
existing impact-graph machinery against the union of those files.

This module is intentionally git-only for Phase 2. If git is not available
or the repo is not a git checkout, callers get a structured error.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from . import store
from .graph_builder import collect_impacted


def _git_changed_files(repo_root: Path, ref: str) -> tuple:
    """Return (added_or_modified, removed) lists, both repo-relative POSIX paths."""
    if shutil.which("git") is None:
        raise RuntimeError("git executable not found on PATH")
    if not (repo_root / ".git").exists():
        # support submodules / worktrees: ask git itself
        try:
            subprocess.check_output(
                ["git", "-C", str(repo_root), "rev-parse", "--is-inside-work-tree"],
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"{repo_root} is not a git checkout") from e

    out = subprocess.check_output(
        ["git", "-C", str(repo_root), "diff", "--name-status", ref],
        text=True, errors="ignore",
    )
    added_or_modified: list = []
    removed: list = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 2)
        status = parts[0].strip()
        if status.startswith("R") and len(parts) >= 3:
            # rename: old removed, new added
            removed.append(parts[1].replace("\\", "/"))
            added_or_modified.append(parts[2].replace("\\", "/"))
        elif status == "D" and len(parts) >= 2:
            removed.append(parts[1].replace("\\", "/"))
        elif len(parts) >= 2:
            added_or_modified.append(parts[1].replace("\\", "/"))
    return added_or_modified, removed


def compute_diff_scope(repo_root: Path, ref: str) -> dict:
    try:
        changed, removed = _git_changed_files(repo_root, ref)
    except (RuntimeError, subprocess.CalledProcessError) as e:
        return {"error": str(e)}

    deps = store.read_json(repo_root, "dependencies", {"files": {}}).get("files", {})
    state = store.read_json(repo_root, "state", {})
    tests = store.read_json(repo_root, "tests", {"tests": []}).get("tests", [])

    indexed_changed = [f for f in changed if f in deps]
    not_in_index = [f for f in changed if f not in deps]
    impact = collect_impacted(state, deps, indexed_changed)

    # which tests should run? union of: tests covering any changed/impacted file
    affected_files = set(indexed_changed) | set(impact["direct"]) | set(impact["transitive"])
    related_tests: list = []
    for t in tests:
        if t["file"] in affected_files:
            related_tests.append(t["file"])
            continue
        for cf in t.get("covers_files", []):
            if cf in affected_files:
                related_tests.append(t["file"])
                break

    # features touched
    feature_set: set = set()
    for f in affected_files:
        fid = deps.get(f, {}).get("feature")
        if fid:
            feature_set.add(fid)

    return {
        "ref": ref,
        "changed": indexed_changed,
        "removed": removed,
        "not_in_index": not_in_index,
        "direct_impact": impact["direct"],
        "transitive_impact": impact["transitive"],
        "features_touched": sorted(feature_set),
        "related_tests": sorted(set(related_tests)),
    }
