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
    compute_churn,
    fetch_relevant,
    list_memories,
    memory_stats,
    resolve_memory,
)
from .core.reporter import format_html, format_terminal
from .core.summarizer import feature_one_liner
from .core.tracker import compute_savings_summary, log_query

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

    # serve — MCP stdio server
    sub.add_parser("serve", help="Start MCP JSON-RPC 2.0 stdio server.")

    # mem — MemPalace long-term memory
    p_mem = sub.add_parser("mem", help="MemPalace: long-term knowledge store.")
    mem_sub = p_mem.add_subparsers(dest="mem_cmd", required=True)

    # mem add
    p_madd = mem_sub.add_parser("add", help="Record a memory (bug, decision, failure, etc.)")
    p_madd.add_argument("--repo", default=".")
    p_madd.add_argument("--type", dest="kind", default="note",
                        choices=["bug", "decision", "failure", "ownership", "note", "fix"],
                        help="Memory type (default: note).")
    p_madd.add_argument("--note", required=True, help="The memory text.")
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

    # mem fetch — uses Phase 1-3 scope engine internally
    p_mfetch = mem_sub.add_parser(
        "fetch", help="Fetch memories relevant to a feature/file/symbol.")
    p_mfetch.add_argument("--repo", default=".")
    p_mfetch.add_argument("--feature", help="Feature id or alias.")
    p_mfetch.add_argument("--file", help="Repo-relative file path.")
    p_mfetch.add_argument("--symbol", help="Symbol name.")
    p_mfetch.add_argument("--type", dest="kind",
                          choices=["bug", "decision", "failure", "ownership", "note", "fix"],
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
                         choices=["bug", "decision", "failure", "ownership", "note", "fix"])
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


def _fmt_mem_entry(e: dict) -> None:
    status = "[resolved]" if e.get("resolved") else "[open]"
    tags = f"  tags: {', '.join(e['tags'])}" if e.get("tags") else ""
    scope = e.get("scope", {})
    files = scope.get("files", [])
    feats = scope.get("features", [])
    syms = scope.get("symbols", [])
    print(f"  {e['id']}  [{e['type']}] {status}  {e.get('ts','')}")
    print(f"  {e['note']}")
    if files:
        print(f"  files: {', '.join(files)}")
    if feats:
        print(f"  features: {', '.join(feats)}")
    if syms:
        print(f"  symbols: {', '.join(syms)}")
    if tags:
        print(tags)
    print()


def _fmt_mem_fetch(s: dict) -> None:
    if "error" in s:
        print(s["error"]); return
    rscope = s.get("resolved_scope", {})
    print(f"resolved scope: files={len(rscope.get('files',[]))}  "
          f"features={len(rscope.get('features',[]))}  "
          f"symbols={len(rscope.get('symbols',[]))}")
    if rscope.get("features"):
        print(f"  features: {', '.join(sorted(rscope['features']))}")
    if rscope.get("files"):
        print(f"  files: {', '.join(sorted(rscope['files'])[:5])}"
              + (f"  +{len(rscope['files'])-5} more" if len(rscope['files']) > 5 else ""))
    if s.get("warnings"):
        for w in s["warnings"]:
            print(f"  warning: {w}")
    matches = s.get("matches", [])
    print(f"\nmatched {len(matches)} memor{'y' if len(matches)==1 else 'ies'}:")
    print("-" * 60)
    if not matches:
        print("  (none — add memories with: scope mem add --note \"...\")")
        return
    for e in matches:
        _fmt_mem_entry(e)


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


def cmd_serve(_args) -> int:
    from .mcp_server import serve
    serve()
    return 0


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
    "report":      cmd_report,
    "serve":       cmd_serve,
    "mem":         cmd_mem,
}


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return HANDLERS[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
