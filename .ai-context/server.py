"""AI Context MCP Server — v1.2.0

Serves two layers:
  1. Context docs  (.ai-context/generated/ + curated/)
  2. Code scope    (delegates to scope-intelligence-toolkit CLI)

Run:  uvicorn server:app --reload --port 8000
Deps: pip install fastapi uvicorn
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR   = Path(__file__).parent
GEN_DIR    = BASE_DIR / "generated"
CUR_DIR    = BASE_DIR / "curated"
SCOPE_CLI  = [sys.executable, "-m", "scope_intel"]

with open(GEN_DIR / "index.json", encoding="utf-8") as f:
    MANIFEST = json.load(f)

app = FastAPI(
    title="AI Context + Scope Intelligence MCP Server",
    version="1.2.0",
    description="Deterministic retrieval of project context docs and live code scope.",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        raise HTTPException(status_code=404, detail=f"File not found: {path.name}")


def _extract_section(content: str, query: str) -> list:
    """Return markdown sections whose heading or body contains the query (case-insensitive)."""
    q = query.lower()
    sections: list = []
    current_heading: str = ""
    current_lines: list = []

    def _flush():
        if current_heading or current_lines:
            body = "\n".join(current_lines).strip()
            if q in current_heading.lower() or q in body.lower():
                sections.append({"heading": current_heading, "content": body})

    for line in content.splitlines():
        if re.match(r"^#{1,4} ", line):
            _flush()
            current_heading = line.lstrip("#").strip()
            current_lines = []
        else:
            current_lines.append(line)
    _flush()
    return sections


def _skill_section(content: str, skill_id: str) -> Optional[str]:
    """Extract just the section matching a skill id from a skills playbook."""
    q = skill_id.lower().lstrip("/")
    in_section = False
    lines: list = []
    for line in content.splitlines():
        if re.match(r"^#{1,4} ", line):
            heading = line.lstrip("#").strip().lower()
            if q in heading:
                in_section = True
                lines = [line]
                continue
            elif in_section:
                break
        if in_section:
            lines.append(line)
    return "\n".join(lines).strip() if lines else None


def _scope_run(repo: str, *args) -> dict:
    """Call the scope CLI and return parsed JSON output."""
    repo_path = Path(repo).resolve()
    cmd = SCOPE_CLI + list(args) + ["--repo", str(repo_path), "--json"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30,
                                cwd=str(BASE_DIR.parent))
        if result.returncode != 0 and not result.stdout.strip():
            return {"error": result.stderr.strip() or "scope CLI returned non-zero"}
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# 1. Context-doc endpoints (Layer 1)
# ---------------------------------------------------------------------------

@app.get("/list_context_files", summary="List all available context files")
def list_context_files():
    return MANIFEST["structure"]


@app.get("/get_context_file/{file_id}", summary="Full content of a context file by ID prefix")
def get_context_file(file_id: str):
    mapping = {f["file"].split("-")[0]: f["file"]
               for f in MANIFEST["structure"]["generated"]}
    filename = mapping.get(file_id)
    if not filename:
        raise HTTPException(status_code=404, detail=f"No file with id '{file_id}'")
    return {"file_id": file_id, "content": _read(GEN_DIR / filename)}


@app.get("/get_context_slice", summary="Section-aware search across all context files")
def get_context_slice(query: str = Query(..., description="Search term")):
    results: list = []
    for fmeta in MANIFEST["structure"]["generated"]:
        path = GEN_DIR / fmeta["file"]
        if not path.exists():
            continue
        content = _read(path)
        sections = _extract_section(content, query)
        if sections:
            results.append({
                "file": fmeta["file"],
                "purpose": fmeta.get("purpose"),
                "sections": sections,
            })
    return {"query": query, "matches": results, "total_sections": sum(
        len(r["sections"]) for r in results)}


@app.get("/get_phase_status", summary="Current phase + deliverables")
def get_phase_status():
    return {"phase_status": _read(CUR_DIR / "current phase.md")}


@app.get("/get_constraints", summary="Token-efficiency constraints")
def get_constraints():
    return {"constraints": _read(CUR_DIR / "constraints.md")}


@app.get("/get_module_map", summary="Toolkit + repo-local module map")
def get_module_map():
    return {"module_map": _read(CUR_DIR / "module-map.md")}


@app.get("/get_skill_playbook/{skill_id}", summary="Playbook for a specific skill")
def get_skill_playbook(skill_id: str):
    content = _read(GEN_DIR / "007-skill-playbooks.md")
    section = _skill_section(content, skill_id)
    if section:
        return {"skill_id": skill_id, "content": section}
    return {"skill_id": skill_id, "content": content,
            "note": f"Skill '{skill_id}' section not found — returning full playbook"}


@app.get("/get_subagent_strategy", summary="Subagent roles and strategy")
def get_subagent_strategy():
    return {"content": _read(GEN_DIR / "008-subagent-strategy.md")}


@app.get("/get_schema_design", summary="Feature-map + symbol schema examples")
def get_schema_design():
    return {"content": _read(GEN_DIR / "009-schema-design.md")}


@app.get("/get_claude_integration", summary="Claude Code wiring guide")
def get_claude_integration():
    return {"content": _read(GEN_DIR / "claude-code-integration.md")}


@app.get("/get_roadmap", summary="Phased implementation roadmap")
def get_roadmap():
    return {"content": _read(GEN_DIR / "roadmap.md")}


# ---------------------------------------------------------------------------
# 2. Scope proxy endpoints (Layer 2 — delegates to scope_intel CLI)
# ---------------------------------------------------------------------------

@app.get("/scope/summary", summary="Repo-wide scope summary (delegated to scope CLI)")
def scope_summary(repo: str = Query(..., description="Absolute or relative repo path")):
    return _scope_run(repo, "summary")


@app.get("/scope/feature", summary="Feature scope (files, symbols, tests)")
def scope_feature(
    repo: str = Query(...),
    name: str = Query(..., description="Feature id or alias"),
):
    return _scope_run(repo, "feature", name)


@app.get("/scope/features", summary="List all features in a repo")
def scope_features(repo: str = Query(...)):
    return _scope_run(repo, "features")


@app.get("/scope/impacted", summary="Files impacted by a change")
def scope_impacted(
    repo: str = Query(...),
    file: Optional[str] = Query(None),
    feature: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
):
    extra = []
    if file:    extra += ["--file", file]
    if feature: extra += ["--feature", feature]
    if symbol:  extra += ["--symbol", symbol]
    if not extra:
        raise HTTPException(status_code=400, detail="Provide at least one of: file, feature, symbol")
    return _scope_run(repo, "impacted", *extra)


@app.get("/scope/tests", summary="Tests covering a file or feature")
def scope_tests(
    repo: str = Query(...),
    file: Optional[str] = Query(None),
    feature: Optional[str] = Query(None),
):
    extra = []
    if file:    extra += ["--file", file]
    if feature: extra += ["--feature", feature]
    if not extra:
        raise HTTPException(status_code=400, detail="Provide file or feature")
    return _scope_run(repo, "tests", *extra)


@app.get("/scope/symbol", summary="Symbol context: callers + callees + reads/writes")
def scope_symbol(repo: str = Query(...), name: str = Query(...)):
    return _scope_run(repo, "symbol", name)


@app.get("/scope/callers", summary="All callers of a symbol (cross-file)")
def scope_callers(repo: str = Query(...), name: str = Query(...)):
    return _scope_run(repo, "callers", name)


@app.get("/scope/callees", summary="All callees of a symbol (cross-file)")
def scope_callees(repo: str = Query(...), name: str = Query(...)):
    return _scope_run(repo, "callees", name)


@app.get("/scope/touchpoints", summary="Routes, env configs, DB models in a repo")
def scope_touchpoints(
    repo: str = Query(...),
    type: Optional[str] = Query(None, description="routes | configs | db_models | events"),
    feature: Optional[str] = Query(None),
):
    extra = []
    if type:    extra += ["--type", type]
    if feature: extra += ["--feature", feature]
    return _scope_run(repo, "touchpoints", *extra)


@app.get("/scope/diff", summary="Scope impact of a git change")
def scope_diff(
    repo: str = Query(...),
    ref: str = Query("HEAD~1", description="Git ref to diff against"),
):
    return _scope_run(repo, "diff", ref)


@app.get("/scope/report", summary="Token savings summary across all past scope queries")
def scope_report(repo: str = Query(..., description="Absolute or relative repo path")):
    """Returns aggregated token-savings estimates from query_log.jsonl.

    Fields: total_queries, total_tokens_saved_est, savings_percent,
            by_command breakdown, recent_queries list.
    """
    # Import directly — no CLI subprocess needed since this is Python-land
    repo_path = Path(repo).resolve()
    try:
        sys.path.insert(0, str(BASE_DIR.parent / "scope-intelligence-toolkit"))
        from scope_intel.core.tracker import compute_savings_summary  # type: ignore
        return compute_savings_summary(repo_path)
    except Exception as e:
        return {"error": str(e)}
