"""Graph renderer — produce Mermaid or DOT diagrams from the scope index.

Three diagram types:
  classDiagram   — classes + methods + inheritance for a feature, file, or symbol
  graph TD       — file-level import/dependency graph for a feature or file
  callGraph      — call chain (callers → symbol → callees) centred on a symbol

All renderers operate on the pre-built index; no external deps required.

Usage (from Python):
    from scope_intel.core.graph_renderer import render_graph
    code = render_graph(repo_root, target="feature", query="auth", kind="class")
    print(code)   # paste into GitHub, Notion, or any Mermaid renderer

Outputs:
  format="mermaid"  (default) — fenced ```mermaid block
  format="dot"      — Graphviz DOT source
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from . import store


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def render_graph(
    repo_root: Path,
    *,
    target: str = "feature",
    query: str,
    kind: str = "class",
    format: str = "mermaid",
    max_nodes: int = 60,
) -> dict:
    """Generate a graph diagram from the scope index.

    Args:
        repo_root:  Path to the repo root (must be scope-indexed).
        target:     "feature" | "file" | "symbol"
        query:      Feature id/alias, file path, or symbol name.
        kind:       "class"  → classDiagram (classes + methods + inheritance)
                    "deps"   → graph TD    (file-level import graph)
                    "calls"  → callGraph   (callers → symbol → callees)
        format:     "mermaid" | "dot"
        max_nodes:  Cap on nodes to keep diagrams readable (default 60).

    Returns:
        {
          "diagram": str,      # raw diagram source
          "fenced":  str,      # ```mermaid fenced block (mermaid only)
          "format":  str,
          "kind":    str,
          "nodes":   int,
          "edges":   int,
          "truncated": bool,
        }
    """
    repo_root = Path(repo_root)

    if not store.is_initialized(repo_root):
        return {"error": "repo not indexed — run `scope index` first"}

    symbols  = store.read_json(repo_root, "symbols",      {"symbols":  []})["symbols"]
    deps     = store.read_json(repo_root, "dependencies", {"files":    {}})["files"]
    features = store.read_json(repo_root, "features",     {"features": []})["features"]
    aliases  = store.read_json(repo_root, "aliases",      {})

    if kind == "class":
        raw, meta = _class_diagram(
            symbols, deps, features, aliases,
            target=target, query=query, max_nodes=max_nodes,
        )
    elif kind == "deps":
        raw, meta = _deps_graph(
            deps, features, aliases,
            target=target, query=query, max_nodes=max_nodes,
        )
    elif kind == "calls":
        raw, meta = _call_graph(
            symbols,
            query=query, max_nodes=max_nodes,
        )
    else:
        return {"error": f"unknown kind '{kind}' — use class | deps | calls"}

    if "error" in meta:
        return meta

    if format == "dot":
        dot_src = _to_dot(raw, kind, query)
        return {
            "diagram": dot_src,
            "fenced":  f"```dot\n{dot_src}\n```",
            "format":  "dot",
            "kind":    kind,
            **meta,
        }

    mermaid = _to_mermaid(raw, kind)
    return {
        "diagram": mermaid,
        "fenced":  f"```mermaid\n{mermaid}\n```",
        "format":  "mermaid",
        "kind":    kind,
        **meta,
    }


# ---------------------------------------------------------------------------
# Internal intermediate representation
# ---------------------------------------------------------------------------
# raw = {"nodes": [{id, label, meta}], "edges": [{from, to, label}]}

def _safe_id(s: str) -> str:
    """Make a string safe for Mermaid node IDs (no spaces, colons, dots)."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", s)


def _resolve_feature(query: str, features: list, aliases: dict) -> Optional[dict]:
    import difflib as _dl
    q = query.lower()
    # exact id match
    for f in features:
        if f["id"] == q:
            return f
    # alias match
    fid = aliases.get(q)
    if fid:
        for f in features:
            if f["id"] == fid:
                return f
    # substring
    for f in features:
        if q in f["id"]:
            return f
    return None


# ---------------------------------------------------------------------------
# 1. Class diagram
# ---------------------------------------------------------------------------

