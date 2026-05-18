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
    """Return (added, modified, removed) lists, both repo-relative POSIX paths.

    added:    files git reports as A (new) or the rename destination (R)
    modified: files git reports as M, C, or any other non-D/A/R status
    removed:  files git reports as D or the rename source (R)
    """
    if shutil.which("git") is None:
        raise RuntimeError("git executable not found on PATH")
    if not (repo_root / ".git").exists():
        # support submodules / worktrees: ask git itself
        try:
            subprocess.check_output(
                ["git", "-C", str(repo_root), "rev-parse", "--is-inside-work-tree"],
                stderr=subprocess.DEVNULL,
            )
        except (subprocess.CalledProcessError, OSError) as e:
            raise RuntimeError(f"{repo_root} is not a git checkout") from e

    try:
        out = subprocess.check_output(
            ["git", "-C", str(repo_root), "diff", "--name-status", ref],
            text=True, errors="ignore",
        )
    except OSError as e:
        raise RuntimeError(str(e)) from e
    added: list = []
    modified: list = []
    removed: list = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 2)
        status = parts[0].strip()
        if status.startswith("R") and len(parts) >= 3:
            # rename: old removed, new is effectively added
            removed.append(parts[1].replace("\\", "/"))
            added.append(parts[2].replace("\\", "/"))
        elif status == "D" and len(parts) >= 2:
            removed.append(parts[1].replace("\\", "/"))
        elif status == "A" and len(parts) >= 2:
            added.append(parts[1].replace("\\", "/"))
        elif len(parts) >= 2:
            modified.append(parts[1].replace("\\", "/"))
    return added, modified, removed


def compute_diff_scope(repo_root: Path, ref: str) -> dict:
    try:
        added, modified_files, removed = _git_changed_files(repo_root, ref)
    except (RuntimeError, OSError, subprocess.CalledProcessError) as e:
        return {"error": str(e)}

    deps = store.read_json(repo_root, "dependencies", {"files": {}}).get("files", {})
    state = store.read_json(repo_root, "state", {})
    tests = store.read_json(repo_root, "tests", {"tests": []}).get("tests", [])

    # All changed files (added + modified) for impact analysis
    changed = added + modified_files
    indexed_changed = [f for f in changed if f in deps]

    # Files git says changed but not in scope index — split by whether they're new or modified
    new_unindexed      = [f for f in added          if f not in deps]
    modified_unindexed = [f for f in modified_files if f not in deps]
    # Legacy key kept for backward compatibility
    not_in_index = new_unindexed + modified_unindexed
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
        "not_in_index": not_in_index,           # backward compat (added + modified_unindexed)
        "new_unindexed": new_unindexed,          # A-status files not in scope index
        "modified_unindexed": modified_unindexed, # M-status files not in scope index
        "direct_impact": impact["direct"],
        "transitive_impact": impact["transitive"],
        "features_touched": sorted(feature_set),
        "related_tests": sorted(set(related_tests)),
    }
