"""Walk a repo, dispatch each file to the matching adapter, and persist a compact index.

Design constraints:
  * No source code is written to disk — only paths, names, hashes, edges.
  * Adapters are tried in order; the first to claim a file wins.
  * Single pass over the file system; second pass resolves imports once all files are known.
"""
from __future__ import annotations

import fnmatch
import hashlib
import datetime as dt
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Optional

from ..adapters import LanguageAdapter, default_adapters
from ..adapters.base import ParsedFile
from . import store
from .call_resolver import resolve_calls
from .graph_builder import build_impact_graph
from .summarizer import build_repo_summary


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _hash_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _ignored(rel_posix: str, globs: Iterable[str]) -> bool:
    for g in globs:
        if fnmatch.fnmatch(rel_posix, g):
            return True
    return False


def _pick_adapter(path: Path, adapters: list) -> Optional[LanguageAdapter]:
    for ad in adapters:
        if ad.matches(path):
            return ad
    return None


def _infer_feature(rel_posix: str, feature_roots: list, overrides: dict) -> Optional[str]:
    # explicit override beats heuristic
    for prefix, fid in overrides.items():
        if rel_posix == prefix or rel_posix.startswith(prefix.rstrip("/") + "/"):
            return fid
    parts = rel_posix.split("/")
    if not parts:
        return None
    # require feature dir to actually be a directory (i.e. have descendants)
    def _is_dir_segment(seg: str) -> bool:
        return "." not in seg
    # case 1: <root>/<feature>/...
    if len(parts) >= 3 and parts[0] in feature_roots and _is_dir_segment(parts[1]):
        return parts[1]
    # case 2: <feature>/<root>/... (e.g. checkout/src/...)
    if len(parts) >= 3 and parts[1] in feature_roots and _is_dir_segment(parts[0]):
        return parts[0]
    # case 3: tests/<feature>/...  → still owned by <feature>
    if len(parts) >= 3 and parts[0] in ("tests", "test", "__tests__", "spec", "e2e") \
            and _is_dir_segment(parts[1]):
        return parts[1]
    # case 4: top-level dir is the feature (only when not a recognised root)
    if len(parts) >= 2 and _is_dir_segment(parts[0]) and parts[0] not in feature_roots:
        return parts[0]
    return None


def _walk_repo(repo_root: Path, ignore_globs: list, max_kb: int) -> Iterable[Path]:
    skip_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv",
                 "dist", "build", "target", "out", store.INDEX_DIR_NAME,
                 ".idea", ".vscode"}
    for p in repo_root.rglob("*"):
        if not p.is_file():
            continue
        # fast directory-prefix skip
        if any(part in skip_dirs for part in p.relative_to(repo_root).parts[:-1]):
            continue
        rel = p.relative_to(repo_root).as_posix()
        if _ignored(rel, ignore_globs):
            continue
        try:
            if p.stat().st_size > max_kb * 1024:
                continue
        except OSError:
            continue
        yield p


# ---------------------------------------------------------------------------

