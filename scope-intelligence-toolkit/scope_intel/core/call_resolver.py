"""Resolve bare call names on each symbol to qualified symbol IDs across files.

Inputs:
  files_index: { rel -> {imports, symbols, ...} }
  symbols:     [ {id, name, qualified_name, file, calls, ...} ]

Outputs (mutates in place):
  - each symbol gets `resolved_calls`: sorted list of symbol IDs it calls
  - each symbol gets `called_by`: sorted list of symbol IDs that call it

Resolution strategy (best-effort, single-pass):
  1. Same-file lookup — bare names matching another symbol in the file
  2. Imported-file lookup — bare/dotted names matching a symbol exported by
     a file the source file imports
  3. Dotted forms ("ClassName.method", "module.func") — try the leaf segment
"""
from __future__ import annotations

from collections import defaultdict


def resolve_calls(files_index: dict, symbols: list) -> None:
    # Build lookup tables
    by_id = {s["id"]: s for s in symbols}
    by_file: dict = defaultdict(list)
    by_name: dict = defaultdict(list)  # name -> list[symbol_id]
    for s in symbols:
        by_file[s["file"]].append(s)
        by_name[s["name"]].append(s["id"])
        qn = s.get("qualified_name")
        if qn and qn != s["name"]:
            by_name[qn].append(s["id"])

    for s in symbols:
        f = s["file"]
        imports = files_index.get(f, {}).get("imports", []) or []
        candidates_pool: set = set()
        # imports first — these are most likely to be the real targets
        for imp in imports:
            for sym in by_file.get(imp, []):
                candidates_pool.add(sym["id"])
        # plus the same file
        for sym in by_file.get(f, []):
            if sym["id"] != s["id"]:
                candidates_pool.add(sym["id"])

        resolved: set = set()
        for raw in s.get("calls") or []:
            leaf = raw.rsplit(".", 1)[-1]
            for cand in by_name.get(raw, []) + by_name.get(leaf, []):
                if cand == s["id"] or cand not in candidates_pool:
                    continue
                resolved.add(cand)
        s["resolved_calls"] = sorted(resolved)

    # Build reverse edges
    inverse: dict = defaultdict(set)
    for s in symbols:
        for tgt in s.get("resolved_calls", []):
            inverse[tgt].add(s["id"])
    for sid, callers in inverse.items():
        if sid in by_id:
            by_id[sid]["called_by"] = sorted(callers)
    for s in symbols:
        s.setdefault("called_by", [])