def _class_diagram(symbols, deps, features, aliases, *, target, query, max_nodes):
    """Build a classDiagram intermediate representation."""

    # --- Select relevant symbols ---
    if target == "feature":
        feat = _resolve_feature(query, features, aliases)
        if not feat:
            return {}, {"error": f"No feature matched '{query}'"}
        fid = feat["id"]
        relevant_files = {p for p, e in deps.items() if e.get("feature") == fid}
        syms = [s for s in symbols if s.get("feature") == fid or s["file"] in relevant_files]
    elif target == "file":
        syms = [s for s in symbols if s["file"] == query or s["file"].endswith(query)]
        if not syms:
            return {}, {"error": f"No symbols found in file '{query}'"}
    elif target == "symbol":
        q = query.lower()
        matched = [s for s in symbols if s["name"].lower() == q or
                   s.get("qualified_name", "").lower() == q]
        if not matched:
            return {}, {"error": f"No symbol matched '{query}'"}
        # Include the class the matched symbol belongs to + its siblings
        parent_names = {s.get("parent") for s in matched if s.get("parent")}
        syms = [s for s in symbols if
                s["name"] in parent_names or
                s.get("qualified_name") in parent_names or
                s.get("parent") in parent_names or
                s in matched]
    else:
        return {}, {"error": f"unknown target '{target}'"}

    # Build: class → methods, class → bases
    classes: dict[str, dict] = {}  # class_id → {name, file, methods[], bases[]}
    for s in syms:
        if s["kind"] == "class":
            cid = s.get("qualified_name") or s["name"]
            if cid not in classes:
                classes[cid] = {
                    "name":    s["name"],
                    "file":    s["file"],
                    "methods": [],
                    "bases":   s.get("bases", []),
                }
    for s in syms:
        if s["kind"] == "method" and s.get("parent"):
            cid = s["parent"]
            if cid not in classes:
                # create a stub for the parent if not already present
                classes[cid] = {"name": cid.split(".")[-1], "file": s["file"],
                                 "methods": [], "bases": []}
            params = [p for p in s.get("params", []) if p != "self"]
            classes[cid]["methods"].append({
                "name":   s["name"],
                "params": params,
                "line":   s["line"],
            })

    # Truncate
    truncated = len(classes) > max_nodes
    class_list = list(classes.items())[:max_nodes]

    nodes = [{"id": _safe_id(cid), "label": meta["name"],
              "meta": {"file": meta["file"], "bases": meta["bases"],
                       "methods": meta["methods"]}}
             for cid, meta in class_list]

    # Inheritance edges
    class_names = {meta["name"]: _safe_id(cid) for cid, meta in class_list}
    edges = []
    for cid, meta in class_list:
        for base in meta["bases"]:
            if base in class_names:
                edges.append({"from": _safe_id(cid), "to": class_names[base],
                              "label": "inherits"})

    return (
        {"nodes": nodes, "edges": edges},
        {"nodes": len(nodes), "edges": len(edges), "truncated": truncated},
    )


# ---------------------------------------------------------------------------
# 2. Dependency graph (file → file)
# ---------------------------------------------------------------------------

def _deps_graph(deps, features, aliases, *, target, query, max_nodes):
    """File-level import graph for a feature or file."""

    if target == "feature":
        feat = _resolve_feature(query, list({
            e.get("feature"): {"id": e.get("feature")} for e in deps.values()
            if e.get("feature")
        }.values()), aliases)
        if not feat:
            # Fall back: just find by id substring in feature values
            fid = query
        else:
            fid = feat["id"]
        files = {p for p, e in deps.items() if e.get("feature") == fid}
    elif target == "file":
        files = {p for p in deps if p == query or p.endswith(query)}
        # Also include immediate imports
        for p, e in list(deps.items()):
            for imp in e.get("imports", []):
                if imp in {query} | files:
                    files.add(p)
    else:
        return {}, {"error": "deps graph supports target=feature or target=file only"}

    if not files:
        return {}, {"error": f"No files found for '{query}'"}

    truncated = len(files) > max_nodes
    files = set(list(files)[:max_nodes])

    nodes = [{"id": _safe_id(f), "label": Path(f).name,
              "meta": {"path": f}} for f in sorted(files)]

    edges = []
    for f in sorted(files):
        for imp in deps.get(f, {}).get("imports", []):
            if imp in files:
                edges.append({"from": _safe_id(f), "to": _safe_id(imp), "label": "imports"})

    return (
        {"nodes": nodes, "edges": edges},
        {"nodes": len(nodes), "edges": len(edges), "truncated": truncated},
    )


# ---------------------------------------------------------------------------
# 3. Call graph (callers → symbol → callees)
# ---------------------------------------------------------------------------

