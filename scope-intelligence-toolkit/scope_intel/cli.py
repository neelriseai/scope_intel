"""Command-line entry point for the scope intelligence toolkit.

All commands accept --repo <path> (default: cwd).
Read-only queries accept --json for machine-readable output.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from . import __version__
from .core import store
from .core.diff import compute_diff_scope
from .core.indexer import build_index
from .core.query_engine import (
    find_impacted_files,
    get_callees,
    get_callers,
    get_feature_scope,
    get_related_tests,
    get_repo_summary,
    get_symbol_context,
    get_touchpoints,
)
from .core.mempalace import (
    add_memory,
    auto_capture_from_git,
    compute_churn,
    decay_confidence,
    detect_conflicts,
    export_memories,
    fetch_relevant,
    import_memories,
    list_memories,
    memory_stats,
    resolve_memory,
    search_memories,
)
from .core.doc_ingestor import ingest_document
from .core.reporter import format_global_html, format_global_terminal, format_html, format_terminal
from .core.summarizer import feature_one_liner
from .core.tracker import compute_global_summary, compute_savings_summary, log_query

TEMPLATE_PATH = Path(__file__).parent / "templates" / "CLAUDE.md.tmpl"


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--repo", default=".", help="Path to target repo (default: cwd).")
    p.add_argument("--json", action="store_true", help="Emit raw JSON.")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="scope",
        description="Scope Intelligence Toolkit — compact, language-agnostic scope index.",
    )
    p.add_argument("--version", action="version", version=f"scope {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    # init
    p_init = sub.add_parser("init", help="Create .scope-intelligence/ in the target repo.")
    p_init.add_argument("--repo", default=".")
    p_init.add_argument("--write-claude-md", action="store_true",
                        help="Write a CLAUDE.md hint at the repo root if missing.")

    # index
    p_idx = sub.add_parser("index", help="Full index build over the repo.")
    p_idx.add_argument("path", nargs="?", default=".")
    p_idx.add_argument("--incremental", action="store_true",
                       help="Skip files whose content hash is unchanged since last index.")
    p_idx.add_argument("--verbose", action="store_true")

    # update — re-parse a listed subset of files
    p_upd = sub.add_parser("update", help="Re-parse a subset of files (after edits).")
    _add_common(p_upd)
    p_upd.add_argument("--files", nargs="+", required=True,
                       help="Repo-relative paths to re-parse.")

    # summary
    p_sum = sub.add_parser("summary", help="Repo-wide overview.")
    _add_common(p_sum)

    # features — list all
    p_lf = sub.add_parser("features", help="List all detected features.")
    _add_common(p_lf)

    # feature — single feature scope
    p_feat = sub.add_parser("feature", help="Scope of a single feature.")
    _add_common(p_feat)
    p_feat.add_argument("name", help="Feature id or alias.")

    # impacted
    p_imp = sub.add_parser("impacted", help="Files transitively impacted by a change.")
    _add_common(p_imp)
    p_imp.add_argument("--file", help="Repo-relative file path.")
    p_imp.add_argument("--feature", help="Feature id or alias.")
    p_imp.add_argument("--symbol", help="Symbol name or qualified name.")

    # tests
    p_tst = sub.add_parser("tests", help="Tests covering a file or feature.")
    _add_common(p_tst)
    p_tst.add_argument("--file")
    p_tst.add_argument("--feature")

    # symbol — callers + callees
    p_sym = sub.add_parser("symbol", help="Callers + callees of a symbol (full context).")
    _add_common(p_sym)
    p_sym.add_argument("name")

    # callers — who calls a symbol
    p_callers = sub.add_parser("callers", help="All callers of a symbol (cross-file).")
    _add_common(p_callers)
    p_callers.add_argument("name")

    # callees — what a symbol calls
    p_callees = sub.add_parser("callees", help="All callees of a symbol (cross-file).")
    _add_common(p_callees)
    p_callees.add_argument("name")

    # touchpoints
    p_tp = sub.add_parser("touchpoints", help="Routes, configs, DB models found in the repo.")
    _add_common(p_tp)
    p_tp.add_argument("--type", choices=["routes", "configs", "db_models", "events"],
                      help="Filter to one touchpoint category.")
    p_tp.add_argument("--feature", help="Filter by feature.")
    p_tp.add_argument("--file", help="Filter by file.")

    # diff — git-based scope delta
    p_diff = sub.add_parser("diff",
                            help="Scope impact of a git change (default: HEAD~1).")
    _add_common(p_diff)
    p_diff.add_argument("ref", nargs="?", default="HEAD~1",
                        help="Git ref to diff against (default: HEAD~1).")

    # report — token savings dashboard
    p_rep = sub.add_parser("report", help="Token savings report from past queries.")
    p_rep.add_argument("--repo", default=".")
    p_rep.add_argument("--html", action="store_true", help="Generate HTML dashboard.")
    p_rep.add_argument("--output", default="scope-report.html",
                       help="Output path for --html (default: scope-report.html).")

    # global-report — cross-repo dashboard
    p_gr = sub.add_parser("global-report",
                           help="Aggregated token savings across multiple repos.")
    p_gr.add_argument("--repo", action="append", dest="repos", default=[],
                      metavar="PATH",
                      help="Repo path to include (repeat for each repo).")
    p_gr.add_argument("--html", action="store_true", help="Generate HTML dashboard.")
    p_gr.add_argument("--output", default="global-scope-report.html",
                      help="Output path for --html (default: global-scope-report.html).")

    # serve — MCP stdio server
    sub.add_parser("serve", help="Start MCP JSON-RPC 2.0 stdio server.")

    # doc — document ingestion
    p_doc = sub.add_parser("doc", help="Document ingestion — parse design docs into .ai-context/.")
    doc_sub = p_doc.add_subparsers(dest="doc_cmd", required=True)

    p_ingest = doc_sub.add_parser(
        "ingest",
        help="Parse a design doc (PDF/DOCX/MD/TXT) and generate .ai-context/ files.",
    )
    p_ingest.add_argument("doc", help="Path to the design document.")
    p_ingest.add_argument("--repo", default=".", help="Target repo root (default: cwd).")
    p_ingest.add_argument(
        "--overwrite", action="store_true",
        help="Regenerate files that already exist (default: skip existing).",
    )
    p_ingest.add_argument(
        "--dry-run", action="store_true",
        help="Parse and report what would be generated without writing anything.",
    )
    p_ingest.add_argument(
        "--no-claude-md", action="store_true",
        help="Skip updating CLAUDE.md at repo root.",
    )
    p_ingest.add_argument(
        "--mode", choices=["python", "llm"], default="python",
        help=(
            "Extraction mode. "
            "'python' = fast regex routing, no LLM (default). "
            "'llm'    = Qwen/Ollama classifies each chunk — richer extraction, "
            "requires Ollama running locally."
        ),
    )
    p_ingest.add_argument(
        "--ollama-model", default="qwen2.5:14b", metavar="MODEL",
        help="Ollama model to use in --mode llm (default: qwen2.5:14b).",
    )
    p_ingest.add_argument(
        "--ollama-url", default="http://localhost:11434", metavar="URL",
        help="Ollama server URL (default: http://localhost:11434).",
    )
    p_ingest.add_argument(
        "--second-pass", action="store_true",
        help="Run a second Qwen pass to synthesise module-map.md from all component summaries.",
    )
    p_ingest.add_argument(
        "--if-changed", action="store_true", dest="if_changed",
        help=(
            "Skip ingest if the source document has not changed since the last run "
            "(compared by SHA-256 hash stored in index.json)."
        ),
    )
    p_ingest.add_argument("--json", action="store_true", help="Emit raw JSON result.")

    # doc list — show what's been generated
    p_list = doc_sub.add_parser(
        "list",
        help="List all .ai-context/ files generated for this repo.",
    )
    p_list.add_argument("--repo", default=".", help="Target repo root (default: cwd).")
    p_list.add_argument("--json", action="store_true", help="Emit raw JSON result.")

    # doc fetch — retrieve content of a generated file
    p_fetch = doc_sub.add_parser(
        "fetch",
        help="Print the content of a generated .ai-context/ file.",
    )
    p_fetch.add_argument(
        "name",
        help=(
            "File id or partial name, e.g. 'overview', '001', 'constraints'. "
            "Matched against file ids in .ai-context/generated/index.json."
        ),
    )
    p_fetch.add_argument("--repo", default=".", help="Target repo root (default: cwd).")
    p_fetch.add_argument("--json", action="store_true", help="Emit raw JSON result.")

    # doc clear — remove generated .ai-context/ files
    p_clear = doc_sub.add_parser(
        "clear",
        help="Remove all .ai-context/ generated files (keeps curated/ by default).",
    )
    p_clear.add_argument("--repo", default=".", help="Target repo root (default: cwd).")
    p_clear.add_argument(
        "--all", action="store_true", dest="clear_all",
        help="Also remove curated/ files (constraints.md, current-phase.md, module-map.md).",
    )
    p_clear.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be removed without deleting anything.",
    )

    # doc rebuild — clear generated/ then re-ingest
    p_rebuild = doc_sub.add_parser(
        "rebuild",
        help="Clear generated .ai-context/ files and re-ingest a design doc in one step.",
    )
    p_rebuild.add_argument("doc", help="Path to the design document.")
    p_rebuild.add_argument("--repo", default=".", help="Target repo root (default: cwd).")
    p_rebuild.add_argument(
        "--mode", choices=["python", "llm"], default="python",
        help="Extraction mode (default: python).",
    )
    p_rebuild.add_argument("--ollama-model", default="qwen2.5:14b", metavar="MODEL")
    p_rebuild.add_argument("--ollama-url", default="http://localhost:11434", metavar="URL")
    p_rebuild.add_argument("--second-pass", action="store_true")
    p_rebuild.add_argument("--no-claude-md", action="store_true")
    p_rebuild.add_argument("--json", action="store_true", help="Emit raw JSON result.")

    # doc export — concatenate all .ai-context/ into one file
    p_export = doc_sub.add_parser(
        "export",
        help="Concatenate all .ai-context/ files into a single file (or stdout).",
    )
    p_export.add_argument("--repo", default=".", help="Target repo root (default: cwd).")
    p_export.add_argument(
        "--output", default="-", metavar="FILE",
        help="Output file path. Use '-' for stdout (default: -).",
    )
    p_export.add_argument(
        "--layer", choices=["generated", "curated", "all"], default="all",
        help="Which layer to include (default: all).",
    )
    p_export.add_argument(
        "--no-header", action="store_true",
        help="Omit the export header comment.",
    )
    p_export.add_argument("--json", action="store_true", help="Emit raw JSON result.")

    # doc stats — token/char counts per .ai-context/ file
    p_stats = doc_sub.add_parser(
        "stats",
        help="Show character and estimated token counts for all .ai-context/ files.",
    )
    p_stats.add_argument("--repo", default=".", help="Target repo root (default: cwd).")
    p_stats.add_argument("--json", action="store_true", help="Emit raw JSON result.")

    # doc search — grep across generated .ai-context/ files
    p_search = doc_sub.add_parser(
        "search",
        help="Search all .ai-context/ files for a keyword or phrase.",
    )
    p_search.add_argument("query", help="Keyword or phrase to search for (case-insensitive).")
    p_search.add_argument("--repo", default=".", help="Target repo root (default: cwd).")
    p_search.add_argument(
        "--layer", choices=["generated", "curated", "all"], default="all",
        help="Which layer to search (default: all).",
    )
    p_search.add_argument(
        "--context", type=int, default=2, metavar="N",
        help="Lines of context around each match (default: 2).",
    )
    p_search.add_argument("--json", action="store_true", help="Emit raw JSON result.")

    # mem — MemPalace long-term memory
    p_mem = sub.add_parser("mem", help="MemPalace: long-term knowledge store.")
    mem_sub = p_mem.add_subparsers(dest="mem_cmd", required=True)

    # mem add
    p_madd = mem_sub.add_parser("add", help="Record a memory (bug, decision, failure, etc.)")
    p_madd.add_argument("--repo", default=".")
    p_madd.add_argument("--type", dest="kind", default="note",
                        choices=["semantic", "procedure",
                                 "bug", "decision", "failure", "ownership", "note", "fix"],
                        help="Memory type (default: note).")
    p_madd.add_argument("--note", required=True, help="The memory text / title.")
    p_madd.add_argument("--file", nargs="+", dest="files", default=[],
                        help="Repo-relative files this memory concerns.")
    p_madd.add_argument("--feature", nargs="+", dest="features", default=[],
                        help="Feature ids this memory concerns.")
    p_madd.add_argument("--symbol", nargs="+", dest="symbols", default=[],
                        help="Symbol names this memory concerns.")
    p_madd.add_argument("--tag", nargs="+", dest="tags", default=[],
                        help="Free-form tags.")
    p_madd.add_argument("--author", default="", help="Author identifier.")
    p_madd.add_argument("--resolved", action="store_true",
                        help="Mark this entry as already resolved.")
    p_madd.add_argument("--confidence", type=float, default=1.0,
                        help="Confidence 0.0-1.0 for semantic facts (default: 1.0).")
    p_madd.add_argument("--step", action="append", dest="steps", default=[],
                        metavar="STEP",
                        help="One step for a procedure memory. Repeat flag for each step.")

    # mem fetch — uses Phase 1-3 scope engine internally
    p_mfetch = mem_sub.add_parser(
        "fetch", help="Fetch layered memories relevant to a feature/file/symbol.")
    p_mfetch.add_argument("--repo", default=".")
    p_mfetch.add_argument("--feature", help="Feature id or alias.")
    p_mfetch.add_argument("--file", help="Repo-relative file path.")
    p_mfetch.add_argument("--symbol", help="Symbol name.")
    p_mfetch.add_argument("--type", dest="kind",
                          choices=["semantic", "procedure",
                                   "bug", "decision", "failure", "ownership", "note", "fix"],
                          help="Filter to one memory type.")
    p_mfetch.add_argument("--include-resolved", action="store_true",
                          help="Include already-resolved entries.")
    p_mfetch.add_argument("--limit", type=int, default=20,
                          help="Max entries to return (default: 20).")
    p_mfetch.add_argument("--json", action="store_true")

    # mem list
    p_mlist = mem_sub.add_parser("list", help="List all memories (with optional filters).")
    p_mlist.add_argument("--repo", default=".")
    p_mlist.add_argument("--type", dest="kind",
                         choices=["semantic", "procedure",
                                  "bug", "decision", "failure", "ownership", "note", "fix"])
    p_mlist.add_argument("--tag")
    p_mlist.add_argument("--open-only", action="store_true",
                         help="Hide resolved entries.")
    p_mlist.add_argument("--json", action="store_true")

    # mem resolve
    p_mres = mem_sub.add_parser("resolve", help="Mark a memory entry as resolved.")
    p_mres.add_argument("--repo", default=".")
    p_mres.add_argument("id", help="Memory id (mp_...).")

    # mem churn
    p_mchurn = mem_sub.add_parser("churn", help="Git-based file/feature churn analysis.")
    p_mchurn.add_argument("--repo", default=".")
    p_mchurn.add_argument("--days", type=int, default=90,
                          help="Look back N days (default: 90).")
    p_mchurn.add_argument("--json", action="store_true")

    # mem auto-capture  (Phase 5)
    p_mac = mem_sub.add_parser("auto-capture",
                               help="Scan git log and auto-create episodic memories.")
    p_mac.add_argument("--repo", default=".")
    p_mac.add_argument("--days", type=int, default=30,
                       help="Commits to scan (default: last 30 days).")
    p_mac.add_argument("--dry-run", action="store_true",
                       help="Preview what would be captured without writing.")
    p_mac.add_argument("--json", action="store_true")

    # mem decay  (Phase 5)
    p_mdecay = mem_sub.add_parser("decay",
                                  help="Apply confidence decay to semantic memories.")
    p_mdecay.add_argument("--repo", default=".")
    p_mdecay.add_argument("--half-life", type=int, default=90, dest="half_life",
                          help="Days for confidence to halve (default: 90).")
    p_mdecay.add_argument("--floor", type=float, default=0.1,
                          help="Minimum confidence after decay (default: 0.1).")
    p_mdecay.add_argument("--dry-run", action="store_true",
                          help="Preview changes without writing.")
    p_mdecay.add_argument("--json", action="store_true")

    # mem search  (Phase 5)
    p_msearch = mem_sub.add_parser("search",
                                   help="TF-IDF free-text search over memory notes.")
    p_msearch.add_argument("--repo", default=".")
    p_msearch.add_argument("query", help="Free-text search query.")
    p_msearch.add_argument("--type", dest="kind",
                           choices=["semantic", "procedure",
                                    "bug", "decision", "failure",
                                    "ownership", "note", "fix"])
    p_msearch.add_argument("--limit", type=int, default=10,
                           help="Max results (default: 10).")
    p_msearch.add_argument("--json", action="store_true")

    # mem export  (Phase 5)
    p_mexp = mem_sub.add_parser("export",
                                help="Export mempalace to a portable JSON file.")
    p_mexp.add_argument("--repo", default=".")
    p_mexp.add_argument("--output", default="mempalace_export.json",
                        help="Output file path (default: mempalace_export.json).")

    # mem import  (Phase 5)
    p_mimp = mem_sub.add_parser("import",
                                help="Import memories from a portable JSON file.")
    p_mimp.add_argument("--repo", default=".")
    p_mimp.add_argument("file", help="Path to exported JSON file.")
    p_mimp.add_argument("--replace", action="store_true",
                        help="Replace existing mempalace (default: merge, skip duplicates).")
    p_mimp.add_argument("--json", action="store_true")

    # mem conflicts  (Phase 5)
    p_mconf = mem_sub.add_parser("conflicts",
                                 help="Detect potentially contradicting semantic memories.")
    p_mconf.add_argument("--repo", default=".")
    p_mconf.add_argument("--include-resolved", action="store_true")
    p_mconf.add_argument("--json", action="store_true")

    return p


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_repo(arg: str) -> Path:
    return Path(arg).resolve()


def _emit(payload: dict, as_json: bool, *, formatter=None) -> None:
    if as_json or formatter is None:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        formatter(payload)


def _not_indexed(repo: Path) -> bool:
    if not store.is_initialized(repo):
        print(f"error: {repo} has no scope index. Run `scope init && scope index` first.",
              file=sys.stderr)
        return True
    return False


# ---------------------------------------------------------------------------
# Formatters (human view)
# ---------------------------------------------------------------------------

def _fmt_summary(s: dict) -> None:
    if "error" in s:
        print(s["error"]); return
    t = s.get("totals", {})
    print(f"repo: {s.get('repo_root')}")
    print(f"files={t.get('files')}  symbols={t.get('symbols')}  "
          f"tests={t.get('tests')}  features={t.get('features')}")
    if s.get("languages"):
        print("languages: " + ", ".join(f"{k}={v}" for k, v in s["languages"].items()))
    if s.get("test_frameworks"):
        print("test frameworks: " + ", ".join(f"{k}={v}"
              for k, v in s["test_frameworks"].items()))
    print("\ntop features:")
    for f in s.get("top_features", []):
        print(f"  - {f['id']}  files={f['files']}  symbols={f['symbols']}  "
              f"tests={f.get('tests', 0)}  langs={','.join(f.get('languages', []))}")
    if s.get("most_imported_files"):
        print("\nmost-imported files:")
        for m in s["most_imported_files"][:5]:
            print(f"  - {m['file']}  imported_by={m['imported_by']}")


def _fmt_features_list(payload: dict) -> None:
    feats = payload.get("features", [])
    if not feats:
        print("no features indexed"); return
    for f in feats:
        print(f"- {feature_one_liner(f)}")


def _fmt_feature(s: dict) -> None:
    if "error" in s:
        print(s["error"])
        if "available" in s:
            print("available: " + ", ".join(s["available"]))
        return
    f = s["feature"]
    print(f"# feature: {f['id']}")
    print(f"languages: {', '.join(f.get('languages', []))}")
    print(f"files: {f.get('file_count')}    symbols: {f.get('symbol_count')}")
    if f.get("aliases"):
        print(f"aliases: {', '.join(f['aliases'])}")
    if f.get("depends_on_features"):
        print(f"depends on: {', '.join(f['depends_on_features'])}")
    if f.get("entry_points"):
        print("entry points:")
        for ep in f["entry_points"]:
            print(f"  - {ep}")
    print("\nfiles:")
    for fp in s["files"][:20]:
        print(f"  - {fp}")
    if len(s["files"]) > 20:
        print(f"  ... +{len(s['files']) - 20} more")
    if s.get("tests"):
        print("\nrelated tests:")
        for t in s["tests"]:
            print(f"  - {t['file']}  ({t['framework']}, {len(t['cases'])} cases)")


def _fmt_impacted(s: dict) -> None:
    if "error" in s:
        print(s["error"]); return
    print(f"targets: {', '.join(s.get('targets', []))}")
    for label, key in [("direct", "direct"), ("transitive", "transitive")]:
        items = s.get(key, [])
        print(f"{label}  ({len(items)}):")
        for f in items[:30]:
            print(f"  - {f}")
        if len(items) > 30:
            print(f"  ... +{len(items) - 30} more")
    feats = s.get("features", [])
    if feats:
        print(f"features touched: {', '.join(feats)}")


def _fmt_tests(s: dict) -> None:
    matches = s.get("matches", [])
    if not matches:
        print(s.get("note", "no matches")); return
    for m in matches:
        print(f"- {m['file']}  ({m.get('framework')})")
        if m.get("cases"):
            extra = "  ..." if len(m["cases"]) > 6 else ""
            print(f"    cases: {', '.join(m['cases'][:6])}{extra}")
        if m.get("covers_files"):
            extra = "  ..." if len(m["covers_files"]) > 3 else ""
            print(f"    covers: {', '.join(m['covers_files'][:3])}{extra}")


def _fmt_symbol(s: dict) -> None:
    if "error" in s:
        print(s["error"]); return
    for m in s["matches"]:
        sym = m["symbol"]
        print(f"# {sym['id']}  ({sym['kind']}, line {sym.get('line')})")
        print(f"  feature: {sym.get('feature') or '?'}    language: {sym.get('language')}")
        if sym.get("params"):
            print(f"  params: {', '.join(sym['params'])}")
        if sym.get("reads"):
            print(f"  reads:  {', '.join(sym['reads'][:8])}")
        if sym.get("writes"):
            print(f"  writes: {', '.join(sym['writes'][:8])}")
        if m.get("callees"):
            print("  calls:")
            for c in m["callees"][:10]:
                print(f"    - {c.get('id') or c.get('name')}  [{c.get('file', '')}]")
        if m.get("callers"):
            print("  called by:")
            for c in m["callers"][:10]:
                print(f"    - {c['id']}  [{c.get('file', '')}]")
        print()


def _fmt_callers(s: dict) -> None:
    if "error" in s:
        print(s["error"]); return
    for m in s["matches"]:
        print(f"callers of {m['symbol']}:")
        if not m["callers"]:
            print("  (none resolved — symbol may be a top-level entry point)"); continue
        for c in m["callers"]:
            print(f"  - {c['id']}  [{c.get('kind')}]  {c.get('file', '')}")


def _fmt_callees(s: dict) -> None:
    if "error" in s:
        print(s["error"]); return
    for m in s["matches"]:
        print(f"callees of {m['symbol']}:")
        if not m["callees"] and not m.get("unresolved"):
            print("  (none)"); continue
        for c in m["callees"]:
            print(f"  - {c['id']}  [{c.get('kind')}]  {c.get('file', '')}")
        if m.get("unresolved"):
            print(f"  unresolved bare calls: {', '.join(m['unresolved'])}")


def _fmt_touchpoints(s: dict) -> None:
    if "error" in s:
        print(s["error"]); return
    t = s.get("totals", {})
    total = sum(t.values())
    if total == 0:
        print("no touchpoints found — add Flask/Spring/Express decorators or run scope index"); return
    if s.get("routes"):
        print(f"routes ({len(s['routes'])}):")
        for r in s["routes"]:
            print(f"  [{r.get('method','?'):6}] {r.get('path')}  ->  {r.get('handler') or '?'}"
                  f"  [{r.get('framework')}]  {r.get('file', '')}")
    if s.get("configs"):
        print(f"\nconfig keys ({len(s['configs'])}):")
        for c in s["configs"]:
            dflt = f" (default: {c['default']})" if c.get("default") else ""
            print(f"  {c.get('name')}{dflt}  [{c.get('file', '')}:{c.get('line', '?')}]")
    if s.get("db_models"):
        print(f"\ndb models ({len(s['db_models'])}):")
        for m in s["db_models"]:
            tbl = f" → table={m['table']}" if m.get("table") else ""
            print(f"  {m.get('name')}{tbl}  [{m.get('file', '')}]")
    if s.get("events"):
        print(f"\nevents ({len(s['events'])}):")
        for e in s["events"]:
            print(f"  {e.get('name')}  [{e.get('kind')}]  [{e.get('file', '')}]")


def _fmt_mem_entry(e: dict, indent: str = "  ") -> None:
    status = "[resolved]" if e.get("resolved") else "[open]"
    etype = e.get("type", "note")
    # type-specific prefix
    if etype == "semantic":
        conf = e.get("confidence", 1.0)
        type_str = f"[semantic  conf={conf:.0%}]"
    elif etype == "procedure":
        type_str = f"[procedure steps={len(e.get('steps', []))}]"
    else:
        type_str = f"[{etype}]"

    print(f"{indent}{e['id']}  {type_str} {status}  {e.get('ts','')}")
    print(f"{indent}{e['note']}")

    if etype == "procedure" and e.get("steps"):
        for i, step in enumerate(e["steps"], 1):
            print(f"{indent}  {i}. {step}")

    scope = e.get("scope", {})
    if scope.get("files"):
        print(f"{indent}files: {', '.join(scope['files'])}")
    if scope.get("features"):
        print(f"{indent}features: {', '.join(scope['features'])}")
    if scope.get("symbols"):
        print(f"{indent}symbols: {', '.join(scope['symbols'])}")
    if e.get("tags"):
        print(f"{indent}tags: {', '.join(e['tags'])}")
    print()


def _fmt_mem_fetch(s: dict) -> None:
    if "error" in s:
        print(s["error"]); return

    rscope = s.get("resolved_scope", {})
    print(f"resolved scope: "
          f"files={len(rscope.get('files', []))}  "
          f"features={len(rscope.get('features', []))}  "
          f"symbols={len(rscope.get('symbols', []))}")
    if rscope.get("features"):
        print(f"  features: {', '.join(sorted(rscope['features']))}")
    if rscope.get("files"):
        shown = sorted(rscope["files"])[:5]
        more = len(rscope["files"]) - 5
        print(f"  files: {', '.join(shown)}" + (f"  +{more} more" if more > 0 else ""))
    for w in s.get("warnings", []):
        print(f"  warning: {w}")

    layers = s.get("layers", {})

    # Structural layer — compact summary
    struct = layers.get("structural", {})
    if struct.get("features") or struct.get("files"):
        print("\n[structural]")
        for feat in struct.get("features", []):
            deps = f"  depends: {', '.join(feat['depends_on'])}" if feat.get("depends_on") else ""
            print(f"  feature {feat['id']}: "
                  f"{feat['file_count']} files  {feat['symbol_count']} symbols  "
                  f"lang={','.join(feat.get('languages', []))}{deps}")
        for f in struct.get("files", []):
            print(f"  {f['file']}  [{f['language']}]  {f['loc']} loc  {f['symbols']} symbols")

    # Semantic layer — timeless facts
    sem = layers.get("semantic", [])
    if sem:
        print(f"\n[semantic facts]  ({len(sem)})")
        print("-" * 50)
        for e in sem:
            _fmt_mem_entry(e)

    # Procedural layer — step-by-step workflows
    proc = layers.get("procedural", [])
    if proc:
        print(f"\n[procedural workflows]  ({len(proc)})")
        print("-" * 50)
        for e in proc:
            _fmt_mem_entry(e)

    # Episodic layer — past incidents
    epi = layers.get("episodic", [])
    if epi:
        print(f"\n[episodic incidents]  ({len(epi)})")
        print("-" * 50)
        for e in epi:
            _fmt_mem_entry(e)

    if s.get("total", 0) == 0:
        print("\n  (no memories yet — add with: scope mem add --note \"...\")")


def _fmt_mem_list(s: dict) -> None:
    entries = s.get("entries", [])
    if not entries:
        print("no memories recorded yet. Use: scope mem add --note \"...\"")
        return
    print(f"total: {s['total']}")
    print("-" * 60)
    for e in entries:
        _fmt_mem_entry(e)


def _fmt_churn(s: dict) -> None:
    if "error" in s:
        print(s["error"]); return
    print(f"churn over last {s['days']} days  "
          f"({s.get('total_changed_files', 0)} unique files changed)")
    print("\ntop files:")
    for item in s.get("top_files", [])[:10]:
        bar = "#" * min(item["changes"], 20)
        print(f"  {item['file']:<45} {item['changes']:>3}x  {bar}")
    feats = s.get("features", {})
    if feats:
        print("\nhigh-churn features:")
        for fid, v in feats.items():
            print(f"  {fid:<20} {v['total_changes']} changes across {len(v['files'])} file(s)")


def _fmt_auto_capture(s: dict) -> None:
    if "error" in s:
        print(s["error"]); return
    dry = " [DRY RUN]" if s.get("dry_run") else ""
    print(f"auto-capture from last {s['days_scanned']} days{dry}")
    print(f"  captured:             {s['captured']}")
    print(f"  skipped (existing):   {s['skipped_existing']}")
    print(f"  skipped (no keyword): {s['skipped_unclassified']}")
    if s.get("entries"):
        print("\ncaptured entries:")
        for e in s["entries"]:
            print(f"  [{e.get('type','?')}]  {e.get('note','')[:70]}")
            if e.get("files"):
                print(f"         files: {', '.join(e['files'][:4])}")


def _fmt_decay(s: dict) -> None:
    if "error" in s:
        print(s["error"]); return
    dry = " [DRY RUN]" if s.get("dry_run") else ""
    print(f"confidence decay  half-life={s['half_life_days']}d  floor={s['floor']}{dry}")
    print(f"  updated:   {s['updated']}")
    print(f"  unchanged: {s['unchanged']}")
    if s.get("changes"):
        print("\nchanges:")
        for c in s["changes"]:
            print(f"  {c['id']}  age={c['age_days']}d  "
                  f"{c['old_confidence']:.0%} -> {c['new_confidence']:.0%}  "
                  f"{c['note'][:50]}")


def _fmt_search(s: dict) -> None:
    if "error" in s:
        print(s["error"]); return
    results = s.get("results", [])
    if not results:
        print(f"no memories matched: {s['query']}"); return
    print(f"search: \"{s['query']}\"  ({s['total']} results)")
    print("-" * 60)
    for e in results:
        score = e.get("_score", 0)
        print(f"  score={score:.4f}  [{e.get('type','?')}]  {e['id']}")
        print(f"  {e.get('note','')}")
        if e.get("steps"):
            for i, step in enumerate(e["steps"], 1):
                print(f"    {i}. {step}")
        print()


def _fmt_conflicts(s: dict) -> None:
    if "error" in s:
        print(s["error"]); return
    print(f"conflict detection: {s['semantic_checked']} semantic memories checked")
    conflicts = s.get("conflicts", [])
    if not conflicts:
        print("  no conflicts detected"); return
    print(f"  {s['total']} potential conflict(s) found\n")
    for i, c in enumerate(conflicts, 1):
        a, b = c["memory_a"], c["memory_b"]
        print(f"conflict #{i}")
        print(f"  A  {a['id']}  conf={a['confidence']:.0%}  {a['ts']}")
        print(f"     {a['note']}")
        print(f"  B  {b['id']}  conf={b['confidence']:.0%}  {b['ts']}")
        print(f"     {b['note']}")
        if c.get("shared_files"):
            print(f"  shared files: {', '.join(c['shared_files'])}")
        if c.get("shared_features"):
            print(f"  shared features: {', '.join(c['shared_features'])}")
        print(f"  -> {c['suggestion']}")
        print()


def _fmt_diff(s: dict) -> None:
    if "error" in s:
        print(s["error"]); return
    print(f"diff vs {s.get('ref')}")
    changed = s.get("changed", [])
    removed = s.get("removed", [])
    not_indexed = s.get("not_in_index", [])
    print(f"\nchanged ({len(changed)}):")
    for f in changed:
        print(f"  ~ {f}")
    if removed:
        print(f"\nremoved ({len(removed)}):")
        for f in removed:
            print(f"  - {f}")
    if not_indexed:
        print(f"\nnot in index (new files?):")
        for f in not_indexed:
            print(f"  + {f}")
    direct = s.get("direct_impact", [])
    trans = s.get("transitive_impact", [])
    print(f"\ndirect impact ({len(direct)}):")
    for f in direct[:20]:
        print(f"  - {f}")
    if len(direct) > 20:
        print(f"  ... +{len(direct) - 20} more")
    print(f"transitive impact ({len(trans)}):")
    for f in trans[:20]:
        print(f"  - {f}")
    if len(trans) > 20:
        print(f"  ... +{len(trans) - 20} more")
    feats = s.get("features_touched", [])
    if feats:
        print(f"\nfeatures touched: {', '.join(feats)}")
    tests = s.get("related_tests", [])
    if tests:
        print(f"tests to run ({len(tests)}):")
        for t in tests[:15]:
            print(f"  - {t}")
        if len(tests) > 15:
            print(f"  ... +{len(tests) - 15} more")


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def cmd_init(args) -> int:
    repo = _resolve_repo(args.repo)
    if not repo.exists():
        print(f"error: {repo} does not exist", file=sys.stderr); return 2
    store.ensure_index_dir(repo)
    if not store.read_json(repo, "config"):
        store.write_json(repo, "config", store.default_config())
    print(f"initialized {store.index_dir(repo)}")
    if args.write_claude_md:
        target = repo / "CLAUDE.md"
        if target.exists():
            print("CLAUDE.md already exists — not overwriting.")
        else:
            target.write_text(TEMPLATE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"wrote {target}")
    print("\nNext: `scope index` from inside the repo.")
    return 0


def cmd_index(args) -> int:
    repo = _resolve_repo(args.path)
    if not store.is_initialized(repo):
        store.ensure_index_dir(repo)
        store.write_json(repo, "config", store.default_config())
    counts = build_index(repo, incremental=args.incremental, verbose=args.verbose)
    skipped = counts.get("skipped_unchanged", 0)
    print(f"indexed: files={counts['files']}  symbols={counts['symbols']}  "
          f"tests={counts['tests']}  features={counts['features']}  "
          f"touchpoints={counts.get('touchpoints', 0)}"
          + (f"  skipped={skipped}" if skipped else ""))
    print(f"index dir: {store.index_dir(repo)}")
    return 0


def cmd_update(args) -> int:
    repo = _resolve_repo(args.repo)
    if _not_indexed(repo): return 2
    counts = build_index(repo, only_files=args.files)
    print(f"updated {len(args.files)} file(s). totals: "
          f"files={counts['files']}  symbols={counts['symbols']}  tests={counts['tests']}")
    return 0


def cmd_summary(args) -> int:
    repo = _resolve_repo(args.repo)
    if _not_indexed(repo): return 2
    _emit(get_repo_summary(repo), args.json, formatter=_fmt_summary)
    return 0


def cmd_features(args) -> int:
    repo = _resolve_repo(args.repo)
    payload = store.read_json(repo, "features", {"features": []})
    _emit(payload, args.json, formatter=_fmt_features_list)
    return 0


def cmd_feature(args) -> int:
    repo = _resolve_repo(args.repo)
    if _not_indexed(repo): return 2
    t0 = time.monotonic()
    scope = get_feature_scope(repo, args.name)
    ms = int((time.monotonic() - t0) * 1000)
    _emit(scope, args.json, formatter=_fmt_feature)
    if "error" not in scope:
        log_query(repo, "feature", {"name": args.name},
                  scope.get("files", []), latency_ms=ms)
    return 0


def cmd_impacted(args) -> int:
    repo = _resolve_repo(args.repo)
    if _not_indexed(repo): return 2
    t0 = time.monotonic()
    scope = find_impacted_files(repo, file=args.file, feature=args.feature,
                                symbol=args.symbol)
    ms = int((time.monotonic() - t0) * 1000)
    _emit(scope, args.json, formatter=_fmt_impacted)
    if "error" not in scope:
        result_files = list(dict.fromkeys(
            scope.get("targets", []) +
            scope.get("direct", []) +
            scope.get("transitive", [])
        ))
        log_query(repo, "impacted",
                  {"file": args.file, "feature": args.feature, "symbol": args.symbol},
                  result_files, latency_ms=ms)
    return 0


def cmd_tests(args) -> int:
    repo = _resolve_repo(args.repo)
    if _not_indexed(repo): return 2
    t0 = time.monotonic()
    scope = get_related_tests(repo, file=args.file, feature=args.feature)
    ms = int((time.monotonic() - t0) * 1000)
    _emit(scope, args.json, formatter=_fmt_tests)
    result_files = [m["file"] for m in scope.get("matches", [])]
    if result_files:
        log_query(repo, "tests",
                  {"file": args.file, "feature": args.feature},
                  result_files, latency_ms=ms)
    return 0


def cmd_symbol(args) -> int:
    repo = _resolve_repo(args.repo)
    if _not_indexed(repo): return 2
    t0 = time.monotonic()
    scope = get_symbol_context(repo, args.name)
    ms = int((time.monotonic() - t0) * 1000)
    _emit(scope, args.json, formatter=_fmt_symbol)
    if "error" not in scope:
        result_files = list(dict.fromkeys(
            f for m in scope.get("matches", [])
            if (f := m["symbol"].get("file"))
        ))
        log_query(repo, "symbol", {"name": args.name},
                  result_files, latency_ms=ms)
    return 0


def cmd_callers(args) -> int:
    repo = _resolve_repo(args.repo)
    if _not_indexed(repo): return 2
    t0 = time.monotonic()
    scope = get_callers(repo, args.name)
    ms = int((time.monotonic() - t0) * 1000)
    _emit(scope, args.json, formatter=_fmt_callers)
    if "error" not in scope:
        result_files = list(dict.fromkeys(
            f for m in scope.get("matches", [])
            for c in m.get("callers", [])
            if (f := c.get("file"))
        ))
        log_query(repo, "callers", {"name": args.name},
                  result_files, latency_ms=ms)
    return 0


def cmd_callees(args) -> int:
    repo = _resolve_repo(args.repo)
    if _not_indexed(repo): return 2
    t0 = time.monotonic()
    scope = get_callees(repo, args.name)
    ms = int((time.monotonic() - t0) * 1000)
    _emit(scope, args.json, formatter=_fmt_callees)
    if "error" not in scope:
        result_files = list(dict.fromkeys(
            f for m in scope.get("matches", [])
            for c in m.get("callees", [])
            if (f := c.get("file"))
        ))
        log_query(repo, "callees", {"name": args.name},
                  result_files, latency_ms=ms)
    return 0


def cmd_touchpoints(args) -> int:
    repo = _resolve_repo(args.repo)
    if _not_indexed(repo): return 2
    t0 = time.monotonic()
    scope = get_touchpoints(repo, kind=args.type, feature=args.feature, file=args.file)
    ms = int((time.monotonic() - t0) * 1000)
    _emit(scope, args.json, formatter=_fmt_touchpoints)
    if "error" not in scope:
        result_files = list(dict.fromkeys(
            item["file"]
            for key in ("routes", "configs", "db_models", "events")
            for item in scope.get(key, [])
            if item.get("file")
        ))
        log_query(repo, "touchpoints",
                  {"type": args.type, "feature": args.feature, "file": args.file},
                  result_files, latency_ms=ms)
    return 0


def cmd_diff(args) -> int:
    repo = _resolve_repo(args.repo)
    if _not_indexed(repo): return 2
    _emit(compute_diff_scope(repo, args.ref), args.json, formatter=_fmt_diff)
    return 0


def cmd_report(args) -> int:
    repo = _resolve_repo(args.repo)
    summary = compute_savings_summary(repo)
    mem = memory_stats(repo)
    summary["memory"] = mem
    if args.html:
        out = Path(args.output).resolve()
        html_content = format_html(summary, repo)
        out.write_text(html_content, encoding="utf-8")
        print(f"report written to {out}")
    else:
        print(format_terminal(summary))
        if mem.get("total", 0) > 0:
            print(f"\n  MemPalace: {mem['total']} entries  "
                  f"({mem.get('open',0)} open, {mem.get('resolved',0)} resolved)")
            bt = mem.get("by_type", {})
            if bt:
                print("  by type: " + "  ".join(f"{k}={v}" for k, v in bt.items()))
    return 0


def cmd_global_report(args) -> int:
    if not args.repos:
        print("error: provide at least one --repo path", file=sys.stderr)
        return 2
    repo_paths = [Path(r).resolve() for r in args.repos]
    missing = [str(p) for p in repo_paths if not (p / ".scope-intelligence").exists()]
    if missing:
        for m in missing:
            print(f"warning: no scope index at {m} — run `scope init && scope index` there first",
                  file=sys.stderr)
    g = compute_global_summary(repo_paths)
    if args.html:
        out = Path(args.output).resolve()
        out.write_text(format_global_html(g), encoding="utf-8")
        print(f"global report written to {out}")
    else:
        print(format_global_terminal(g))
    return 0


def cmd_serve(_args) -> int:
    from .mcp_server import serve
    serve()
    return 0


# ---------------------------------------------------------------------------
# Doc ingest formatter + handler
# ---------------------------------------------------------------------------

def _fmt_ingest(r: dict) -> None:
    if "error" in r:
        print(r["error"]); return

    # --if-changed shortcut: doc unchanged, nothing to do
    if r.get("unchanged"):
        print(f"scope doc ingest  [unchanged — skipped]")
        print(f"  source: {r['source']}")
        print(f"  hash:   {r.get('source_hash', '?')}  (matches stored hash)")
        print(f"  note:   {r.get('note', '')}")
        return

    dry = "  [DRY RUN — nothing written]" if r.get("dry_run") else ""
    mode_tag = f"  [mode={r.get('mode','python')}]" if r.get("mode") else ""
    print(f"scope doc ingest{dry}{mode_tag}")

    if r.get("warning"):
        print(f"  ⚠ {r['warning']}")

    print(f"  source:            {r['source']}")
    print(f"  format:            {r['format']}")
    print(f"  sections parsed:   {r['sections_parsed']}")
    print(f"  sections unmatched:{r['sections_unmatched']}")
    print(f"  files written:     {r['files_written']}")
    print(f"  files skipped:     {r['files_skipped']}")
    print(f"  memories added:    {r['memories_added']}")
    print(f"  features added:    {r['features_added']}")

    if r.get("llm_chunks_classified") is not None:
        total   = r["llm_chunks_classified"]
        by_llm  = r.get("llm_chunks_by_llm", 0)
        fb      = r.get("llm_chunks_fallback", 0)
        pct     = f"  ({by_llm/total*100:.0f}% by LLM)" if total else ""
        print(f"  chunks classified: {total}  (llm={by_llm}  fallback={fb}){pct}")

    gctx = r.get("global_context")
    if gctx and gctx.get("project_name"):
        print(f"  project detected:  {gctx['project_name']}")
        if gctx.get("tech_stack"):
            print(f"  tech stack:        {', '.join(gctx['tech_stack'][:6])}")

    if r.get("conflicts_after_ingest") is not None:
        n = r["conflicts_after_ingest"]
        flag = "  ⚠ run: scope mem conflicts" if n > 0 else ""
        print(f"  post-ingest conflicts: {n}{flag}")

    written = [f for f in r.get("generated", []) if f.get("status") == "written"]
    skipped = [f for f in r.get("generated", []) if f.get("status") == "skipped_existing"]

    if written:
        print("\ngenerated files:")
        for f in sorted(written, key=lambda x: x["path"]):
            layer_tag = f"[{f['layer']}]"
            print(f"  {layer_tag:<12} {f['path']}")

    if skipped:
        print("\nskipped (already exist — use --overwrite to regenerate):")
        for f in sorted(skipped, key=lambda x: x["path"]):
            print(f"  {f['path']}")

    templates = r.get("templates_created", [])
    if templates:
        print("\ncurated templates created (edit these manually):")
        for t in sorted(templates):
            print(f"  ✏  {t}")
        print("  → run `scope doc fetch constraints` to view, then edit as needed")

    if r.get("unmatched_sections"):
        print(f"\nunmatched sections ({len(r['unmatched_sections'])}) "
              f"— not routed to any output file:")
        for title in r["unmatched_sections"][:10]:
            print(f"  - {title}")
        if len(r["unmatched_sections"]) > 10:
            print(f"  ... +{len(r['unmatched_sections']) - 10} more")

    # Routing table — shown in dry-run mode to let users debug section routing
    rt = r.get("routing_table", [])
    if r.get("dry_run") and rt:
        # Deduplicate: show each (section→file) pair once; build display rows first
        seen_rt: set[tuple] = set()
        disp_rows: list[dict] = []
        for entry in rt:
            key = (entry["section"], entry.get("file") or "")
            if key in seen_rt:
                continue
            seen_rt.add(key)
            lyr = entry.get("layer") or ""
            f   = entry.get("file")
            if f:
                dest = f"[{lyr}] {f}" if lyr else f
                hint_str = ""
            else:
                dest = "⚠ (unmatched)"
                hint = entry.get("hint")
                hint_str = f"  💡 {hint}" if hint else ""
            disp_rows.append({
                "section":  entry["section"],
                "dest":     dest,
                "via":      entry.get("via", ""),
                "hint_str": hint_str,
            })

        col1 = min(max((len(dr["section"]) for dr in disp_rows), default=7), 50)
        print(f"\nrouting table ({len(disp_rows)} sections):")
        print(f"  {'section':<{col1}}  {'→ output file'}")
        print(f"  {'─'*col1}  {'─'*40}")
        for dr in disp_rows:
            via_tag = f"  (via {dr['via']})" if dr["via"] else ""
            trunc   = dr["section"][:col1]
            print(f"  {trunc:<{col1}}  → {dr['dest']}{via_tag}{dr['hint_str']}")


def _doc_list(repo: Path) -> dict:
    """Return manifest of .ai-context/ files for this repo.

    index.json may include curated files (layer='curated') because ingest
    writes all generated_files there. We split by layer so the caller gets
    clean generated / curated lists without duplicates.
    """
    index_path = repo / ".ai-context" / "generated" / "index.json"
    if not index_path.exists():
        return {"error": "no .ai-context/ found — run `scope doc ingest` first"}
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"error": f"index.json unreadable: {exc}"}

    # Split index files by layer to avoid mixing curated into the generated list
    all_files = index.get("files", [])
    generated = [f for f in all_files if f.get("layer", "generated") == "generated"]

    # Curated: authoritative source is the filesystem (not index.json which may
    # include curated entries or may have been written by an older version).
    curated_dir = repo / ".ai-context" / "curated"
    curated: list[dict] = []
    if curated_dir.exists():
        for p in sorted(curated_dir.glob("*.md")):
            rel = str(p.relative_to(repo)).replace("\\", "/")
            curated.append({"id": p.stem, "path": rel, "layer": "curated"})

    # Check if source doc has changed since last ingest
    source_hash   = index.get("source_hash", "")
    source_name   = index.get("source", "")
    doc_changed   = False
    if source_hash and source_name:
        # Try to find the source doc relative to the repo root (best-effort)
        for candidate in [repo / source_name,
                          repo / "docs" / source_name,
                          repo / "design" / source_name]:
            if candidate.exists():
                from .core.doc_ingestor import _doc_hash as _dh
                current_hash = _dh(candidate)
                doc_changed = bool(current_hash and current_hash != source_hash)
                break

    return {
        "source":       source_name or "?",
        "generated_at": index.get("generated_at", "?"),
        "source_hash":  source_hash,
        "mode":         index.get("mode", "?"),
        "doc_changed":  doc_changed,
        "generated":    generated,
        "curated":      curated,
        "total":        len(generated) + len(curated),
    }


def _fmt_doc_list(r: dict) -> None:
    if "error" in r:
        print(r["error"]); return
    changed_tag = "  ⚠ source doc changed — run `scope doc rebuild`" if r.get("doc_changed") else ""
    print(f"AI context files — {r['total']} total  "
          f"(source: {r['source']}  mode: {r['mode']}  at: {r['generated_at']}){changed_tag}")
    if r.get("generated"):
        print("\ngenerated/")
        for f in r["generated"]:
            print(f"  {f['id']:<35} {f.get('title','')}")
    if r.get("curated"):
        print("\ncurated/")
        for f in r["curated"]:
            print(f"  {f['id']}")


def _doc_fetch(repo: Path, name: str) -> dict:
    """Retrieve content of a generated .ai-context/ file by id or partial name.

    Searches generated/ files first (via index.json), then curated/ files.
    Deduplicates by path so index.json entries and glob results for the same
    file are not double-counted.
    """
    index_path = repo / ".ai-context" / "generated" / "index.json"
    curated_dir = repo / ".ai-context" / "curated"

    candidates: list[dict] = []
    seen_paths: set[str] = set()

    def _add(entry: dict) -> None:
        p = entry.get("path", "")
        if p not in seen_paths:
            seen_paths.add(p)
            candidates.append(entry)

    q = name.lower()

    # Search generated files via index.json
    if index_path.exists():
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
            for f in index.get("files", []):
                if q in f["id"].lower() or q in f.get("title", "").lower():
                    _add(f)
        except Exception:  # noqa: BLE001
            pass

    # Search curated via filesystem (curated files may not be in index.json)
    if curated_dir.exists():
        for p in curated_dir.glob("*.md"):
            if q in p.stem.lower():
                rel = str(p.relative_to(repo)).replace("\\", "/")
                _add({
                    "id":    p.stem,
                    "path":  rel,
                    "title": p.stem.replace("-", " ").title(),
                    "layer": "curated",
                })

    if not candidates:
        return {"error": f"no .ai-context/ file matching '{name}' — run `scope doc list`"}
    if len(candidates) > 1:
        ids = [c["id"] for c in candidates]
        return {"error": f"ambiguous: '{name}' matches {ids} — be more specific"}

    hit = candidates[0]
    file_path = repo / hit["path"]
    if not file_path.exists():
        return {"error": f"file on record but not found on disk: {file_path}"}

    content = file_path.read_text(encoding="utf-8")
    return {
        "id":      hit["id"],
        "path":    hit["path"],
        "title":   hit.get("title", hit["id"]),
        "layer":   hit.get("layer", "generated"),
        "content": content,
        "chars":   len(content),
    }


def _doc_search(repo: Path, query: str, *, layer: str = "all",
                context_lines: int = 2) -> dict:
    """Search all .ai-context/ files for a keyword (case-insensitive).

    Returns a list of matches: {file_id, path, layer, matches[]}.
    Each match has {line_no, line, context_before[], context_after[]}.
    """
    ai_ctx = repo / ".ai-context"
    if not ai_ctx.exists():
        return {"error": "no .ai-context/ found — run `scope doc ingest` first"}

    import re as _re
    pattern = _re.compile(_re.escape(query), _re.IGNORECASE)
    results: list[dict] = []

    def _search_dir(directory: Path, lyr: str) -> None:
        if not directory.exists():
            return
        for p in sorted(directory.glob("*.md")):
            rel = str(p.relative_to(repo)).replace("\\", "/")
            try:
                lines = p.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            matches: list[dict] = []
            for i, line in enumerate(lines):
                if pattern.search(line):
                    before = lines[max(0, i - context_lines): i]
                    after  = lines[i + 1: i + 1 + context_lines]
                    matches.append({
                        "line_no":        i + 1,
                        "line":           line,
                        "context_before": before,
                        "context_after":  after,
                    })
            if matches:
                results.append({
                    "file_id": p.stem,
                    "path":    rel,
                    "layer":   lyr,
                    "matches": matches,
                    "match_count": len(matches),
                })

    if layer in ("generated", "all"):
        _search_dir(ai_ctx / "generated", "generated")
    if layer in ("curated", "all"):
        _search_dir(ai_ctx / "curated", "curated")

    total_matches = sum(r["match_count"] for r in results)
    return {
        "query":         query,
        "files_searched": (
            len(list((ai_ctx / "generated").glob("*.md")) if (ai_ctx / "generated").exists() else [])
            + len(list((ai_ctx / "curated").glob("*.md")) if (ai_ctx / "curated").exists() else [])
        ),
        "files_with_matches": len(results),
        "total_matches": total_matches,
        "results":       results,
    }


def _fmt_doc_search(r: dict) -> None:
    if "error" in r:
        print(r["error"]); return
    print(f"search: '{r['query']}'  —  {r['total_matches']} match(es) "
          f"in {r['files_with_matches']}/{r['files_searched']} files")
    for res in r["results"]:
        print(f"\n{'─'*60}")
        print(f"  [{res['layer']}] {res['path']}  ({res['match_count']} match(es))")
        print(f"{'─'*60}")
        for m in res["matches"]:
            for ctx_line in m["context_before"]:
                print(f"  {m['line_no'] - len(m['context_before'])+ m['context_before'].index(ctx_line)}│ {ctx_line}")
            print(f"→ {m['line_no']}│ {m['line']}")
            for ctx_line in m["context_after"]:
                print(f"  {m['line_no'] + 1 + m['context_after'].index(ctx_line)}│ {ctx_line}")
    if r["total_matches"] == 0:
        print(f"  (no matches — try a different query or run `scope doc list`)")


def _fmt_doc_fetch(r: dict) -> None:
    if "error" in r:
        print(r["error"]); return
    print(f"# {r['title']}  [{r['layer']}]  ({r['chars']} chars)")
    print(f"# path: {r['path']}")
    print()
    print(r["content"])


def _doc_stats(repo: Path) -> dict:
    """Return character/token counts for every .ai-context/ file.

    Token estimate: 1 token ≈ 4 characters (conservative GPT-style heuristic).
    """
    ai_ctx = repo / ".ai-context"
    if not ai_ctx.exists():
        return {"error": "no .ai-context/ found — run `scope doc ingest` first"}

    def _scan_dir(directory: Path, layer: str) -> list[dict]:
        files: list[dict] = []
        if not directory.exists():
            return files
        for p in sorted(directory.glob("*.md")):
            rel = str(p.relative_to(repo)).replace("\\", "/")
            try:
                chars = len(p.read_text(encoding="utf-8"))
            except OSError:
                chars = 0
            files.append({
                "id":     p.stem,
                "path":   rel,
                "layer":  layer,
                "chars":  chars,
                "tokens": chars // 4,   # ~4 chars per token
            })
        return files

    generated = _scan_dir(ai_ctx / "generated", "generated")
    curated   = _scan_dir(ai_ctx / "curated",   "curated")
    all_files = generated + curated
    total_chars  = sum(f["chars"]  for f in all_files)
    total_tokens = sum(f["tokens"] for f in all_files)

    return {
        "generated":    generated,
        "curated":      curated,
        "total_files":  len(all_files),
        "total_chars":  total_chars,
        "total_tokens": total_tokens,
    }


def _fmt_doc_stats(r: dict) -> None:
    if "error" in r:
        print(r["error"]); return

    def _bar(n: int, max_n: int, width: int = 20) -> str:
        filled = int(n / max_n * width) if max_n else 0
        return "█" * filled + "░" * (width - filled)

    all_files = r.get("generated", []) + r.get("curated", [])
    max_tokens = max((f["tokens"] for f in all_files), default=1)

    print(f"AI context file stats — {r['total_files']} files  "
          f"{r['total_chars']:,} chars  ~{r['total_tokens']:,} tokens")
    print()

    for layer, key in [("generated/", "generated"), ("curated/", "curated")]:
        files = r.get(key, [])
        if not files:
            continue
        print(f"  {layer}")
        for f in files:
            bar = _bar(f["tokens"], max_tokens)
            print(f"    {f['id']:<40} {f['chars']:>7,} chars  "
                  f"~{f['tokens']:>5,} tok  {bar}")
        print()

    print(f"  total: {r['total_chars']:,} chars  ~{r['total_tokens']:,} tokens")

    # Context budget hints
    token_budget = r["total_tokens"]
    if token_budget < 8_000:
        hint = "fits easily in a single 8k context window"
    elif token_budget < 32_000:
        hint = "fits in a 32k context window"
    elif token_budget < 128_000:
        hint = "fits in a 128k context window"
    else:
        hint = "⚠ exceeds 128k tokens — consider splitting or using scope doc fetch selectively"
    print(f"  budget: {hint}")


def _doc_export(
    repo: Path,
    *,
    layer: str = "all",
    include_header: bool = True,
) -> dict:
    """Concatenate all .ai-context/ files into a single text blob.

    Returns:
        {content, total_files, total_chars, total_tokens, source, files[]}
    """
    ai_ctx = repo / ".ai-context"
    if not ai_ctx.exists():
        return {"error": "no .ai-context/ found — run `scope doc ingest` first"}

    # Discover source doc name from index.json if available
    index_path = ai_ctx / "generated" / "index.json"
    source = "unknown"
    if index_path.exists():
        try:
            source = json.loads(index_path.read_text(encoding="utf-8")).get("source", "unknown")
        except Exception:  # noqa: BLE001
            pass

    dirs: list[tuple[Path, str]] = []
    if layer in ("generated", "all"):
        dirs.append((ai_ctx / "generated", "generated"))
    if layer in ("curated", "all"):
        dirs.append((ai_ctx / "curated", "curated"))

    sections: list[dict] = []
    for directory, lyr in dirs:
        if not directory.exists():
            continue
        for p in sorted(directory.glob("*.md")):
            try:
                text = p.read_text(encoding="utf-8")
            except OSError:
                continue
            rel = str(p.relative_to(repo)).replace("\\", "/")
            sections.append({
                "id":    p.stem,
                "path":  rel,
                "layer": lyr,
                "text":  text,
                "chars": len(text),
            })

    if not sections:
        return {"error": "no .ai-context/ files found — run `scope doc ingest` first"}

    import time as _time
    total_chars = sum(s["chars"] for s in sections)

    # Build the combined text
    parts: list[str] = []
    if include_header:
        parts.append(
            f"<!-- scope-intel-export: {source} | "
            f"{_time.strftime('%Y-%m-%d')} | "
            f"{len(sections)} files | "
            f"~{total_chars // 4:,} tokens -->\n"
        )
    for s in sections:
        parts.append(f"\n\n<!-- === {s['path']} [{s['layer']}] === -->\n\n")
        parts.append(s["text"])

    content = "".join(parts)
    return {
        "content":      content,
        "source":       source,
        "total_files":  len(sections),
        "total_chars":  len(content),
        "total_tokens": len(content) // 4,
        "files": [{"id": s["id"], "path": s["path"], "layer": s["layer"],
                   "chars": s["chars"]} for s in sections],
    }


def cmd_doc(args) -> int:
    if args.doc_cmd == "ingest":
        repo = _resolve_repo(args.repo)
        if _not_indexed(repo):
            return 2
        result = ingest_document(
            repo,
            Path(args.doc),
            overwrite=args.overwrite,
            dry_run=args.dry_run,
            update_claude_md=not args.no_claude_md,
            mode=args.mode,
            ollama_model=args.ollama_model,
            ollama_url=args.ollama_url,
            second_pass=args.second_pass,
            if_changed=getattr(args, "if_changed", False),
        )
        _emit(result, args.json, formatter=_fmt_ingest)
        return 0 if "error" not in result else 2

    if args.doc_cmd == "rebuild":
        repo = _resolve_repo(args.repo)
        if _not_indexed(repo):
            return 2
        # Step 1: clear generated/ (preserve curated)
        gen_dir = repo / ".ai-context" / "generated"
        cleared = 0
        if gen_dir.exists():
            for p in list(gen_dir.iterdir()):
                p.unlink()
                cleared += 1
            try:
                gen_dir.rmdir()
            except OSError:
                pass
        if not args.json:
            print(f"cleared {cleared} file(s) from .ai-context/generated/")
        # Step 2: re-ingest
        result = ingest_document(
            repo,
            Path(args.doc),
            overwrite=True,
            dry_run=False,
            update_claude_md=not args.no_claude_md,
            mode=args.mode,
            ollama_model=args.ollama_model,
            ollama_url=args.ollama_url,
            second_pass=args.second_pass,
        )
        result["rebuild_cleared"] = cleared
        _emit(result, args.json, formatter=_fmt_ingest)
        return 0 if "error" not in result else 2

    if args.doc_cmd == "export":
        repo = _resolve_repo(args.repo)
        result = _doc_export(repo, layer=args.layer, include_header=not args.no_header)
        if "error" in result:
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(result["error"], file=sys.stderr)
            return 2
        if args.json:
            # JSON mode: return metadata + content
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0
        content = result["content"]
        if args.output == "-":
            print(content)
        else:
            out = Path(args.output)
            out.write_text(content, encoding="utf-8")
            print(f"exported {result['total_files']} files  "
                  f"{result['total_chars']:,} chars  "
                  f"~{result['total_tokens']:,} tokens  → {out}",
                  file=sys.stderr)
        return 0

    if args.doc_cmd == "stats":
        repo = _resolve_repo(args.repo)
        result = _doc_stats(repo)
        _emit(result, args.json, formatter=_fmt_doc_stats)
        return 0 if "error" not in result else 2

    if args.doc_cmd == "list":
        repo = _resolve_repo(args.repo)
        result = _doc_list(repo)
        _emit(result, args.json, formatter=_fmt_doc_list)
        return 0 if "error" not in result else 2

    if args.doc_cmd == "fetch":
        repo = _resolve_repo(args.repo)
        result = _doc_fetch(repo, args.name)
        _emit(result, args.json, formatter=_fmt_doc_fetch)
        return 0 if "error" not in result else 2

    if args.doc_cmd == "search":
        repo = _resolve_repo(args.repo)
        result = _doc_search(repo, args.query,
                             layer=args.layer, context_lines=args.context)
        _emit(result, args.json, formatter=_fmt_doc_search)
        return 0 if "error" not in result else 2

    if args.doc_cmd == "clear":
        repo = _resolve_repo(args.repo)
        ai_ctx = repo / ".ai-context"
        if not ai_ctx.exists():
            print("nothing to clear — .ai-context/ does not exist")
            return 0

        removed: list[str] = []
        skipped: list[str] = []

        # Always clear generated/
        gen_dir = ai_ctx / "generated"
        if gen_dir.exists():
            for p in sorted(gen_dir.iterdir()):
                rel = str(p.relative_to(repo)).replace("\\", "/")
                if args.dry_run:
                    skipped.append(rel)
                else:
                    p.unlink()
                    removed.append(rel)
            if not args.dry_run:
                gen_dir.rmdir()  # remove dir only if empty

        # Optionally clear curated/
        if args.clear_all:
            cur_dir = ai_ctx / "curated"
            if cur_dir.exists():
                for p in sorted(cur_dir.iterdir()):
                    rel = str(p.relative_to(repo)).replace("\\", "/")
                    if args.dry_run:
                        skipped.append(rel)
                    else:
                        p.unlink()
                        removed.append(rel)
                if not args.dry_run:
                    cur_dir.rmdir()

        # Remove .ai-context/ dir itself if now empty
        if not args.dry_run:
            try:
                ai_ctx.rmdir()  # only succeeds if empty
            except OSError:
                pass  # not empty — curated/ still there, or other files

        if args.dry_run:
            print(f"[dry run] would remove {len(skipped)} files:")
            for f in skipped:
                print(f"  {f}")
        else:
            print(f"removed {len(removed)} files from .ai-context/")
            for f in removed:
                print(f"  {f}")
            if not args.clear_all:
                print("curated/ preserved — use --all to also remove curated files")
        return 0

    print(f"unknown doc subcommand: {args.doc_cmd}", file=sys.stderr)
    return 2


def cmd_mem(args) -> int:
    repo = _resolve_repo(args.repo)
    mc = args.mem_cmd

    if mc == "add":
        result = add_memory(
            repo,
            kind=args.kind,
            note=args.note,
            files=args.files,
            features=args.features,
            symbols=args.symbols,
            tags=args.tags,
            author=args.author,
            resolved=args.resolved,
            confidence=args.confidence,
            steps=args.steps or None,
        )
        if "error" in result:
            print(result["error"], file=sys.stderr); return 2
        print(f"recorded: {result['id']}  [{result['type']}]  {result['note'][:60]}")
        return 0

    if mc == "fetch":
        if not (args.feature or args.file or args.symbol):
            print("error: provide at least one of --feature, --file, --symbol",
                  file=sys.stderr); return 2
        result = fetch_relevant(
            repo,
            feature=args.feature,
            file=args.file,
            symbol=args.symbol,
            kind=args.kind,
            include_resolved=args.include_resolved,
            limit=args.limit,
        )
        _emit(result, args.json, formatter=_fmt_mem_fetch)
        return 0

    if mc == "list":
        result = list_memories(
            repo,
            kind=args.kind,
            tag=args.tag,
            include_resolved=not args.open_only,
        )
        _emit(result, args.json, formatter=_fmt_mem_list)
        return 0

    if mc == "resolve":
        result = resolve_memory(repo, args.id)
        if "error" in result:
            print(result["error"], file=sys.stderr); return 2
        print(f"resolved: {result['resolved']}")
        return 0

    if mc == "churn":
        result = compute_churn(repo, days=args.days)
        _emit(result, args.json, formatter=_fmt_churn)
        return 0

    if mc == "auto-capture":
        result = auto_capture_from_git(
            repo, days=args.days, dry_run=args.dry_run
        )
        _emit(result, args.json, formatter=_fmt_auto_capture)
        return 0

    if mc == "decay":
        result = decay_confidence(
            repo,
            half_life_days=args.half_life,
            floor=args.floor,
            dry_run=args.dry_run,
        )
        _emit(result, args.json, formatter=_fmt_decay)
        return 0

    if mc == "search":
        result = search_memories(
            repo,
            args.query,
            kind=args.kind,
            limit=args.limit,
        )
        _emit(result, args.json, formatter=_fmt_search)
        return 0

    if mc == "export":
        result = export_memories(repo, Path(args.output))
        if "error" in result:
            print(result["error"], file=sys.stderr); return 2
        print(f"exported {result['exported']} memories -> {result['output']}")
        return 0

    if mc == "import":
        result = import_memories(repo, Path(args.file), merge=not args.replace)
        if "error" in result:
            print(result["error"], file=sys.stderr); return 2
        _emit(result, args.json, formatter=lambda s: print(
            f"imported {s['imported']} memories  skipped {s['skipped']} duplicates"
            + (" [replaced]" if s.get("replaced") else "")
        ))
        return 0

    if mc == "conflicts":
        result = detect_conflicts(repo, include_resolved=args.include_resolved)
        _emit(result, args.json, formatter=_fmt_conflicts)
        return 0

    print(f"unknown mem subcommand: {mc}", file=sys.stderr)
    return 2


# ---------------------------------------------------------------------------

HANDLERS = {
    "init":        cmd_init,
    "index":       cmd_index,
    "update":      cmd_update,
    "summary":     cmd_summary,
    "features":    cmd_features,
    "feature":     cmd_feature,
    "impacted":    cmd_impacted,
    "tests":       cmd_tests,
    "symbol":      cmd_symbol,
    "callers":     cmd_callers,
    "callees":     cmd_callees,
    "touchpoints": cmd_touchpoints,
    "diff":        cmd_diff,
    "report":         cmd_report,
    "global-report":  cmd_global_report,
    "serve":          cmd_serve,
    "doc":            cmd_doc,
    "mem":            cmd_mem,
}


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return HANDLERS[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