def build_index(repo_root: Path, *, only_files: Optional[list] = None,
                incremental: bool = False, verbose: bool = False) -> dict:
    """Index a repo (full build, or partial when `only_files` is given).

    When `incremental=True` and a previous index exists, files whose content
    hash matches the previous run are skipped — only changed files are
    re-parsed. Cross-file edges and aggregates are still recomputed because
    they depend on the global view.

    Returns a dict with summary counts. Persists all index JSON files.
    """
    repo_root = repo_root.resolve()
    store.ensure_index_dir(repo_root)
    config = store.read_json(repo_root, "config", store.default_config())
    ignore_globs = config.get("ignore_globs", [])
    feature_roots = config.get("feature_roots", [])
    feature_overrides = config.get("feature_overrides", {})
    user_aliases = config.get("aliases", {})
    max_kb = int(config.get("max_file_size_kb", 512))

    adapters = default_adapters()

    # Step 1: enumerate target files
    if only_files:
        files = []
        for raw in only_files:
            p = (repo_root / raw).resolve()
            if p.exists() and p.is_file():
                files.append(p)
    else:
        files = list(_walk_repo(repo_root, ignore_globs, max_kb))

    rel_files = [p.relative_to(repo_root) for p in files]

    # When doing partial update, fold into existing dependencies.json
    deps_existing = store.read_json(repo_root, "dependencies", None) or {
        "version": store.SCHEMA_VERSION, "generated_at": _now_iso(),
        "files": {}, "external": {},
    }
    sym_existing = store.read_json(repo_root, "symbols", None) or {
        "version": store.SCHEMA_VERSION, "generated_at": _now_iso(),
        "symbols": [],
    }
    tests_existing = store.read_json(repo_root, "tests", None) or {
        "version": store.SCHEMA_VERSION, "generated_at": _now_iso(),
        "tests": [],
    }

    files_index: dict = deps_existing.get("files", {}) if (only_files or incremental) else {}
    symbols_out: list = []
    tests_out: list = []
    skipped_unchanged: int = 0
    touchpoints_existing = store.read_json(repo_root, "touchpoints", None) or {
        "version": store.SCHEMA_VERSION, "generated_at": _now_iso(),
        "by_file": {}, "routes": [], "configs": [], "db_models": [], "events": [],
    }
    touchpoints_by_file: dict = {}
    if only_files or incremental:
        touchpoints_by_file = dict(touchpoints_existing.get("by_file", {}))
    if only_files:
        replaced = {p.relative_to(repo_root).as_posix() for p in files}
        files_index = {k: v for k, v in files_index.items() if k not in replaced}
        symbols_out = [s for s in sym_existing.get("symbols", []) if s.get("file") not in replaced]
        tests_out = [t for t in tests_existing.get("tests", []) if t.get("file") not in replaced]
        for k in replaced:
            touchpoints_by_file.pop(k, None)
    elif incremental:
        # Carry forward all symbols/tests; they'll be selectively replaced below.
        symbols_out = list(sym_existing.get("symbols", []))
        tests_out = list(tests_existing.get("tests", []))

    # Step 2: parse each file
    for path in files:
        rel = path.relative_to(repo_root).as_posix()
        adapter = _pick_adapter(path, adapters)
        if adapter is None:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        new_hash = _hash_text(content)

        if incremental and not only_files:
            prev = files_index.get(rel)
            if prev and prev.get("hash") == new_hash:
                skipped_unchanged += 1
                continue
            # changed: drop stale symbols/tests/touchpoints for this file
            symbols_out = [s for s in symbols_out if s.get("file") != rel]
            tests_out = [t for t in tests_out if t.get("file") != rel]
            touchpoints_by_file.pop(rel, None)

        parsed: ParsedFile = adapter.parse_file(path, content)
        feature_id = _infer_feature(rel, feature_roots, feature_overrides)

        files_index[rel] = {
            "language": parsed.language,
            "feature": feature_id,
            "package": parsed.package,
            "hash": new_hash,
            "imports_raw": parsed.imports_raw,
            "imports": [],          # filled in step 3
            "imported_by": [],      # filled in step 4
            "symbols": [s.name for s in parsed.symbols],
            "loc": parsed.loc,
        }

        if parsed.touchpoints:
            tp = parsed.touchpoints
            if tp.routes or tp.configs or tp.db_models or tp.events:
                touchpoints_by_file[rel] = {
                    "routes": tp.routes,
                    "configs": tp.configs,
                    "db_models": tp.db_models,
                    "events": tp.events,
                }

        for s in parsed.symbols:
            entry: dict = {
                "id": f"{rel}::{s.qualified_name or s.name}",
                "name": s.name,
                "qualified_name": s.qualified_name,
                "kind": s.kind,
                "file": rel,
                "line": s.line,
                "language": parsed.language,
                "feature": feature_id,
                "parent": s.parent,
                "calls": s.calls,
                "params": s.params,
            }
            if s.reads:
                entry["reads"] = s.reads
            if s.writes:
                entry["writes"] = s.writes
            if getattr(s, "bases", None):
                entry["bases"] = s.bases
            symbols_out.append(entry)

        if parsed.test:
            tests_out.append({
                "file": rel,
                "framework": parsed.test.framework,
                "test_cases": parsed.test.test_cases,
                "language": parsed.language,
                "feature": feature_id,
                "covers_files": [],     # filled in step 5
                "covers_features": [],  # filled in step 5
                "covers_hints": parsed.test.covers_hints,
            })

        if verbose:
            print(f"  parsed {rel} [{parsed.language}, {len(parsed.symbols)} symbols]")

    # Step 3: resolve imports to internal files
    known_paths = [Path(p) for p in files_index.keys()]
    for rel, entry in files_index.items():
        adapter = _pick_adapter(repo_root / rel, adapters)
        if adapter is None:
            continue
        resolved: list = []
        for raw in entry.get("imports_raw", []):
            r = adapter.resolve_import(raw, repo_root / rel, repo_root, known_paths)
            if r and r != rel and r not in resolved:
                resolved.append(r)
        entry["imports"] = resolved

    # Step 4: reverse edges
    rev = defaultdict(list)
    for src, entry in files_index.items():
        for tgt in entry["imports"]:
            rev[tgt].append(src)
    for tgt, srcs in rev.items():
        if tgt in files_index:
            files_index[tgt]["imported_by"] = sorted(set(srcs))

    # Step 4.5: cross-file call resolution (Phase 2)
    resolve_calls(files_index, symbols_out)

    # Step 5: tests — link covers_files via imports + naming heuristic
    src_files = [p for p in files_index if not _is_test_file(p, files_index[p])]
    src_basenames = {Path(p).stem.lower(): p for p in src_files}
    for t in tests_out:
        covered: set = set()
        # imports first
        for imp in files_index.get(t["file"], {}).get("imports", []):
            covered.add(imp)
        # naming heuristic: test_login.py -> login.py, LoginTest.java -> Login.java
        stem = Path(t["file"]).stem.lower()
        candidates = [
            stem.replace("test_", ""),
            stem.replace("_test", ""),
            stem.replace(".spec", ""),
            stem.replace(".test", ""),
            stem.removesuffix("test"),
            stem.removesuffix("it"),
        ]
        for c in candidates:
            c = c.strip("._")
            if not c:
                continue
            if c in src_basenames:
                covered.add(src_basenames[c])
        t["covers_files"] = sorted(covered)
        feats = {files_index[c].get("feature") for c in covered if c in files_index}
        feats.discard(None)
        # also include the test's own feature
        if t.get("feature"):
            feats.add(t["feature"])
        t["covers_features"] = sorted(feats)

    # Step 6: external deps
    external: dict = {}
    for ad in adapters:
        deps = ad.external_deps(repo_root)
        if deps:
            external.setdefault(ad.name, []).extend(deps)

    # Step 7: features
    features = _build_features(files_index, symbols_out, tests_out, user_aliases)

    # Step 8: aliases roster
    aliases = {fid: feat.get("aliases", []) for fid, feat in
               ((f["id"], f) for f in features)}
    for fid, extra in user_aliases.items():
        cur = set(aliases.get(fid, []))
        cur.update(extra)
        aliases[fid] = sorted(cur)

    # Step 9: packages
    packages = _build_packages(files_index, symbols_out)

    # Persist
    store.write_json(repo_root, "dependencies", {
        "version": store.SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "files": files_index,
        "external": external,
    })
    store.write_json(repo_root, "symbols", {
        "version": store.SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "symbols": symbols_out,
    })
    store.write_json(repo_root, "tests", {
        "version": store.SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "tests": tests_out,
    })
    store.write_json(repo_root, "features", {
        "version": store.SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "features": features,
    })
    store.write_json(repo_root, "aliases", aliases)
    store.write_json(repo_root, "packages", packages)

    # Touchpoints aggregate (flat lists across the repo + per-file detail).
    flat_routes:    list = []
    flat_configs:   list = []
    flat_db_models: list = []
    flat_events:    list = []
    for rel, tp in sorted(touchpoints_by_file.items()):
        for r in tp.get("routes") or []:
            flat_routes.append({**r, "file": rel,
                                "feature": files_index.get(rel, {}).get("feature")})
        for c in tp.get("configs") or []:
            flat_configs.append({**c, "file": rel,
                                 "feature": files_index.get(rel, {}).get("feature")})
        for m in tp.get("db_models") or []:
            flat_db_models.append({**m, "file": rel,
                                   "feature": files_index.get(rel, {}).get("feature")})
        for e in tp.get("events") or []:
            flat_events.append({**e, "file": rel,
                                "feature": files_index.get(rel, {}).get("feature")})
    store.write_json(repo_root, "touchpoints", {
        "version": store.SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "by_file": touchpoints_by_file,
        "routes": flat_routes,
        "configs": flat_configs,
        "db_models": flat_db_models,
        "events": flat_events,
    })

    # Pre-compute repo summary so `scope summary` is instant.
    summary = build_repo_summary(repo_root, files_index, symbols_out, tests_out, features)
    store.write_json(repo_root, "summary", summary)

    # Build impact-graph cache (still uses files_index but pre-resolves transitive sets).
    impact = build_impact_graph(files_index)
    state = {
        "version": store.SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "file_count": len(files_index),
        "symbol_count": len(symbols_out),
        "test_count": len(tests_out),
        "feature_count": len(features),
        "impact_cache": impact,
        "config_snapshot": config,
    }
    store.write_json(repo_root, "state", state)

    return {
        "files": len(files_index),
        "symbols": len(symbols_out),
        "tests": len(tests_out),
        "features": len(features),
        "touchpoints": (len(flat_routes) + len(flat_configs)
                        + len(flat_db_models) + len(flat_events)),
        "skipped_unchanged": skipped_unchanged,
    }