def _call_graph(symbols, *, query, max_nodes):
    """Call graph centred on a symbol: callers on the left, callees on the right."""
    q = query.lower()
    by_id = {s["id"]: s for s in symbols}
    matched = [s for s in symbols if s["name"].lower() == q or
               s.get("qualified_name", "").lower() == q]
    if not matched:
        return {}, {"error": f"No symbol matched '{query}'"}

    root = matched[0]
    root_id = _safe_id(root["id"])

    nodes = [{"id": root_id, "label": root.get("qualified_name") or root["name"],
              "meta": {"file": root["file"], "role": "root"}}]
    edges = []
    seen: set = {root_id}

    def _add(sym_id: str, role: str) -> str:
        nid = _safe_id(sym_id)
        if nid not in seen and len(nodes) < max_nodes:
            seen.add(nid)
            s = by_id.get(sym_id, {})
            nodes.append({"id": nid,
                          "label": s.get("qualified_name") or s.get("name") or sym_id,
                          "meta": {"file": s.get("file", ""), "role": role}})
        return nid

    for cid in (root.get("called_by") or [])[:max_nodes // 2]:
        nid = _add(cid, "caller")
        edges.append({"from": nid, "to": root_id, "label": "calls"})

    for cid in (root.get("resolved_calls") or [])[:max_nodes // 2]:
        nid = _add(cid, "callee")
        edges.append({"from": root_id, "to": nid, "label": "calls"})

    truncated = (
        len(root.get("called_by") or []) > max_nodes // 2 or
        len(root.get("resolved_calls") or []) > max_nodes // 2
    )
    return (
        {"nodes": nodes, "edges": edges},
        {"nodes": len(nodes), "edges": len(edges), "truncated": truncated},
    )


# ---------------------------------------------------------------------------
# Mermaid renderer
# ---------------------------------------------------------------------------

def _to_mermaid(raw: dict, kind: str) -> str:
    nodes = raw.get("nodes", [])
    edges = raw.get("edges", [])

    if kind == "class":
        lines = ["classDiagram"]
        for n in nodes:
            meta    = n["meta"]
            methods = meta.get("methods", [])
            lines.append(f"    class {n['id']} [{n['label']}] {{")
            for m in methods:
                params = ", ".join(m["params"])
                lines.append(f"        +{m['name']}({params})")
            lines.append("    }")
        for e in edges:
            # inheritance
            lines.append(f"    {e['to']} <|-- {e['from']}")
        # Add file notes as comments
        file_map: dict = {}
        for n in nodes:
            f = n["meta"].get("file", "")
            if f:
                file_map.setdefault(f, []).append(n["label"])
        for f, names in file_map.items():
            lines.append(f"    %% {f}: {', '.join(names)}")
        return "\n".join(lines)

    elif kind == "deps":
        lines = ["graph TD"]
        for n in nodes:
            safe = n["id"]
            label = n["label"]
            lines.append(f"    {safe}[{label}]")
        for e in edges:
            lines.append(f"    {e['from']} --> {e['to']}")
        return "\n".join(lines)

    elif kind == "calls":
        lines = ["graph LR"]
        for n in nodes:
            shape_open  = "((" if n["meta"].get("role") == "root" else "("
            shape_close = "))" if n["meta"].get("role") == "root" else ")"
            label = n["label"].split("::")[-1]  # short name
            lines.append(f"    {n['id']}{shape_open}{label}{shape_close}")
        for e in edges:
            lines.append(f"    {e['from']} --> {e['to']}")
        return "\n".join(lines)

    return ""


# ---------------------------------------------------------------------------
# DOT renderer
# ---------------------------------------------------------------------------

def _to_dot(raw: dict, kind: str, title: str) -> str:
    nodes = raw.get("nodes", [])
    edges = raw.get("edges", [])
    safe_title = re.sub(r"[^a-zA-Z0-9_]", "_", title)

    lines = [f'digraph {safe_title} {{', '    rankdir=LR;',
             '    node [fontname="Helvetica" fontsize=10];']

    if kind == "class":
        for n in nodes:
            methods = n["meta"].get("methods", [])
            label_parts = [n["label"]]
            for m in methods:
                params = ", ".join(m["params"])
                label_parts.append(f"+ {m['name']}({params})")
            label = "\\n".join(label_parts)
            lines.append(f'    {n["id"]} [shape=box label="{label}"];')
        for e in edges:
            lines.append(f'    {e["from"]} -> {e["to"]} [arrowhead=empty label="extends"];')

    else:
        for n in nodes:
            lines.append(f'    {n["id"]} [label="{n["label"]}"];')
        for e in edges:
            lines.append(f'    {e["from"]} -> {e["to"]};')

    lines.append("}")
    return "\n".join(lines)
