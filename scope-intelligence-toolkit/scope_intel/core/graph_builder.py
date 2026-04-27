"""Cheap, in-memory transitive-impact computation.

Given the file-level import graph, precompute for each file the set of files
that *transitively depend on it* — i.e. blast radius of a change. We cap depth
to keep results compact and useful.
"""
from __future__ import annotations

from collections import defaultdict, deque

MAX_DEPTH = 4
MAX_PER_NODE = 100


def build_impact_graph(files_index: dict) -> dict:
    """Return {file -> [files transitively impacted, BFS up to MAX_DEPTH]}."""
    # forward: A -> files that import A (i.e. when A changes, these may break)
    forward: dict = {rel: list(entry.get("imported_by", []))
                     for rel, entry in files_index.items()}

    impact: dict = {}
    for src in files_index:
        visited: set = set()
        order: list = []
        queue: deque = deque([(src, 0)])
        while queue and len(order) < MAX_PER_NODE:
            cur, depth = queue.popleft()
            if depth > MAX_DEPTH:
                continue
            for nxt in forward.get(cur, []):
                if nxt in visited or nxt == src:
                    continue
                visited.add(nxt)
                order.append(nxt)
                queue.append((nxt, depth + 1))
        if order:
            impact[src] = order
    return impact


def impacted_for(state: dict, target: str) -> list:
    cache = (state or {}).get("impact_cache", {})
    return cache.get(target, [])


def collect_impacted(state: dict, files_index: dict, targets: list) -> dict:
    """Aggregate impact for one or more changed files. Returns a structured dict."""
    direct: set = set()
    transitive: set = set()
    feature_hits: dict = defaultdict(int)
    for t in targets:
        if t in files_index:
            for f in files_index[t].get("imported_by", []):
                direct.add(f)
        for f in impacted_for(state, t):
            transitive.add(f)
    transitive -= direct
    transitive.discard("")
    for f in direct | transitive:
        fid = files_index.get(f, {}).get("feature")
        if fid:
            feature_hits[fid] += 1
    return {
        "targets": list(targets),
        "direct": sorted(direct),
        "transitive": sorted(transitive),
        "features": sorted(feature_hits.keys()),
        "feature_hit_counts": dict(feature_hits),
    }
