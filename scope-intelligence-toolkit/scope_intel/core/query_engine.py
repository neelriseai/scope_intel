"""Implements the query commands. Returns plain dicts so the CLI can print
either compact JSON or a short human view."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from . import store
from .graph_builder import collect_impacted


def _load(repo_root: Path) -> dict:
    return {
        "summary":      store.read_json(repo_root, "summary", {}),
        "features":     store.read_json(repo_root, "features", {"features": []}),
        "symbols":      store.read_json(repo_root, "symbols", {"symbols": []}),
        "dependencies": store.read_json(repo_root, "dependencies", {"files": {}, "external": {}}),
        "tests":        store.read_json(repo_root, "tests", {"tests": []}),
        "aliases":      store.read_json(repo_root, "aliases", {}),
        "packages":     store.read_json(repo_root, "packages", {"packages": []}),
        "touchpoints":  store.read_json(repo_root, "touchpoints",
                                        {"routes": [], "configs": [],
                                         "db_models": [], "events": []}),
        "state":        store.read_json(repo_root, "state", {}),
    }


# --- public queries --------------------------------------------------------

def get_repo_summary(repo_root: Path) -> dict:
    data = _load(repo_root)
    return data["summary"] or {"error": "Index not built. Run `scope index` first."}


def get_feature_scope(repo_root: Path, query: str) -> dict:
    data = _load(repo_root)
    feature = _resolve_feature(query, data["features"]["features"], data["aliases"])
    if not feature:
        return {"error": f"No feature matched '{query}'.",
                "available": [f["id"] for f in data["features"]["features"]]}
    fid = feature["id"]
    deps = data["dependencies"]["files"]
    syms = [s for s in data["symbols"]["symbols"] if s.get("feature") == fid]
    tests = [t for t in data["tests"]["tests"] if fid in (t.get("covers_features") or [])]
    files = [rel for rel, e in deps.items() if e.get("feature") == fid]
    # top entry symbols (cap at 10)
    entry_syms = [s for s in syms if s["kind"] in ("function", "method") and any(
        kw in s["name"].lower()
        for kw in ("handle", "main", "run", "start", "controller", "router", "endpoint", "api")
    )][:10]
    return {
        "feature": feature,
        "files": sorted(files),
        "entry_symbols": [
            {"id": s["id"], "kind": s["kind"], "file": s["file"], "line": s["line"]}
            for s in entry_syms
        ],
        "symbol_sample": [
            {"name": s["name"], "kind": s["kind"], "file": s["file"], "line": s["line"]}
            for s in syms[:25]
        ],
        "tests": [
            {"file": t["file"], "framework": t.get("framework"),
             "cases": t.get("test_cases", [])[:5]}
            for t in tests
        ],
    }


def find_impacted_files(repo_root: Path, *, file: Optional[str] = None,
                        feature: Optional[str] = None,
                        symbol: Optional[str] = None) -> dict:
    data = _load(repo_root)
    deps = data["dependencies"]["files"]
    state = data["state"]
    targets: list = []

    if file:
        if file not in deps:
            return {"error": f"File '{file}' not in index. Did you spell the relative path correctly?"}
        targets.append(file)
    if feature:
        feat = _resolve_feature(feature, data["features"]["features"], data["aliases"])
        if not feat:
            return {"error": f"No feature matched '{feature}'."}
        targets.extend([rel for rel, e in deps.items() if e.get("feature") == feat["id"]])
    if symbol:
        for s in data["symbols"]["symbols"]:
            qn = s.get("qualified_name") or s["name"]
            if symbol == s["name"] or symbol == qn or symbol == s["id"]:
                if s["file"] not in targets:
                    targets.append(s["file"])
    if not targets:
        return {"error": "Provide --file, --feature, or --symbol."}
    return collect_impacted(state, deps, sorted(set(targets)))


def get_related_tests(repo_root: Path, *, file: Optional[str] = None,
                      feature: Optional[str] = None) -> dict:
    data = _load(repo_root)
    tests = data["tests"]["tests"]
    matches: list = []
    if file:
        for t in tests:
            if file in (t.get("covers_files") or []) or t["file"] == file:
                matches.append(t)
    if feature:
        feat = _resolve_feature(feature, data["features"]["features"], data["aliases"])
        if feat:
            fid = feat["id"]
            for t in tests:
                if fid in (t.get("covers_features") or []) and t not in matches:
                    matches.append(t)
    if not matches:
        return {"matches": [], "note": "No related tests found via covers_files/covers_features."}
    return {
        "matches": [
            {
                "file": t["file"],
                "framework": t.get("framework"),
                "cases": t.get("test_cases", []),
                "covers_files": t.get("covers_files", []),
                "covers_features": t.get("covers_features", []),
            } for t in matches
        ]
    }


def get_symbol_context(repo_root: Path, query: str) -> dict:
    data = _load(repo_root)
    matches = _find_symbols(query, data["symbols"]["symbols"])[:5]
    if not matches:
        return {"error": f"No symbol matched '{query}'."}
    by_id = {s["id"]: s for s in data["symbols"]["symbols"]}
    out: list = []
    for s in matches:
        # Phase 2: prefer resolved cross-file edges; fall back to bare calls.
        resolved = s.get("resolved_calls") or []
        callees: list = []
        for cid in resolved[:20]:
            tgt = by_id.get(cid)
            if tgt:
                callees.append({"id": cid, "name": tgt["name"], "file": tgt["file"]})
        callers: list = []
        for cid in (s.get("called_by") or [])[:20]:
            src = by_id.get(cid)
            if src:
                callers.append({"id": cid, "kind": src["kind"], "file": src["file"]})
        # if the resolver came up empty, fall back to bare-name match (Phase 1 behavior)
        if not callers:
            for s2 in data["symbols"]["symbols"]:
                if s["name"] in (s2.get("calls") or []) and s2["id"] != s["id"]:
                    callers.append({"id": s2["id"], "kind": s2["kind"], "file": s2["file"]})
                    if len(callers) >= 20:
                        break
        out.append({
            "symbol": s,
            "callers": callers,
            "callees": callees or [{"name": c} for c in (s.get("calls") or [])][:20],
        })
    return {"matches": out}


def get_callers(repo_root: Path, query: str) -> dict:
    data = _load(repo_root)
    matches = _find_symbols(query, data["symbols"]["symbols"])[:5]
    if not matches:
        return {"error": f"No symbol matched '{query}'."}
    by_id = {s["id"]: s for s in data["symbols"]["symbols"]}
    out: list = []
    for s in matches:
        callers = []
        for cid in (s.get("called_by") or []):
            src = by_id.get(cid)
            if src:
                callers.append({"id": cid, "kind": src["kind"], "file": src["file"],
                                "feature": src.get("feature")})
        out.append({"symbol": s["id"], "callers": callers})
    return {"matches": out}


def get_callees(repo_root: Path, query: str) -> dict:
    data = _load(repo_root)
    matches = _find_symbols(query, data["symbols"]["symbols"])[:5]
    if not matches:
        return {"error": f"No symbol matched '{query}'."}
    by_id = {s["id"]: s for s in data["symbols"]["symbols"]}
    out: list = []
    for s in matches:
        callees: list = []
        seen: set = set()
        for cid in (s.get("resolved_calls") or []):
            tgt = by_id.get(cid)
            if tgt and cid not in seen:
                seen.add(cid)
                callees.append({"id": cid, "kind": tgt["kind"], "file": tgt["file"],
                                "feature": tgt.get("feature")})
        out.append({
            "symbol": s["id"], "callees": callees,
            "unresolved": [c for c in (s.get("calls") or [])
                           if not any(c == by_id[cid]["name"] for cid in (s.get("resolved_calls") or []))][:10],
        })
    return {"matches": out}


def get_touchpoints(repo_root: Path, *, kind: Optional[str] = None,
                    feature: Optional[str] = None,
                    file: Optional[str] = None) -> dict:
    data = _load(repo_root)
    tp = data["touchpoints"]
    sections = ("routes", "configs", "db_models", "events")
    if kind and kind not in sections:
        return {"error": f"Unknown kind '{kind}'. Use one of {', '.join(sections)}."}
    out: dict = {}
    for s in sections:
        if kind and kind != s:
            continue
        items = list(tp.get(s) or [])
        if feature:
            feat = _resolve_feature(feature, data["features"]["features"], data["aliases"])
            if feat:
                fid = feat["id"]
                items = [i for i in items if i.get("feature") == fid]
        if file:
            items = [i for i in items if i.get("file") == file]
        out[s] = items
    out["totals"] = {k: len(v) for k, v in out.items() if k in sections}
    return out


def _find_symbols(query: str, symbols: list) -> list:
    matches: list = []
    q = query.lower()
    for s in symbols:
        qn = s.get("qualified_name") or s["name"]
        if (query == s["name"] or query == qn or query == s["id"]
                or q in s["name"].lower()):
            matches.append(s)
    return matches


# --- helpers ---------------------------------------------------------------

def _resolve_feature(query: str, features: list, aliases: dict) -> Optional[dict]:
    q = query.strip().lower()
    by_id = {f["id"].lower(): f for f in features}
    if q in by_id:
        return by_id[q]
    # alias roster
    for fid, alist in (aliases or {}).items():
        if any(q == a.lower() for a in (alist or [])):
            return by_id.get(fid.lower())
    # alias inside feature record
    for f in features:
        for a in (f.get("aliases") or []):
            if q == a.lower():
                return f
    # substring fallback
    for fid, f in by_id.items():
        if q in fid:
            return f
    return None