# ---------------------------------------------------------------------------

def _is_test_file(rel: str, entry: dict) -> bool:
    rel_l = rel.lower()
    if any(part in {"tests", "test", "__tests__", "spec", "e2e"} for part in rel.split("/")):
        return True
    name = Path(rel).name.lower()
    return (
        name.startswith("test_") or name.endswith("_test.py")
        or name.endswith("test.java") or name.endswith("it.java")
        or ".spec." in name or ".test." in name
    )


def _build_features(files_index: dict, symbols: list, tests: list,
                    user_aliases: dict) -> list:
    by_feature: dict = defaultdict(lambda: {
        "files": [], "languages": set(), "packages": set(),
        "symbol_count": 0, "tests": [], "entry_points": [],
    })
    for rel, entry in files_index.items():
        fid = entry.get("feature")
        if not fid:
            continue
        bucket = by_feature[fid]
        bucket["files"].append(rel)
        if entry.get("language"):
            bucket["languages"].add(entry["language"])
        if entry.get("package"):
            bucket["packages"].add(entry["package"])
    for s in symbols:
        fid = s.get("feature")
        if not fid:
            continue
        by_feature[fid]["symbol_count"] += 1
        # cheap "entry point" heuristic: top-level handler/controller-named symbols
        if s["kind"] in ("function", "method") and any(
            kw in s["name"].lower()
            for kw in ("handle", "main", "run", "start", "controller", "router", "endpoint", "api")
        ):
            qn = s.get("qualified_name") or s["name"]
            entry = f"{s['file']}::{qn}"
            if entry not in by_feature[fid]["entry_points"]:
                by_feature[fid]["entry_points"].append(entry)
    for t in tests:
        for fid in t.get("covers_features") or []:
            by_feature[fid]["tests"].append(t["file"])

    out: list = []
    for fid, bucket in sorted(by_feature.items()):
        # cross-feature dependencies inferred from per-file imports
        deps: set = set()
        for f in bucket["files"]:
            for imp in files_index.get(f, {}).get("imports", []):
                imp_feature = files_index.get(imp, {}).get("feature")
                if imp_feature and imp_feature != fid:
                    deps.add(imp_feature)
        # auto aliases — start from feature id tokens; user can extend via config
        auto_aliases = sorted({fid, fid.replace("-", " "), fid.replace("_", " ")})
        if fid in user_aliases:
            auto_aliases = sorted(set(auto_aliases) | set(user_aliases[fid]))
        out.append({
            "id": fid,
            "aliases": auto_aliases,
            "owned_packages": sorted(bucket["packages"]) or [fid],
            "key_files": sorted(bucket["files"])[:10],
            "entry_points": bucket["entry_points"][:10],
            "depends_on_features": sorted(deps),
            "related_tests": sorted(set(bucket["tests"])),
            "languages": sorted(bucket["languages"]),
            "file_count": len(bucket["files"]),
            "symbol_count": bucket["symbol_count"],
        })
    return out


def _build_packages(files_index: dict, symbols: list) -> dict:
    pkg_map: dict = defaultdict(lambda: {"language": None, "files": [], "symbols": 0})
    for rel, entry in files_index.items():
        pkg = entry.get("package") or _dir_as_package(rel)
        rec = pkg_map[pkg]
        rec["language"] = rec["language"] or entry.get("language")
        rec["files"].append(rel)
    for s in symbols:
        rel = s.get("file")
        if not rel:
            continue
        pkg = files_index.get(rel, {}).get("package") or _dir_as_package(rel)
        pkg_map[pkg]["symbols"] += 1
    return {
        "version": store.SCHEMA_VERSION,
        "packages": [
            {"name": k, **v} for k, v in sorted(pkg_map.items())
        ],
    }


def _dir_as_package(rel: str) -> str:
    parts = Path(rel).parent.parts
    if not parts:
        return "<root>"
    return "/".join(parts)
