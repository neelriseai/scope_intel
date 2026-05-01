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
from .core.federation import (
    federation_add,
    federation_link,
    federation_list,
    federation_remove,
    federated_fetch,
)
from .core.mempalace import (
    add_memory,
    auto_capture_from_git,
    capture_memory,
    CAPTURE_SIGNALS,
    compute_churn,
    decay_confidence,
    detect_conflicts,
    export_memories,
    fetch_relevant,
    import_memories,
    list_memories,
    memory_stats,
    prune_memories,
    resolve_memory,
    search_memories,
    touch_memory,
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

    # graph — Mermaid / DOT diagram of classes, deps, or call chains
    p_graph = sub.add_parser("graph", help="Generate Mermaid or DOT diagram from the index.")
    _add_common(p_graph)
    p_graph.add_argument("query", help="Feature id, file path, or symbol name.")
    p_graph.add_argument(
        "--target", choices=["feature", "file", "symbol"], default="feature",
        help="What 'query' refers to (default: feature).",
    )
    p_graph.add_argument(
        "--kind", choices=["class", "deps", "calls"], default="class",
        help=(
            "class = classDiagram (classes + methods + inheritance);  "
            "deps  = import dependency graph (file → file);  "
            "calls = call graph (callers → symbol → callees)."
        ),
    )
    p_graph.add_argument(
        "--format", choices=["mermaid", "dot"], default="mermaid",
        help="Output format (default: mermaid).",
    )
    p_graph.add_argument(
        "--max-nodes", type=int, default=60, metavar="N",
        help="Cap diagram at N nodes for readability (default: 60).",
    )
    p_graph.add_argument(
        "--output", metavar="FILE",
        help="Write diagram to FILE instead of stdout.",
    )

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
        "--ollama-model", default="qwen2.5:7b", metavar="MODEL",
        help="Ollama model to use in --mode llm (default: qwen2.5:7b).",
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
    p_ingest.add_argument(
        "--verify", action="store_true",
        help="Run `scope doc check` immediately after ingest and append health report to result.",
    )
    p_ingest.add_argument("--json", action="store_true", help="Emit raw JSON result.")

    # doc list — show what's been generated
    p_list = doc_sub.add_parser(
        "list",
        help="List all .ai-context/ files generated for this repo.",
    )
    p_list.add_argument("--repo", default=".", help="Target repo root (default: cwd).")
    p_list.add_argument("--pinned", action="store_true",
                        help="Show only pinned files.")
    p_list.add_argument("--tag", metavar="TAG",
                        help="Show only files with this tag.")
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
    p_fetch.add_argument(
        "--section", metavar="HEADING",
        help=(
            "Extract only the content of a specific heading section "
            "(partial match, case-insensitive). E.g. --section 'roadmap'."
        ),
    )
    p_fetch.add_argument("--repo", default=".", help="Target repo root (default: cwd).")
    p_fetch.add_argument("--json", action="store_true", help="Emit raw JSON result.")

    # doc section — extract a single heading section from a file (shorthand)
    p_sect = doc_sub.add_parser(
        "section",
        help=(
            "Extract a specific heading section from a .ai-context/ file. "
            "Equivalent to `scope doc fetch <file> --section <heading>`."
        ),
    )
    p_sect.add_argument(
        "name",
        help="File id or partial name.",
    )
    p_sect.add_argument(
        "heading",
        help="Heading text to match (partial, case-insensitive).",
    )
    p_sect.add_argument("--repo", default=".", help="Target repo root (default: cwd).")
    p_sect.add_argument("--json", action="store_true", help="Emit raw JSON result.")

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

    # doc fetch-for — unified context for a feature (doc + memories + scope)
    p_fetchfor = doc_sub.add_parser(
        "fetch-for",
        help=(
            "Retrieve all design doc context, memories, and scope info relevant to a feature. "
            "One-shot context bundle for Claude."
        ),
    )
    p_fetchfor.add_argument(
        "feature",
        help="Feature id or alias (e.g. 'memory-layer', 'rag', 'validation-engine').",
    )
    p_fetchfor.add_argument("--repo", default=".", help="Target repo root (default: cwd).")
    p_fetchfor.add_argument(
        "--no-memories", action="store_true",
        help="Skip memory fetch (faster if MemPalace is large).",
    )
    p_fetchfor.add_argument(
        "--no-scope", action="store_true",
        help="Skip scope index lookup (feature file list, symbols).",
    )
    p_fetchfor.add_argument("--json", action="store_true", help="Emit raw JSON result.")

    # doc pin / unpin — protect a generated file from being overwritten by ingest/rebuild
    p_pin = doc_sub.add_parser(
        "pin",
        help=(
            "Pin a generated .ai-context/ file so it is never overwritten by "
            "`scope doc ingest --overwrite` or `scope doc rebuild`."
        ),
    )
    p_pin.add_argument(
        "file_id",
        help="File id or partial name (e.g. '001', 'roadmap', 'constraints').",
    )
    p_pin.add_argument("--repo", default=".", help="Target repo root (default: cwd).")
    p_pin.add_argument("--json", action="store_true", help="Emit raw JSON result.")

    p_unpin = doc_sub.add_parser(
        "unpin",
        help="Remove a pin from a .ai-context/ file, allowing it to be overwritten again.",
    )
    p_unpin.add_argument(
        "file_id",
        help="File id or partial name to unpin.",
    )
    p_unpin.add_argument("--repo", default=".", help="Target repo root (default: cwd).")
    p_unpin.add_argument("--json", action="store_true", help="Emit raw JSON result.")

    # doc annotate — add/view human notes on a generated file's index entry
    p_ann = doc_sub.add_parser(
        "annotate",
        help=(
            "Add or view human annotations on a .ai-context/ file. "
            "Use annotations to leave 'last reviewed', 'needs update' notes "
            "without touching the file content."
        ),
    )
    p_ann.add_argument(
        "file_id",
        help="File id or partial name (e.g. 'roadmap', '003', 'constraints').",
    )
    p_ann.add_argument(
        "--add", dest="add_note", metavar="NOTE",
        help="Annotation text to record.",
    )
    p_ann.add_argument(
        "--author", default="", metavar="NAME",
        help="Author name or handle to attach to the annotation.",
    )
    p_ann.add_argument(
        "--clear", action="store_true",
        help="Remove all existing annotations from this file.",
    )
    p_ann.add_argument("--repo", default=".", help="Target repo root (default: cwd).")
    p_ann.add_argument("--json", action="store_true", help="Emit raw JSON result.")

    # doc check — health validation
    p_check = doc_sub.add_parser(
        "check",
        help="Validate .ai-context/ structure and flag issues (missing files, TODO placeholders, thin content).",
    )
    p_check.add_argument("--repo", default=".", help="Target repo root (default: cwd).")
    p_check.add_argument("--json", action="store_true", help="Emit raw JSON result.")

    # doc ingest-batch — ingest all docs in a directory
    p_ibatch = doc_sub.add_parser(
        "ingest-batch",
        help="Ingest all design docs (PDF/DOCX/MD/TXT) in a directory.",
    )
    p_ibatch.add_argument("directory", help="Directory containing design documents.")
    p_ibatch.add_argument("--repo", default=".", help="Target repo root (default: cwd).")
    p_ibatch.add_argument(
        "--glob", default="*.pdf,*.docx,*.md,*.txt", metavar="PATTERNS",
        help=(
            "Comma-separated glob patterns to match (default: *.pdf,*.docx,*.md,*.txt). "
            "Example: --glob '*.pdf,*.docx'"
        ),
    )
    p_ibatch.add_argument(
        "--overwrite", action="store_true",
        help="Overwrite files that already exist (default: skip existing).",
    )
    p_ibatch.add_argument(
        "--if-changed", action="store_true", dest="if_changed",
        help="Skip individual files whose hash matches the stored hash.",
    )
    p_ibatch.add_argument(
        "--mode", choices=["python", "llm"], default="python",
        help="Extraction mode (default: python).",
    )
    p_ibatch.add_argument("--ollama-model", default="qwen2.5:7b", metavar="MODEL")
    p_ibatch.add_argument("--ollama-url", default="http://localhost:11434", metavar="URL")
    p_ibatch.add_argument("--no-claude-md", action="store_true")
    p_ibatch.add_argument(
        "--stop-on-error", action="store_true",
        help="Abort the batch on the first ingest error (default: log and continue).",
    )
    p_ibatch.add_argument("--json", action="store_true", help="Emit raw JSON result.")

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
    p_rebuild.add_argument("--ollama-model", default="qwen2.5:7b", metavar="MODEL")
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
    p_export.add_argument(
        "--tag", default=None, metavar="TAG",
        help="Only include files carrying this tag (set via `scope doc tag`).",
    )
    p_export.add_argument("--json", action="store_true", help="Emit raw JSON result.")

    # doc validate — check .ai-context/ integrity
    p_validate = doc_sub.add_parser(
        "validate",
        help="Check .ai-context/ integrity: orphaned entries, untracked files, hash drift.",
    )
    p_validate.add_argument("--repo", default=".", help="Target repo root (default: cwd).")
    p_validate.add_argument("--json", action="store_true", help="Emit raw JSON result.")

    # doc rename — rename a curated .ai-context/ file
    p_rename = doc_sub.add_parser(
        "rename",
        help="Rename a curated .ai-context/ file and update annotations references.",
    )
    p_rename.add_argument("old", help="Current name or partial id of the curated file.")
    p_rename.add_argument("new", help="New name (without extension).")
    p_rename.add_argument("--repo", default=".", help="Target repo root (default: cwd).")
    p_rename.add_argument("--json", action="store_true", help="Emit raw JSON result.")

    # doc copy — duplicate a curated file under a new name
    p_copy = doc_sub.add_parser(
        "copy",
        help="Duplicate a curated .ai-context/ file under a new name (annotations not copied).",
    )
    p_copy.add_argument("source", help="Source name or partial id of the curated file to copy.")
    p_copy.add_argument("new", help="New file name (without extension).")
    p_copy.add_argument("--repo", default=".", help="Target repo root (default: cwd).")
    p_copy.add_argument("--json", action="store_true", help="Emit raw JSON result.")

    # doc ingest-watch — poll a directory and auto-ingest changed files
    p_iwatch = doc_sub.add_parser(
        "ingest-watch",
        help=(
            "Poll a directory for .md/.txt/.rst changes and auto-ingest them. "
            "Uses mtime + source-hash dedup. Pass --once for a single sweep."
        ),
    )
    p_iwatch.add_argument("directory", help="Directory to watch.")
    p_iwatch.add_argument(
        "--glob", default="*.md,*.txt,*.rst",
        help="Comma-separated patterns to match (default: *.md,*.txt,*.rst).",
    )
    p_iwatch.add_argument(
        "--interval", type=float, default=2.0,
        help="Seconds between sweeps (default: 2.0). Ignored when --once is set.",
    )
    p_iwatch.add_argument(
        "--once", action="store_true",
        help="Run a single sweep then exit (useful for cron / CI).",
    )
    p_iwatch.add_argument(
        "--mode", choices=["python", "llm"], default="python",
        help="Extraction mode (default: python).",
    )
    p_iwatch.add_argument(
        "--no-overwrite", action="store_true",
        help="Pass overwrite=False to ingest (skip files that already produced output).",
    )
    p_iwatch.add_argument("--dry-run", action="store_true", help="Don't write files.")
    p_iwatch.add_argument("--repo", default=".", help="Target repo root (default: cwd).")
    p_iwatch.add_argument("--json", action="store_true", help="Emit raw JSON per sweep.")

    # doc touch — one-shot 'needs review' annotation wrapper
    p_touch = doc_sub.add_parser(
        "touch",
        help="Flag a .ai-context/ file as needing review (shorthand for `annotate --add 'needs review'`).",
    )
    p_touch.add_argument("name", help="File id or partial name to flag.")
    p_touch.add_argument(
        "--reason", default="",
        help="Optional reason appended to the annotation (e.g. 'stale schema').",
    )
    p_touch.add_argument("--author", default="", help="Author name to record on the annotation.")
    p_touch.add_argument("--repo", default=".", help="Target repo root (default: cwd).")
    p_touch.add_argument("--json", action="store_true", help="Emit raw JSON result.")

    # doc snapshot — named point-in-time checkpoints of .ai-context/ file hashes
    p_snap = doc_sub.add_parser(
        "snapshot",
        help=(
            "Manage named snapshots of .ai-context/ file hashes. "
            "Snapshots let you track which files changed between design iterations."
        ),
    )
    snap_sub = p_snap.add_subparsers(dest="snap_cmd", required=True)

    p_snap_save = snap_sub.add_parser("save", help="Save current hashes as a named snapshot.")
    p_snap_save.add_argument("name", help="Snapshot name (e.g. 'v1', 'after-review', 'pre-rebuild').")
    p_snap_save.add_argument("--repo", default=".")
    p_snap_save.add_argument("--json", action="store_true")

    p_snap_list = snap_sub.add_parser("list", help="List all saved snapshots.")
    p_snap_list.add_argument("--repo", default=".")
    p_snap_list.add_argument("--json", action="store_true")

    p_snap_del = snap_sub.add_parser("delete", help="Delete a snapshot by name.")
    p_snap_del.add_argument("name", help="Snapshot name to delete.")
    p_snap_del.add_argument("--repo", default=".")
    p_snap_del.add_argument("--json", action="store_true")

    # doc outline — show the heading hierarchy of a generated file
    p_outline = doc_sub.add_parser(
        "outline",
        help=(
            "Show the heading hierarchy of a .ai-context/ file. "
            "Useful for understanding what a long generated doc covers without printing everything."
        ),
    )
    p_outline.add_argument(
        "name",
        help="File id or partial name (e.g. 'roadmap', '001', 'constraints').",
    )
    p_outline.add_argument("--repo", default=".", help="Target repo root (default: cwd).")
    p_outline.add_argument("--json", action="store_true", help="Emit raw JSON result.")

    # doc tag — attach free-form labels to a .ai-context/ file entry
    p_tag = doc_sub.add_parser(
        "tag",
        help=(
            "Attach or remove free-form tags on a .ai-context/ file. "
            "Tags let you group files (e.g. 'api', 'auth', 'reviewed') for filtered listing."
        ),
    )
    p_tag.add_argument(
        "file_id",
        help="File id or partial name.",
    )
    p_tag.add_argument(
        "--add", dest="add_tags", nargs="+", metavar="TAG",
        help="Tag(s) to add.",
    )
    p_tag.add_argument(
        "--remove", dest="remove_tags", nargs="+", metavar="TAG",
        help="Tag(s) to remove.",
    )
    p_tag.add_argument(
        "--clear", action="store_true",
        help="Remove all tags from this file.",
    )
    p_tag.add_argument("--repo", default=".", help="Target repo root (default: cwd).")
    p_tag.add_argument("--json", action="store_true", help="Emit raw JSON result.")

    # doc report — full markdown health dashboard of .ai-context/ system
    p_drep = doc_sub.add_parser(
        "report",
        help=(
            "Generate a markdown dashboard summarising the entire .ai-context/ state: "
            "file inventory, pin/annotation status, snapshots, token budget, and health."
        ),
    )
    p_drep.add_argument("--repo", default=".", help="Target repo root (default: cwd).")
    p_drep.add_argument(
        "--output", default="-", metavar="FILE",
        help="Output file path. Use '-' for stdout (default: -).",
    )
    p_drep.add_argument("--json", action="store_true", help="Emit raw JSON result.")

    # doc diff — show files manually edited since last ingest
    p_ddiff = doc_sub.add_parser(
        "diff",
        help=(
            "Show which .ai-context/ files have been manually edited since the last "
            "ingest run (or since a named snapshot with --since)."
        ),
    )
    p_ddiff.add_argument("--repo", default=".", help="Target repo root (default: cwd).")
    p_ddiff.add_argument(
        "--since", metavar="SNAPSHOT",
        help="Diff against a named snapshot (created with `scope doc snapshot save <name>`).",
    )
    p_ddiff.add_argument("--json", action="store_true", help="Emit raw JSON result.")

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
    p_search.add_argument(
        "--regex", action="store_true",
        help="Treat query as a regex pattern instead of a literal string.",
    )
    p_search.add_argument(
        "--tag", metavar="TAG",
        help="Restrict search to files with this tag.",
    )
    p_search.add_argument("--json", action="store_true", help="Emit raw JSON result.")

    # doc llm-probe — check whether Ollama can classify local file content
    p_llm_probe = doc_sub.add_parser(
        "llm-probe",
        help=(
            "Probe Ollama: verify it can classify a local file's content. "
            "Answers whether file-path passing works vs. content passing. "
            "Requires Ollama running with qwen2.5:7b (or --model) pulled."
        ),
    )
    p_llm_probe.add_argument("file", help="Local file path to read and classify.")
    p_llm_probe.add_argument(
        "--model", default="qwen2.5:7b",
        help="Ollama model to test against (default: qwen2.5:7b).",
    )
    p_llm_probe.add_argument(
        "--url", default="http://localhost:11434",
        help="Ollama server URL (default: http://localhost:11434).",
    )
    p_llm_probe.add_argument("--json", action="store_true", help="Emit raw JSON result.")

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
    p_madd.add_argument(
        "--half-life", type=int, default=None, dest="half_life_days",
        metavar="DAYS",
        help=("Days for the effective_confidence to halve (semantic only). "
              "Overrides config.semantic_half_life (default 90)."),
    )
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

    # mem federation  (Phase 6.3) — cross-repo memory links
    p_mfed = mem_sub.add_parser(
        "federation",
        help="Manage cross-repo memory federation (Phase 6.3).",
    )
    fed_sub = p_mfed.add_subparsers(dest="fed_cmd", required=True)

    p_fed_add = fed_sub.add_parser("add", help="Register a repo in the federation.")
    p_fed_add.add_argument("path", help="Absolute path to the repo root.")
    p_fed_add.add_argument("--alias", required=True, help="Short alias (e.g. 'payments').")
    p_fed_add.add_argument("--json", action="store_true")

    p_fed_rm = fed_sub.add_parser("remove", help="Remove a repo and its links.")
    p_fed_rm.add_argument("alias", help="Alias to remove.")
    p_fed_rm.add_argument("--json", action="store_true")

    p_fed_link = fed_sub.add_parser("link",
                                    help="Add a directional link: from pulls from to.")
    p_fed_link.add_argument("--from", dest="from_alias", required=True,
                            help="Alias of the repo that will receive satellite memories.")
    p_fed_link.add_argument("--to",   dest="to_alias",   required=True,
                            help="Alias of the satellite repo to pull from.")
    p_fed_link.add_argument(
        "--scope", default="all",
        help="Memory types to share: all | semantic | procedure | episodic "
             "or '+'-joined subset (default: all).",
    )
    p_fed_link.add_argument("--json", action="store_true")

    p_fed_list = fed_sub.add_parser("list", help="Show the full federation manifest.")
    p_fed_list.add_argument("--json", action="store_true")

    p_fed_fetch = fed_sub.add_parser(
        "fetch",
        help="Pull memories from linked repos for the current repo.",
    )
    p_fed_fetch.add_argument("--repo", default=".", help="Current repo root.")
    p_fed_fetch.add_argument("--feature", default=None)
    p_fed_fetch.add_argument("--file",    default=None)
    p_fed_fetch.add_argument("--symbol",  default=None)
    p_fed_fetch.add_argument("--json", action="store_true")

    # mem capture  (Phase 6.2) — agent-triggered high-signal capture
    p_mcap = mem_sub.add_parser(
        "capture",
        help=(
            "Agent-triggered capture: record a high-signal event automatically. "
            "Confidence is capped at 0.7; rate-limited to 5 per signal per hour."
        ),
    )
    p_mcap.add_argument("--repo", default=".")
    p_mcap.add_argument(
        "--signal",
        required=True,
        choices=list(CAPTURE_SIGNALS),
        help=(
            "Signal type: repeated-error | surprising-fix | validated-claim | "
            "repeated-lookup | scope-mismatch"
        ),
    )
    p_mcap.add_argument("--evidence", required=True,
                        help="Text to record (error msg, assertion, etc.).")
    p_mcap.add_argument("--feature", default=None, help="Feature scope hint.")
    p_mcap.add_argument("--file", default=None, dest="capture_file",
                        help="File scope hint.")
    p_mcap.add_argument("--symbol", default=None, help="Symbol scope hint.")
    p_mcap.add_argument("--author", default="agent",
                        help="Agent identifier (default: agent).")
    p_mcap.add_argument("--dry-run", action="store_true",
                        help="Preview without writing.")
    p_mcap.add_argument("--json", action="store_true")

    # mem touch  (Phase 6.1) — reinforce a memory by resetting its timestamp
    p_mtouch = mem_sub.add_parser(
        "touch",
        help="Reinforce a memory: reset its timestamp so effective_confidence returns to base.",
    )
    p_mtouch.add_argument("id", help="Memory id (mp_...).")
    p_mtouch.add_argument("--repo", default=".")
    p_mtouch.add_argument("--json", action="store_true")

    # mem prune  (Phase 6.1) — delete semantics whose effective_confidence < threshold
    p_mprune = mem_sub.add_parser(
        "prune",
        help="Delete semantic memories whose effective_confidence has decayed below a threshold.",
    )
    p_mprune.add_argument("--repo", default=".")
    p_mprune.add_argument(
        "--below", type=float, default=0.2,
        help="Remove entries with effective_confidence < this value (default: 0.2).",
    )
    p_mprune.add_argument(
        "--half-life", type=int, default=None, dest="half_life_days",
        help="Override half-life for this run (days, default: config.semantic_half_life).",
    )
    p_mprune.add_argument("--dry-run", action="store_true",
                          help="Preview what would be removed without deleting.")
    p_mprune.add_argument("--json", action="store_true")

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
        if s.get("suggestions"):
            print("did you mean: " + ", ".join(s["suggestions"]))
        elif "available" in s:
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
            for c in m["callees"][:25]:
                print(f"    - {c.get('id') or c.get('name')}  [{c.get('file', '')}]")
            if len(m["callees"]) > 25:
                print(f"    ... {len(m['callees']) - 25} more — run `scope callees {sym['id']}` for the full list")
        if m.get("callers"):
            print("  called by:")
            for c in m["callers"][:25]:
                print(f"    - {c['id']}  [{c.get('file', '')}]")
            if len(m["callers"]) > 25:
                print(f"    ... {len(m['callers']) - 25} more — run `scope callers {sym['id']}` for the full list")
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
    new_unindexed      = s.get("new_unindexed",      s.get("not_in_index", []))
    modified_unindexed = s.get("modified_unindexed", [])
    print(f"\nchanged ({len(changed)}):")
    for f in changed:
        print(f"  ~ {f}")
    if removed:
        print(f"\nremoved ({len(removed)}):")
        for f in removed:
            print(f"  - {f}")
    if modified_unindexed:
        print(f"\nmodified (not yet indexed — run `scope index` to add):")
        for f in modified_unindexed:
            print(f"  ~ {f}")
    if new_unindexed:
        print(f"\nnew files (not yet indexed — run `scope index` to add):")
        for f in new_unindexed:
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


def cmd_graph(args) -> int:
    from .core.graph_renderer import render_graph
    repo = _resolve_repo(args.repo)
    if _not_indexed(repo): return 2
    result = render_graph(
        repo,
        target=args.target,
        query=args.query,
        kind=args.kind,
        format=args.format,
        max_nodes=args.max_nodes,
    )
    if "error" in result:
        print(f"error: {result['error']}", file=__import__("sys").stderr)
        return 1
    if args.json:
        import json as _json
        print(_json.dumps(result, indent=2))
        return 0
    diagram = result["fenced"]
    if hasattr(args, "output") and args.output:
        Path(args.output).write_text(diagram, encoding="utf-8")
        print(f"diagram written to {args.output}  "
              f"({result['nodes']} nodes, {result['edges']} edges)")
    else:
        print(diagram)
        print(f"\n# {result['nodes']} nodes  {result['edges']} edges"
              + ("  (truncated)" if result.get("truncated") else ""))
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

    written  = [f for f in r.get("generated", []) if f.get("status") == "written"]
    skipped  = [f for f in r.get("generated", []) if f.get("status") == "skipped_existing"]
    pinned_s = [f for f in r.get("generated", []) if f.get("status") == "skipped_pinned"]

    if written:
        print("\ngenerated files:")
        for f in sorted(written, key=lambda x: x["path"]):
            layer_tag = f"[{f['layer']}]"
            print(f"  {layer_tag:<12} {f['path']}")

    if pinned_s:
        print("\nskipped (pinned — use `scope doc unpin <id>` to allow overwrite):")
        for f in sorted(pinned_s, key=lambda x: x["path"]):
            print(f"  📌 {f['path']}")

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

    # --verify health check summary
    hc = r.get("health_check")
    if hc and "error" not in hc:
        hc_status = "✓ healthy" if hc.get("healthy") else \
                    f"⚠ {hc.get('warnings',0)} warning(s)" if not hc.get("errors") else \
                    f"✗ {hc.get('errors',0)} error(s)"
        print(f"\npost-ingest health check: {hc_status}")
        for issue in hc.get("issues", []):
            sym = "✗" if issue["level"] == "error" else "⚠"
            print(f"  {sym} {issue['file']}: {issue['msg']}")
        if hc.get("healthy"):
            print("  all files look good")

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


def _doc_check(repo: Path) -> dict:
    """Validate the .ai-context/ directory and return a structured health report.

    Checks:
      - index.json present and parseable
      - every file listed in index.json exists on disk
      - no generated file is suspiciously short (< MIN_CHARS)
      - all three curated files exist (not just templates)
      - curated files have no unfilled TODO placeholders
      - source doc hash status (changed since last ingest?)
    """
    import re as _re
    ai_ctx = repo / ".ai-context"
    if not ai_ctx.exists():
        return {"error": "no .ai-context/ found — run `scope doc ingest` first"}

    MIN_CHARS = 120   # files shorter than this are flagged
    TODO_RE   = _re.compile(r"\bTODO\b")

    issues: list[dict] = []   # {"level": "warn"|"error", "file": path, "msg": str}
    passes: list[str]  = []   # brief descriptions of checks that passed

    # --- index.json ---
    index_path = ai_ctx / "generated" / "index.json"
    source = "?"; source_hash = ""; generated_at = "?"; mode = "?"
    index_files: list[dict] = []

    if not index_path.exists():
        issues.append({"level": "error", "file": ".ai-context/generated/index.json",
                       "msg": "index.json missing — run `scope doc ingest`"})
    else:
        try:
            idx = json.loads(index_path.read_text(encoding="utf-8"))
            source       = idx.get("source", "?")
            source_hash  = idx.get("source_hash", "")
            generated_at = idx.get("generated_at", "?")
            mode         = idx.get("mode", "?")
            index_files  = idx.get("files", [])
            passes.append(f"index.json valid  ({len(index_files)} files  mode={mode}  source={source})")
        except Exception as exc:  # noqa: BLE001
            issues.append({"level": "error", "file": ".ai-context/generated/index.json",
                           "msg": f"index.json unreadable: {exc}"})

    # --- check each file in index ---
    file_reports: list[dict] = []
    for entry in index_files:
        rel  = entry.get("path", "")
        fpath = repo / rel
        fd: dict = {"path": rel, "layer": entry.get("layer", "?"),
                    "title": entry.get("title", ""), "issues": []}
        if not fpath.exists():
            fd["issues"].append({"level": "error", "msg": "file missing on disk"})
            issues.append({"level": "error", "file": rel,
                           "msg": "listed in index.json but missing on disk"})
        else:
            try:
                content = fpath.read_text(encoding="utf-8")
                fd["chars"] = len(content)
                if len(content) < MIN_CHARS:
                    fd["issues"].append({"level": "warn",
                                         "msg": f"very short ({len(content)} chars) — may be missing content"})
                    issues.append({"level": "warn", "file": rel,
                                   "msg": f"very short ({len(content)} chars)"})
                else:
                    passes.append(f"{rel}  ({len(content):,} chars)")
            except OSError as exc:
                fd["issues"].append({"level": "error", "msg": f"unreadable: {exc}"})
                issues.append({"level": "error", "file": rel, "msg": str(exc)})
        file_reports.append(fd)

    # --- curated files ---
    CURATED_EXPECTED = ["constraints.md", "current-phase.md", "module-map.md"]
    cur_dir = ai_ctx / "curated"
    curated_reports: list[dict] = []
    for fname in CURATED_EXPECTED:
        fpath = cur_dir / fname
        rel   = f".ai-context/curated/{fname}"
        cd: dict = {"path": rel, "layer": "curated", "issues": []}
        if not fpath.exists():
            cd["issues"].append({"level": "warn",
                                  "msg": "missing — create manually or re-run ingest"})
            issues.append({"level": "warn", "file": rel,
                           "msg": "curated file missing (run ingest to create template)"})
        else:
            try:
                content = fpath.read_text(encoding="utf-8")
                cd["chars"] = len(content)
                todo_count = len(TODO_RE.findall(content))
                if todo_count:
                    cd["issues"].append({"level": "warn",
                                          "msg": f"contains {todo_count} unfilled TODO placeholder(s)"})
                    issues.append({"level": "warn", "file": rel,
                                   "msg": f"{todo_count} unfilled TODO placeholder(s)"})
                else:
                    passes.append(f"{rel}  ({len(content):,} chars)")
            except OSError as exc:
                cd["issues"].append({"level": "error", "msg": f"unreadable: {exc}"})
                issues.append({"level": "error", "file": rel, "msg": str(exc)})
        curated_reports.append(cd)

    # --- source doc changed? (best-effort) ---
    doc_changed = False
    if source_hash and source != "?":
        for candidate in [repo / source,
                          repo / "docs" / source,
                          repo / "design" / source]:
            if candidate.exists():
                from .core.doc_ingestor import _doc_hash as _dh
                current_hash = _dh(candidate)
                if current_hash and current_hash != source_hash:
                    doc_changed = True
                    issues.append({"level": "warn", "file": source,
                                   "msg": "source doc changed since last ingest — run `scope doc rebuild`"})
                break

    errors  = sum(1 for i in issues if i["level"] == "error")
    warns   = sum(1 for i in issues if i["level"] == "warn")
    healthy = errors == 0 and warns == 0

    return {
        "healthy":       healthy,
        "source":        source,
        "source_hash":   source_hash,
        "generated_at":  generated_at,
        "mode":          mode,
        "doc_changed":   doc_changed,
        "errors":        errors,
        "warnings":      warns,
        "issues":        issues,
        "passes":        passes,
        "generated_files": file_reports,
        "curated_files":   curated_reports,
    }


def _fmt_doc_check(r: dict) -> None:
    if "error" in r:
        print(r["error"]); return

    status = "✓ healthy" if r["healthy"] else \
             f"⚠ {r['warnings']} warning(s)" if r["errors"] == 0 else \
             f"✗ {r['errors']} error(s)  {r['warnings']} warning(s)"
    print(f"scope doc check — {status}")
    print(f"  source:       {r['source']}  (ingested: {r['generated_at']}  mode: {r['mode']})")
    if r.get("doc_changed"):
        print("  ⚠ source doc has changed since last ingest — run `scope doc rebuild`")
    print()

    all_files = r.get("generated_files", []) + r.get("curated_files", [])
    for fd in all_files:
        if fd.get("issues"):
            for issue in fd["issues"]:
                sym = "✗" if issue["level"] == "error" else "⚠"
                print(f"  {sym} {fd['path']}")
                print(f"      {issue['msg']}")
        else:
            chars = f"  ({fd.get('chars', 0):,} chars)" if "chars" in fd else ""
            print(f"  ✓ {fd['path']}{chars}")

    if r["healthy"]:
        print(f"\n  All {len(all_files)} file(s) look good.")
    else:
        print(f"\n  {r['errors']} error(s)  {r['warnings']} warning(s)")
        if r["errors"]:
            print("  → fix errors first: re-run `scope doc ingest` or create missing files")
        if r["warnings"]:
            print("  → warnings: edit curated files to replace TODO placeholders")


def _doc_diff(repo: Path) -> dict:
    """Compare current .ai-context/ file contents against the hashes stored in index.json.

    Detects files that have been manually edited since the last `scope doc ingest` run.

    Returns:
        {unchanged[], modified[], missing[], extra[], total_checked, has_changes}
    """
    import hashlib as _hashlib

    index_path = repo / ".ai-context" / "generated" / "index.json"
    if not index_path.exists():
        return {"error": "no .ai-context/ found — run `scope doc ingest` first"}

    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"error": f"index.json unreadable: {exc}"}

    files = index.get("files", [])
    source = index.get("source", "?")
    generated_at = index.get("generated_at", "?")

    unchanged: list[dict] = []
    modified:  list[dict] = []
    missing:   list[dict] = []

    for entry in files:
        rel  = entry.get("path", "")
        fid  = entry.get("id", rel)
        stored_hash = entry.get("written_hash", "")
        fpath = repo / rel
        base = {"id": fid, "path": rel, "layer": entry.get("layer", "?")}

        if not fpath.exists():
            missing.append({**base, "stored_hash": stored_hash})
            continue

        try:
            content = fpath.read_text(encoding="utf-8")
            current_hash = _hashlib.sha256(content.encode()).hexdigest()[:8]
        except OSError as exc:
            missing.append({**base, "note": str(exc)})
            continue

        if not stored_hash:
            # Older index.json without written_hash — can't diff this file
            unchanged.append({**base, "note": "no baseline hash (re-ingest to enable diff)"})
        elif current_hash == stored_hash:
            unchanged.append({**base, "current_hash": current_hash})
        else:
            modified.append({
                **base,
                "stored_hash":  stored_hash,
                "current_hash": current_hash,
            })

    # Also check for extra files on disk not in index.json
    indexed_paths = {e.get("path", "") for e in files}
    extra: list[dict] = []
    ai_gen = repo / ".ai-context" / "generated"
    if ai_gen.exists():
        for p in sorted(ai_gen.glob("*.md")):
            rel = str(p.relative_to(repo)).replace("\\", "/")
            if rel not in indexed_paths:
                extra.append({"id": p.stem, "path": rel, "layer": "generated"})

    has_changes = bool(modified or missing or extra)
    return {
        "source":        source,
        "generated_at":  generated_at,
        "total_checked": len(files),
        "unchanged":     unchanged,
        "modified":      modified,
        "missing":       missing,
        "extra":         extra,
        "has_changes":   has_changes,
    }


def _fmt_doc_diff(r: dict) -> None:
    if "error" in r:
        print(r["error"]); return

    status = "✓ no changes" if not r["has_changes"] else \
             f"⚠ {len(r['modified'])} modified  {len(r['missing'])} missing  {len(r['extra'])} extra"
    print(f"scope doc diff — {status}")
    print(f"  baseline: {r['source']}  (ingested: {r['generated_at']})")
    print(f"  checked:  {r['total_checked']} indexed file(s)")

    if r.get("modified"):
        print(f"\nmodified since last ingest ({len(r['modified'])}):")
        for f in r["modified"]:
            print(f"  ✎ [{f['layer']}] {f['path']}")
            print(f"      stored={f['stored_hash']}  current={f['current_hash']}")
        print("  → these files were edited after ingest — run `scope doc rebuild` to reset")

    if r.get("missing"):
        print(f"\nmissing from disk ({len(r['missing'])}):")
        for f in r["missing"]:
            note = f"  ({f.get('note','')})" if f.get("note") else ""
            print(f"  ✗ [{f['layer']}] {f['path']}{note}")
        print("  → re-run `scope doc ingest --overwrite` to regenerate")

    if r.get("extra"):
        print(f"\nextra files not in index.json ({len(r['extra'])}):")
        for f in r["extra"]:
            print(f"  + [{f['layer']}] {f['path']}")
        print("  → these files were added manually (safe to keep or remove)")

    if not r["has_changes"]:
        print(f"\n  All {r['total_checked']} file(s) match their ingest-time hashes.")


def _snapshots_dir(repo: Path) -> Path:
    return repo / ".ai-context" / "snapshots"


def _snapshot_path(repo: Path, name: str) -> Path:
    safe = name.replace("/", "-").replace("\\", "-")
    return _snapshots_dir(repo) / f"{safe}.json"


def _doc_snapshot_save(repo: Path, name: str) -> dict:
    """Capture current .ai-context/ file hashes as a named snapshot."""
    import hashlib as _hashlib
    import time as _time

    ai_ctx = repo / ".ai-context"
    if not ai_ctx.exists():
        return {"error": "no .ai-context/ found — run `scope doc ingest` first"}

    files: list[dict] = []
    for directory, layer in [
        (ai_ctx / "generated", "generated"),
        (ai_ctx / "curated",   "curated"),
    ]:
        if not directory.exists():
            continue
        for p in sorted(directory.glob("*.md")):
            rel = str(p.relative_to(repo)).replace("\\", "/")
            try:
                content = p.read_text(encoding="utf-8")
                h = _hashlib.sha256(content.encode()).hexdigest()[:8]
            except OSError:
                h = ""
            files.append({
                "id":    p.stem,
                "path":  rel,
                "layer": layer,
                "hash":  h,
                "chars": len(content) if h else 0,
            })

    snap_dir = _snapshots_dir(repo)
    snap_dir.mkdir(parents=True, exist_ok=True)

    snapshot = {
        "name":        name,
        "created_at":  _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
        "total_files": len(files),
        "files":       files,
    }
    _snapshot_path(repo, name).write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return {"saved": True, "name": name, "total_files": len(files),
            "path": str(_snapshot_path(repo, name).relative_to(repo)).replace("\\", "/")}


def _doc_snapshot_list(repo: Path) -> dict:
    snap_dir = _snapshots_dir(repo)
    if not snap_dir.exists():
        return {"snapshots": [], "total": 0}
    snapshots: list[dict] = []
    for p in sorted(snap_dir.glob("*.json")):
        try:
            snap = json.loads(p.read_text(encoding="utf-8"))
            snapshots.append({
                "name":        snap.get("name", p.stem),
                "created_at":  snap.get("created_at", "?"),
                "total_files": snap.get("total_files", 0),
            })
        except Exception:  # noqa: BLE001
            snapshots.append({"name": p.stem, "created_at": "?", "total_files": 0})
    return {"snapshots": snapshots, "total": len(snapshots)}


def _doc_snapshot_delete(repo: Path, name: str) -> dict:
    sp = _snapshot_path(repo, name)
    if not sp.exists():
        return {"error": f"snapshot '{name}' not found"}
    sp.unlink()
    return {"deleted": True, "name": name}


def _doc_diff_since(repo: Path, snapshot_name: str) -> dict:
    """Diff current .ai-context/ files against a named snapshot."""
    import hashlib as _hashlib

    sp = _snapshot_path(repo, snapshot_name)
    if not sp.exists():
        return {"error": f"snapshot '{snapshot_name}' not found — "
                         f"create one with `scope doc snapshot save {snapshot_name}`"}
    try:
        snap = json.loads(sp.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"error": f"snapshot unreadable: {exc}"}

    snap_files: dict[str, str] = {f["path"]: f["hash"] for f in snap.get("files", [])}

    ai_ctx = repo / ".ai-context"
    current_files: dict[str, str] = {}
    for directory in [ai_ctx / "generated", ai_ctx / "curated"]:
        if not directory.exists():
            continue
        for p in sorted(directory.glob("*.md")):
            rel = str(p.relative_to(repo)).replace("\\", "/")
            try:
                content = p.read_text(encoding="utf-8")
                current_files[rel] = _hashlib.sha256(content.encode()).hexdigest()[:8]
            except OSError:
                current_files[rel] = ""

    unchanged: list[dict] = []
    modified:  list[dict] = []
    missing:   list[dict] = []
    added:     list[dict] = []  # new files not in snapshot

    for rel, snap_hash in snap_files.items():
        cur_hash = current_files.get(rel)
        base = {"id": rel.split("/")[-1].replace(".md", ""), "path": rel}
        if cur_hash is None:
            missing.append({**base, "snap_hash": snap_hash})
        elif cur_hash == snap_hash:
            unchanged.append({**base, "hash": cur_hash})
        else:
            modified.append({**base, "snap_hash": snap_hash, "current_hash": cur_hash})

    for rel, cur_hash in current_files.items():
        if rel not in snap_files:
            added.append({"id": rel.split("/")[-1].replace(".md", ""), "path": rel,
                          "current_hash": cur_hash})

    has_changes = bool(modified or missing or added)
    return {
        "snapshot":      snapshot_name,
        "snapshot_at":   snap.get("created_at", "?"),
        "total_checked": len(snap_files),
        "unchanged":     unchanged,
        "modified":      modified,
        "missing":       missing,
        "added":         added,
        "has_changes":   has_changes,
    }


def _fmt_snapshot_list(r: dict) -> None:
    snaps = r.get("snapshots", [])
    if not snaps:
        print("no snapshots saved yet")
        print("  → create one with: scope doc snapshot save <name>")
        return
    print(f"snapshots ({r['total']}):")
    for s in snaps:
        print(f"  {s['name']:<25} {s['created_at']}  ({s['total_files']} files)")


def _fmt_doc_diff_since(r: dict) -> None:
    if "error" in r:
        print(r["error"]); return
    status = "✓ no changes" if not r["has_changes"] else \
             (f"⚠ {len(r['modified'])} modified  {len(r['missing'])} missing  "
              f"{len(r['added'])} added")
    print(f"scope doc diff --since '{r['snapshot']}'  (taken {r['snapshot_at']})  — {status}")
    print(f"  checked: {r['total_checked']} file(s) in snapshot")
    if r.get("modified"):
        print(f"\nmodified ({len(r['modified'])}):")
        for f in r["modified"]:
            print(f"  ✎ {f['path']}")
            print(f"      snapshot={f['snap_hash']}  current={f['current_hash']}")
    if r.get("missing"):
        print(f"\ndeleted since snapshot ({len(r['missing'])}):")
        for f in r["missing"]:
            print(f"  ✗ {f['path']}")
    if r.get("added"):
        print(f"\nadded since snapshot ({len(r['added'])}):")
        for f in r["added"]:
            print(f"  + {f['path']}")
    if not r["has_changes"]:
        print(f"\n  All {r['total_checked']} file(s) unchanged since snapshot.")


def _doc_report(repo: Path) -> dict:
    """Produce a comprehensive dict summarising the entire .ai-context/ state.

    Aggregates: file list, pin status, annotation counts, snapshot inventory,
    token budget, health check result, and source doc info.

    Designed to be called as a single MCP call before starting work on a feature.
    """
    import time as _time

    report: dict = {
        "generated_at": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
        "repo":         str(repo),
    }

    ai_ctx = repo / ".ai-context"
    if not ai_ctx.exists():
        report["error"] = "no .ai-context/ found — run `scope doc ingest` first"
        return report

    # --- index info ---
    index_path = ai_ctx / "generated" / "index.json"
    source = "?"; generated_at = "?"; mode = "?"; source_hash = ""
    index_files: list[dict] = []
    pinned_set: set[str] = set()
    if index_path.exists():
        try:
            idx = json.loads(index_path.read_text(encoding="utf-8"))
            source       = idx.get("source", "?")
            generated_at = idx.get("generated_at", "?")
            mode         = idx.get("mode", "?")
            source_hash  = idx.get("source_hash", "")
            index_files  = idx.get("files", [])
            pinned_set   = set(idx.get("pinned_files", []))
        except Exception:  # noqa: BLE001
            pass

    report["source"] = source
    report["ingested_at"] = generated_at
    report["mode"] = mode

    # --- file inventory ---
    stats = _doc_stats(repo)
    all_files: list[dict] = []
    ann_data = _load_annotations(repo)

    for f in stats.get("generated", []) + stats.get("curated", []):
        # Annotation count: generated from index_files; curated from ann_data
        ann_count = 0
        for entry in index_files:
            if entry.get("path") == f["path"]:
                ann_count = len(entry.get("annotations", []))
                break
        ann_count += len(ann_data.get(f["path"], []))

        all_files.append({
            "id":      f["id"],
            "path":    f["path"],
            "layer":   f["layer"],
            "chars":   f["chars"],
            "tokens":  f["tokens"],
            "pinned":  f["path"] in pinned_set,
            "annotations": ann_count,
        })

    report["files"] = all_files
    report["total_files"]  = len(all_files)
    report["total_chars"]  = stats.get("total_chars", 0)
    report["total_tokens"] = stats.get("total_tokens", 0)
    report["pinned_count"] = len(pinned_set)

    # --- snapshots ---
    snap_list = _doc_snapshot_list(repo)
    report["snapshots"] = snap_list.get("snapshots", [])
    report["total_snapshots"] = snap_list.get("total", 0)

    # --- health ---
    health = _doc_check(repo)
    report["healthy"]        = health.get("healthy", False)
    report["health_errors"]  = health.get("errors", 0)
    report["health_warnings"]= health.get("warnings", 0)
    report["health_issues"]  = health.get("issues", [])
    report["doc_changed"]    = health.get("doc_changed", False)

    # --- context budget hint ---
    tok = report["total_tokens"]
    if tok < 8_000:
        budget_hint = "fits in 8k context"
    elif tok < 32_000:
        budget_hint = "fits in 32k context"
    elif tok < 128_000:
        budget_hint = "fits in 128k context"
    else:
        budget_hint = "⚠ exceeds 128k — use selective fetch"
    report["budget_hint"] = budget_hint

    return report


def _fmt_doc_report(r: dict) -> None:
    if "error" in r:
        print(r["error"]); return

    health_sym = "✓" if r["healthy"] else \
                 "⚠" if r["health_errors"] == 0 else "✗"
    print(f"# .ai-context/ Report — {r['source']}")
    print(f"  ingested: {r['ingested_at']}  mode: {r['mode']}")
    print(f"  health: {health_sym}  "
          f"errors={r['health_errors']}  warnings={r['health_warnings']}")
    print(f"  budget: {r['total_chars']:,} chars  ~{r['total_tokens']:,} tok  "
          f"({r['budget_hint']})")
    if r.get("doc_changed"):
        print("  ⚠ source doc changed since last ingest — run `scope doc rebuild`")
    print()

    # File table
    print(f"{'id':<40}  {'layer':<10}  {'chars':>7}  {'~tok':>6}  flags")
    print(f"{'─'*40}  {'─'*10}  {'─'*7}  {'─'*6}  {'─'*10}")
    for f in r.get("files", []):
        flags: list[str] = []
        if f["pinned"]:       flags.append("📌")
        if f["annotations"]:  flags.append(f"✎×{f['annotations']}")
        flag_str = "  ".join(flags)
        print(f"  {f['id']:<38}  {f['layer']:<10}  {f['chars']:>7,}  "
              f"{f['tokens']:>6,}  {flag_str}")

    # Snapshots
    snaps = r.get("snapshots", [])
    if snaps:
        print(f"\nsnapshots ({r['total_snapshots']}):")
        for s in snaps:
            print(f"  {s['name']:<25} {s['created_at']}  ({s['total_files']} files)")
    else:
        print("\nno snapshots — create one with: scope doc snapshot save <name>")

    # Health issues
    issues = r.get("health_issues", [])
    if issues:
        print(f"\nhealth issues ({len(issues)}):")
        for issue in issues:
            sym = "✗" if issue["level"] == "error" else "⚠"
            print(f"  {sym} {issue['file']}: {issue['msg']}")

    print(f"\n  {r['total_files']} files  {r['pinned_count']} pinned  "
          f"{r['total_snapshots']} snapshots  "
          f"generated {r['generated_at']}")


def _fmt_doc_report_to_str(r: dict) -> str:
    """Render the doc report as a markdown string (for --output <file>)."""
    import io as _io
    buf = _io.StringIO()
    old_stdout = __import__("sys").stdout
    __import__("sys").stdout = buf
    try:
        _fmt_doc_report(r)
    finally:
        __import__("sys").stdout = old_stdout
    return buf.getvalue()


def _doc_tag(
    repo: Path,
    name: str,
    *,
    add_tags: list[str] | None = None,
    remove_tags: list[str] | None = None,
    clear: bool = False,
) -> dict:
    """Add, remove, or clear tags on a generated .ai-context/ file.

    Tags are stored in the file's entry in index.json as a list of strings.
    For curated files, tags are stored in .ai-context/annotations.json under a
    separate 'tags' key alongside annotations.

    Returns {id, path, layer, tags[], action}.
    """
    match = _resolve_file_id(repo, name)
    if match is None:
        return {"error": f"no unique file matching '{name}' — use `scope doc list` to see ids"}
    fid, rel = match

    layer = "curated" if "/curated/" in rel else "generated"

    if layer == "generated":
        index_path = repo / ".ai-context" / "generated" / "index.json"
        if not index_path.exists():
            return {"error": "index.json not found — run `scope doc ingest` first"}
        try:
            idx = json.loads(index_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            return {"error": f"index.json unreadable: {exc}"}

        entry = next((e for e in idx.get("files", []) if e.get("path") == rel), None)
        if entry is None:
            return {"error": f"file '{fid}' not found in index.json"}

        tags: list[str] = list(entry.get("tags", []))

        if clear:
            tags = []
        else:
            for t in (add_tags or []):
                if t not in tags:
                    tags.append(t)
            for t in (remove_tags or []):
                tags = [x for x in tags if x != t]

        entry["tags"] = tags
        index_path.write_text(json.dumps(idx, indent=2, ensure_ascii=False),
                               encoding="utf-8")
        action = "cleared" if clear else ("modified" if (add_tags or remove_tags) else "view")
        return {"id": fid, "path": rel, "layer": layer, "tags": tags, "action": action}

    else:
        # Curated — use annotations.json with a separate 'tags' key
        data = _load_annotations(repo)
        entry = data.setdefault(rel, [])
        # Tags stored as a special dict with marker key
        tag_record: dict | None = None
        for item in entry:
            if isinstance(item, dict) and item.get("__type__") == "tags":
                tag_record = item
                break
        if tag_record is None:
            tag_record = {"__type__": "tags", "tags": []}
            entry.append(tag_record)
            data[rel] = entry

        tags = list(tag_record.get("tags", []))
        if clear:
            tags = []
        else:
            for t in (add_tags or []):
                if t not in tags:
                    tags.append(t)
            for t in (remove_tags or []):
                tags = [x for x in tags if x != t]

        tag_record["tags"] = tags
        _save_annotations(repo, data)
        action = "cleared" if clear else ("modified" if (add_tags or remove_tags) else "view")
        return {"id": fid, "path": rel, "layer": layer, "tags": tags, "action": action}


def _get_file_tags(repo: Path, rel_path: str, layer: str,
                   index_files: list[dict], ann_data: dict) -> list[str]:
    """Read the tags for a file from the appropriate store."""
    if layer == "generated":
        for entry in index_files:
            if entry.get("path") == rel_path:
                return list(entry.get("tags", []))
        return []
    else:
        entries = ann_data.get(rel_path, [])
        for item in entries:
            if isinstance(item, dict) and item.get("__type__") == "tags":
                return list(item.get("tags", []))
        return []


def _read_pinned(repo: Path) -> set[str]:
    """Read the set of pinned file paths from index.json (returns empty set if absent)."""
    index_path = repo / ".ai-context" / "generated" / "index.json"
    if not index_path.exists():
        return set()
    try:
        idx = json.loads(index_path.read_text(encoding="utf-8"))
        return set(idx.get("pinned_files", []))
    except Exception:  # noqa: BLE001
        return set()


def _write_pinned(repo: Path, pinned: set[str]) -> bool:
    """Write the updated pinned_files list to index.json.  Returns True on success."""
    index_path = repo / ".ai-context" / "generated" / "index.json"
    if not index_path.exists():
        return False
    try:
        idx = json.loads(index_path.read_text(encoding="utf-8"))
        idx["pinned_files"] = sorted(pinned)
        index_path.write_text(json.dumps(idx, indent=2, ensure_ascii=False),
                               encoding="utf-8")
        return True
    except Exception:  # noqa: BLE001
        return False


def _resolve_file_id(repo: Path, name: str) -> tuple[str, str] | None:
    """Resolve a partial file id/name to (file_id, relative_path) using index.json + curated/.

    Returns None if no match or ambiguous.
    """
    index_path = repo / ".ai-context" / "generated" / "index.json"
    curated_dir = repo / ".ai-context" / "curated"
    q = name.lower()

    candidates: list[tuple[str, str]] = []  # (id, rel_path)

    if index_path.exists():
        try:
            idx = json.loads(index_path.read_text(encoding="utf-8"))
            for f in idx.get("files", []):
                if q in f["id"].lower() or q in f.get("title", "").lower():
                    candidates.append((f["id"], f["path"]))
        except Exception:  # noqa: BLE001
            pass

    if curated_dir.exists():
        for p in curated_dir.glob("*.md"):
            if q in p.stem.lower():
                rel = str(p.relative_to(repo)).replace("\\", "/")
                cid = p.stem
                if not any(c[0] == cid for c in candidates):
                    candidates.append((cid, rel))

    if len(candidates) == 1:
        return candidates[0]
    return None   # 0 matches or ambiguous


def _doc_pin(repo: Path, name: str) -> dict:
    """Pin a .ai-context/ file by id/partial-name."""
    match = _resolve_file_id(repo, name)
    if match is None:
        return {"error": f"no unique file matching '{name}' — use `scope doc list` to see ids"}
    fid, rel = match
    pinned = _read_pinned(repo)
    if rel in pinned:
        return {"pinned": False, "already_pinned": True, "id": fid, "path": rel}
    pinned.add(rel)
    ok = _write_pinned(repo, pinned)
    if not ok:
        return {"error": "could not update index.json — is .ai-context/ readable?"}
    return {"pinned": True, "id": fid, "path": rel,
            "note": f"'{fid}' is now pinned — ingest/rebuild will skip it"}


def _doc_unpin(repo: Path, name: str) -> dict:
    """Remove a pin from a .ai-context/ file."""
    match = _resolve_file_id(repo, name)
    if match is None:
        return {"error": f"no unique file matching '{name}' — use `scope doc list` to see ids"}
    fid, rel = match
    pinned = _read_pinned(repo)
    if rel not in pinned:
        return {"unpinned": False, "not_pinned": True, "id": fid, "path": rel}
    pinned.discard(rel)
    ok = _write_pinned(repo, pinned)
    if not ok:
        return {"error": "could not update index.json"}
    return {"unpinned": True, "id": fid, "path": rel,
            "note": f"'{fid}' unpinned — ingest/rebuild can overwrite it again"}


def _annotations_path(repo: Path) -> Path:
    """Path to the shared annotations store for curated files."""
    return repo / ".ai-context" / "annotations.json"


def _load_annotations(repo: Path) -> dict:
    """Return {rel_path: [annotation_dict, ...]} for all files."""
    p = _annotations_path(repo)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    return {}


def _save_annotations(repo: Path, data: dict) -> None:
    p = _annotations_path(repo)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _doc_annotate(
    repo: Path,
    name: str,
    *,
    add_note: str | None = None,
    author: str = "",
    clear: bool = False,
) -> dict:
    """Add, view, or clear annotations for a .ai-context/ file.

    Annotations for generated files are stored in index.json (per file entry).
    Annotations for curated files are stored in .ai-context/annotations.json.

    Returns:
        {id, path, layer, annotations[], action}
    """
    import time as _time

    match = _resolve_file_id(repo, name)
    if match is None:
        return {"error": f"no unique file matching '{name}' — use `scope doc list` to see ids"}
    fid, rel = match

    # Determine layer by checking which dir the path is in
    layer = "curated" if "/curated/" in rel else "generated"

    if layer == "generated":
        # Annotations live inside index.json → file entry
        index_path = repo / ".ai-context" / "generated" / "index.json"
        if not index_path.exists():
            return {"error": "index.json not found — run `scope doc ingest` first"}
        try:
            idx = json.loads(index_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            return {"error": f"index.json unreadable: {exc}"}

        # Find or create the file entry
        for entry in idx.get("files", []):
            if entry.get("path") == rel:
                break
        else:
            return {"error": f"file '{fid}' not found in index.json"}

        annotations: list[dict] = entry.setdefault("annotations", [])

        if clear:
            entry["annotations"] = []
            index_path.write_text(json.dumps(idx, indent=2, ensure_ascii=False),
                                   encoding="utf-8")
            return {"id": fid, "path": rel, "layer": layer,
                    "annotations": [], "action": "cleared"}

        if add_note:
            new_ann = {
                "ts":     _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
                "note":   add_note,
                "author": author,
            }
            annotations.append(new_ann)
            index_path.write_text(json.dumps(idx, indent=2, ensure_ascii=False),
                                   encoding="utf-8")
            return {"id": fid, "path": rel, "layer": layer,
                    "annotations": list(annotations), "action": "added"}

        # View-only
        return {"id": fid, "path": rel, "layer": layer,
                "annotations": list(annotations), "action": "view"}

    else:
        # Curated: annotations.json
        data = _load_annotations(repo)
        ann_list: list[dict] = data.setdefault(rel, [])

        if clear:
            data[rel] = []
            _save_annotations(repo, data)
            return {"id": fid, "path": rel, "layer": layer,
                    "annotations": [], "action": "cleared"}

        if add_note:
            new_ann = {
                "ts":     _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
                "note":   add_note,
                "author": author,
            }
            ann_list.append(new_ann)
            _save_annotations(repo, data)
            return {"id": fid, "path": rel, "layer": layer,
                    "annotations": list(ann_list), "action": "added"}

        return {"id": fid, "path": rel, "layer": layer,
                "annotations": list(ann_list), "action": "view"}


def _fmt_doc_annotate(r: dict) -> None:
    if "error" in r:
        print(r["error"]); return

    action_map = {"cleared": "cleared all annotations",
                  "added":   "annotation added",
                  "view":    "annotations"}
    action_str = action_map.get(r["action"], r["action"])
    print(f"[{r['layer']}] {r['path']}  — {action_str}")

    annotations = r.get("annotations", [])
    if not annotations:
        print("  (no annotations)")
        if r["action"] == "view":
            print("  → add one with: scope doc annotate <file-id> --add \"your note\"")
        return
    for i, ann in enumerate(annotations, 1):
        author_str = f"  — {ann['author']}" if ann.get("author") else ""
        print(f"  [{i}] {ann.get('ts','?')}{author_str}")
        print(f"       {ann['note']}")


def _doc_fetch_for(
    repo: Path,
    feature: str,
    *,
    include_memories: bool = True,
    include_scope: bool = True,
) -> dict:
    """Return a unified context bundle for a feature: doc excerpts + memories + scope.

    Layers returned:
      doc_files  — .ai-context/ files whose name matches the feature slug
      doc_search — lines from .ai-context/ files that mention the feature
      memories   — relevant MemPalace entries (if include_memories)
      scope      — feature scope info from index (if include_scope + indexed)
    """
    import re as _re

    # Normalise feature name to a slug for file matching
    slug = _re.sub(r"[^a-z0-9]+", "-", feature.lower()).strip("-")

    result: dict = {
        "feature":    feature,
        "slug":       slug,
        "doc_files":  [],
        "doc_search": [],
        "memories":   [],
        "scope":      None,
    }

    # --- 1. Find .ai-context/ files that match the feature slug ---
    ai_ctx = repo / ".ai-context"
    if ai_ctx.exists():
        for directory, layer in [
            (ai_ctx / "generated", "generated"),
            (ai_ctx / "curated",   "curated"),
        ]:
            if not directory.exists():
                continue
            for p in sorted(directory.glob("*.md")):
                # Match if slug appears anywhere in the filename
                if slug in p.stem or slug.replace("-", "") in p.stem.replace("-", ""):
                    try:
                        content = p.read_text(encoding="utf-8")
                    except OSError:
                        continue
                    rel = str(p.relative_to(repo)).replace("\\", "/")
                    result["doc_files"].append({
                        "id":      p.stem,
                        "path":    rel,
                        "layer":   layer,
                        "content": content,
                        "chars":   len(content),
                    })

        # --- 2. Search .ai-context/ for mentions of the feature name ---
        search_r = _doc_search(repo, feature, layer="all", context_lines=2)
        if "error" not in search_r:
            # Exclude files already returned in doc_files to avoid duplication
            existing_paths = {f["path"] for f in result["doc_files"]}
            result["doc_search"] = [
                r for r in search_r.get("results", [])
                if r["path"] not in existing_paths
            ]

    # --- 3. Fetch relevant memories ---
    if include_memories:
        try:
            from .core.mempalace import fetch_relevant
            mem_r = fetch_relevant(repo, feature=slug, limit=15)
            if "error" not in mem_r:
                # Flatten all memory layers into a single list
                layers = mem_r.get("layers", {})
                mems: list[dict] = []
                for layer_key in ("semantic", "procedural", "episodic"):
                    mems.extend(layers.get(layer_key, []))
                result["memories"] = mems
        except Exception:  # noqa: BLE001
            pass

    # --- 4. Scope index lookup ---
    if include_scope:
        try:
            from .core.query_engine import get_feature_scope
            from .core import store
            if store.is_initialized(repo):
                scope_r = get_feature_scope(repo, feature)
                if "error" not in scope_r:
                    result["scope"] = {
                        "files":       scope_r.get("files", [])[:20],
                        "tests":       [t["file"] for t in scope_r.get("tests", [])[:5]],
                        "feature":     scope_r.get("feature", {}),
                    }
        except Exception:  # noqa: BLE001
            pass

    result["total_doc_files"]    = len(result["doc_files"])
    result["total_doc_excerpts"] = len(result["doc_search"])
    result["total_memories"]     = len(result["memories"])
    return result


def _fmt_doc_fetch_for(r: dict) -> None:
    if "error" in r:
        print(r["error"]); return

    print(f"# Context bundle: {r['feature']}")
    print(f"  doc files matched:   {r['total_doc_files']}")
    print(f"  doc sections found:  {r['total_doc_excerpts']}")
    print(f"  memories:            {r['total_memories']}")
    if r["scope"]:
        s = r["scope"]
        feat = s.get("feature", {})
        print(f"  scope:  {feat.get('file_count',0)} files  "
              f"{feat.get('symbol_count',0)} symbols")

    # --- Full doc files (highest priority — exact filename match) ---
    for df in r.get("doc_files", []):
        print(f"\n{'═'*60}")
        print(f"  [{df['layer']}] {df['path']}  ({df['chars']:,} chars)")
        print(f"{'═'*60}")
        # Print first 60 lines to avoid flooding the terminal
        lines = df["content"].splitlines()
        for line in lines[:60]:
            print(line)
        if len(lines) > 60:
            print(f"\n  … ({len(lines)-60} more lines — use `scope doc fetch {df['id']}`)")

    # --- Doc search excerpts ---
    for res in r.get("doc_search", [])[:5]:
        print(f"\n{'─'*60}")
        print(f"  [{res['layer']}] {res['path']}  ({res['match_count']} mention(s))")
        print(f"{'─'*60}")
        for m in res["matches"][:3]:
            for ctx in m["context_before"]:
                print(f"  {ctx}")
            print(f"→ {m['line']}")
            for ctx in m["context_after"]:
                print(f"  {ctx}")

    # --- Memories ---
    if r.get("memories"):
        print(f"\n{'─'*60}")
        print(f"  MEMORIES ({r['total_memories']})")
        print(f"{'─'*60}")
        for mem in r["memories"][:10]:
            kind = mem.get("type", "note")
            conf = f"  conf={mem.get('confidence',1.0):.0%}" if kind == "semantic" else ""
            print(f"  [{kind}]{conf}  {mem.get('note','')[:100]}")

    # --- Scope index ---
    if r["scope"]:
        print(f"\n{'─'*60}")
        print(f"  SCOPE FILES")
        print(f"{'─'*60}")
        for f in r["scope"]["files"][:10]:
            print(f"  {f}")
        if r["scope"]["tests"]:
            print(f"  tests: {', '.join(r['scope']['tests'])}")

    if not any([r["doc_files"], r["doc_search"], r["memories"], r["scope"]]):
        print(f"\n  (no context found for '{r['feature']}' — "
              f"run `scope doc ingest` first or try a different feature name)")


def _fmt_batch_ingest(r: dict) -> None:
    if "error" in r:
        print(r["error"]); return
    total  = r.get("total_docs", 0)
    done   = r.get("docs_ingested", 0)
    skipped = r.get("docs_skipped_unchanged", 0)
    errors = r.get("docs_errored", 0)
    print(f"scope doc ingest-batch — {total} file(s) found")
    print(f"  ingested:  {done}")
    print(f"  unchanged: {skipped}  (--if-changed)")
    print(f"  errors:    {errors}")
    print(f"  files written total:   {r.get('total_files_written', 0)}")
    print(f"  memories added total:  {r.get('total_memories_added', 0)}")
    print(f"  templates created:     {r.get('total_templates_created', 0)}")
    results = r.get("results", [])
    if results:
        print("\nper-document summary:")
        for res in results:
            src = Path(res.get("source", "?")).name
            status = "skipped (unchanged)" if res.get("unchanged") else \
                     f"error: {res.get('error')}" if "error" in res else \
                     f"written={res.get('files_written', 0)}  " \
                     f"memories={res.get('memories_added', 0)}"
            print(f"  {src:<40} {status}")


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
                context_lines: int = 2, use_regex: bool = False,
                tag_filter: str | None = None) -> dict:
    """Search all .ai-context/ files for a keyword or regex (case-insensitive).

    If tag_filter is set, only files that have the given tag are searched.

    Returns a list of matches: {file_id, path, layer, matches[]}.
    Each match has {line_no, line, context_before[], context_after[]}.
    """
    ai_ctx = repo / ".ai-context"
    if not ai_ctx.exists():
        return {"error": "no .ai-context/ found — run `scope doc ingest` first"}

    import re as _re
    try:
        raw_pattern = query if use_regex else _re.escape(query)
        pattern = _re.compile(raw_pattern, _re.IGNORECASE)
    except _re.error as exc:
        return {"error": f"invalid regex pattern: {exc}"}
    results: list[dict] = []

    # Build tag-aware allowed-paths set if tag_filter is set
    allowed_paths: set[str] | None = None
    if tag_filter:
        index_files_: list[dict] = []
        idx_p = ai_ctx / "generated" / "index.json"
        if idx_p.exists():
            try:
                index_files_ = json.loads(idx_p.read_text(encoding="utf-8")).get("files", [])
            except Exception:  # noqa: BLE001
                pass
        ann_data_ = _load_annotations(repo)
        allowed_paths = set()
        for directory, lyr in [(ai_ctx / "generated", "generated"),
                                (ai_ctx / "curated",   "curated")]:
            if not directory.exists():
                continue
            for p in directory.glob("*.md"):
                rel = str(p.relative_to(repo)).replace("\\", "/")
                tags = _get_file_tags(repo, rel, lyr, index_files_, ann_data_)
                if tag_filter in tags:
                    allowed_paths.add(rel)

    def _search_dir(directory: Path, lyr: str) -> None:
        if not directory.exists():
            return
        for p in sorted(directory.glob("*.md")):
            rel = str(p.relative_to(repo)).replace("\\", "/")
            if allowed_paths is not None and rel not in allowed_paths:
                continue  # tag filter excludes this file
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
    total_candidate_files = (
        len(list((ai_ctx / "generated").glob("*.md")) if (ai_ctx / "generated").exists() else [])
        + len(list((ai_ctx / "curated").glob("*.md")) if (ai_ctx / "curated").exists() else [])
    )
    return {
        "query":         query,
        "use_regex":     use_regex,
        "tag_filter":    tag_filter,
        "files_searched": len(allowed_paths) if allowed_paths is not None else total_candidate_files,
        "files_with_matches": len(results),
        "total_matches": total_matches,
        "results":       results,
    }


def _fmt_doc_search(r: dict) -> None:
    if "error" in r:
        print(r["error"]); return
    mode_tag = "  [regex]" if r.get("use_regex") else ""
    print(f"search: '{r['query']}'{mode_tag}  —  {r['total_matches']} match(es) "
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


def _extract_section(content: str, heading: str) -> str | None:
    """Extract the content of a specific markdown heading section (case-insensitive partial match).

    Returns the text of the section from the heading line until the next
    heading at the same or higher level, or end of file. Returns None if not found.
    """
    import re as _re
    q = heading.lower()
    lines = content.splitlines(keepends=True)
    start: int | None = None
    start_level: int = 0

    for i, line in enumerate(lines):
        m = _re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            if start is None:
                if q in title.lower():
                    start = i
                    start_level = level
            else:
                # Stop when we hit a heading at the same or higher level
                if level <= start_level:
                    return "".join(lines[start:i]).rstrip()

    if start is not None:
        return "".join(lines[start:]).rstrip()
    return None


def _doc_fetch_section(repo: Path, name: str, heading: str) -> dict:
    """Fetch a file then extract a specific section by heading."""
    file_result = _doc_fetch(repo, name)
    if "error" in file_result:
        return file_result

    section_text = _extract_section(file_result["content"], heading)
    if section_text is None:
        return {"error": f"no section matching '{heading}' in {file_result['id']} — "
                         f"check headings with `scope doc fetch {name}`"}

    return {
        "id":        file_result["id"],
        "path":      file_result["path"],
        "title":     file_result["title"],
        "layer":     file_result["layer"],
        "heading":   heading,
        "content":   section_text,
        "chars":     len(section_text),
        "full_chars": file_result["chars"],
    }


def _doc_outline(repo: Path, name: str) -> dict:
    """Return the heading hierarchy of a .ai-context/ file.

    Returns:
        {id, path, title, layer, headings[], total_headings, chars}
    Each heading: {level, text, line_no, char_offset}
    """
    import re as _re
    file_result = _doc_fetch(repo, name)
    if "error" in file_result:
        return file_result

    content = file_result["content"]
    headings: list[dict] = []
    char_offset = 0
    for line_no, line in enumerate(content.splitlines(), 1):
        m = _re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            headings.append({
                "level":       len(m.group(1)),
                "text":        m.group(2).strip(),
                "line_no":     line_no,
                "char_offset": char_offset,
            })
        char_offset += len(line) + 1  # +1 for newline

    return {
        "id":             file_result["id"],
        "path":           file_result["path"],
        "title":          file_result["title"],
        "layer":          file_result["layer"],
        "headings":       headings,
        "total_headings": len(headings),
        "chars":          file_result["chars"],
    }


def _fmt_doc_outline(r: dict) -> None:
    if "error" in r:
        print(r["error"]); return
    print(f"# {r['title']}  [{r['layer']}]  "
          f"({r['total_headings']} headings  {r['chars']:,} chars)")
    print(f"# path: {r['path']}")
    print()
    indent_map = {1: "", 2: "  ", 3: "    ", 4: "      ", 5: "        ", 6: "          "}
    for h in r["headings"]:
        indent = indent_map.get(h["level"], "            ")
        marker = "#" * h["level"]
        print(f"{indent}{marker} {h['text']}  (line {h['line_no']})")
    if not r["headings"]:
        print("  (no headings found)")


def _fmt_doc_fetch(r: dict) -> None:
    if "error" in r:
        print(r["error"]); return
    if "heading" in r:
        print(f"# {r['title']} → section '{r['heading']}'  [{r['layer']}]  "
              f"({r['chars']} / {r['full_chars']} chars)")
        print(f"# path: {r['path']}")
    else:
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
    tag_filter: str | None = None,
) -> dict:
    """Concatenate all .ai-context/ files into a single text blob.

    If tag_filter is set, only files carrying that tag are included.

    Returns:
        {content, total_files, total_chars, total_tokens, source, files[]}
    """
    ai_ctx = repo / ".ai-context"
    if not ai_ctx.exists():
        return {"error": "no .ai-context/ found — run `scope doc ingest` first"}

    # Discover source doc name from index.json if available
    index_path = ai_ctx / "generated" / "index.json"
    source = "unknown"
    index_files_: list[dict] = []
    if index_path.exists():
        try:
            idx_data = json.loads(index_path.read_text(encoding="utf-8"))
            source = idx_data.get("source", "unknown")
            index_files_ = idx_data.get("files", [])
        except Exception:  # noqa: BLE001
            pass

    ann_data_ = _load_annotations(repo) if tag_filter else {}

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
            if tag_filter:
                tags = _get_file_tags(repo, rel, lyr, index_files_, ann_data_)
                if tag_filter not in tags:
                    continue
            sections.append({
                "id":    p.stem,
                "path":  rel,
                "layer": lyr,
                "text":  text,
                "chars": len(text),
            })

    if not sections:
        if tag_filter:
            return {"error": f"no .ai-context/ files carry tag '{tag_filter}'"}
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


def _doc_validate(repo: Path) -> dict:
    """Check .ai-context/ integrity: orphaned index entries, untracked files, drift.

    Returns:
        {ok, total_issues, errors, warnings,
         issues: [{severity, code, message, file}]}
    Severity codes:
        E001 — index entry references a file that does not exist on disk
        E002 — file on disk has no matching index entry (untracked)
        W001 — current file hash differs from written_hash (post-ingest edit)
        W002 — annotation entry references a missing file
        W003 — snapshot references a path no longer on disk
    """
    import hashlib as _hl
    ai_ctx = repo / ".ai-context"
    if not ai_ctx.exists():
        return {"error": "no .ai-context/ found — run `scope doc ingest` first"}

    issues: list[dict] = []

    def _add(severity: str, code: str, message: str, file: str = "") -> None:
        issues.append({"severity": severity, "code": code, "message": message, "file": file})

    # ---- Load index --------------------------------------------------------
    index_path = ai_ctx / "generated" / "index.json"
    index_files: list[dict] = []
    if index_path.exists():
        try:
            index_files = json.loads(index_path.read_text(encoding="utf-8")).get("files", [])
        except Exception:  # noqa: BLE001
            pass

    # Build set of paths known to the index (relative to repo, forward-slash)
    indexed_paths: set[str] = set()
    for entry in index_files:
        rel: str = entry.get("path", "").replace("\\", "/")
        if not rel:
            continue
        indexed_paths.add(rel)
        full = repo / rel
        # E001 — index entry missing on disk
        if not full.exists():
            _add("error", "E001",
                 f"index entry exists but file not found on disk: {rel}", rel)
            continue
        # W001 — drift detection (written_hash present and mismatches)
        wh = entry.get("written_hash", "")
        if wh:
            current = _hl.sha256(full.read_text(encoding="utf-8", errors="replace")
                                  .encode()).hexdigest()[:8]
            if current != wh:
                _add("warning", "W001",
                     f"file was edited after ingest (hash {wh!r} → {current!r}): {rel}", rel)

    # ---- Scan disk for untracked generated files ---------------------------
    gen_dir = ai_ctx / "generated"
    if gen_dir.exists():
        for p in gen_dir.glob("*.md"):
            rel = str(p.relative_to(repo)).replace("\\", "/")
            if rel not in indexed_paths:
                _add("error", "E002",
                     f"file on disk has no index entry (untracked): {rel}", rel)

    # ---- Check annotations.json --------------------------------------------
    ann_path = ai_ctx / "annotations.json"
    if ann_path.exists():
        try:
            ann_data = json.loads(ann_path.read_text(encoding="utf-8"))
            for ann_rel, entries in ann_data.items():
                if not entries:
                    continue
                full = repo / ann_rel
                if not full.exists():
                    _add("warning", "W002",
                         f"annotations.json references missing file: {ann_rel}", ann_rel)
        except Exception:  # noqa: BLE001
            pass

    # ---- Check snapshots ---------------------------------------------------
    snap_dir = ai_ctx / "snapshots"
    if snap_dir.exists():
        for sp in snap_dir.glob("*.json"):
            try:
                snap = json.loads(sp.read_text(encoding="utf-8"))
                for snap_rel in snap.get("hashes", {}).keys():
                    full = repo / snap_rel
                    if not full.exists():
                        _add("warning", "W003",
                             f"snapshot '{sp.stem}' references missing file: {snap_rel}",
                             snap_rel)
            except Exception:  # noqa: BLE001
                pass

    errors   = sum(1 for i in issues if i["severity"] == "error")
    warnings = sum(1 for i in issues if i["severity"] == "warning")
    return {
        "ok":           errors == 0,
        "total_issues": len(issues),
        "errors":       errors,
        "warnings":     warnings,
        "issues":       issues,
    }


def _fmt_doc_validate(r: dict) -> None:
    if "error" in r:
        print(r["error"]); return
    status = "✓ OK" if r["ok"] else f"✗ {r['errors']} error(s)"
    print(f"{status}  ({r['warnings']} warning(s)  {r['total_issues']} total issue(s))")
    if not r["issues"]:
        print("  .ai-context/ integrity check passed.")
        return
    for issue in r["issues"]:
        icon = "✗" if issue["severity"] == "error" else "⚠"
        print(f"  {icon} [{issue['code']}] {issue['message']}")


def _doc_rename(repo: Path, old_name: str, new_name: str) -> dict:
    """Rename a curated .ai-context/ file and update annotations.json references.

    Returns:
        {ok, old_path, new_path, annotations_updated}
    or {'error': ...}
    """
    ai_ctx = repo / ".ai-context"
    cur_dir = ai_ctx / "curated"
    if not cur_dir.exists():
        return {"error": "no .ai-context/curated/ directory — nothing to rename"}

    # Resolve old file
    old_md = new_name if new_name.endswith(".md") else f"{new_name}.md"  # used later
    old_stem = old_name.removesuffix(".md") if old_name.endswith(".md") else old_name

    # Find matching curated file (partial, case-insensitive)
    old_path: Path | None = None
    for p in sorted(cur_dir.glob("*.md")):
        if old_stem.lower() in p.stem.lower():
            old_path = p
            break
    if old_path is None:
        return {"error": f"no curated file matching '{old_name}' in .ai-context/curated/"}

    # Build new path
    new_stem = new_name.removesuffix(".md") if new_name.endswith(".md") else new_name
    new_path = cur_dir / f"{new_stem}.md"
    if new_path.exists() and new_path != old_path:
        return {"error": f"target file already exists: {new_path.name}"}

    old_rel = str(old_path.relative_to(repo)).replace("\\", "/")
    new_rel = str(new_path.relative_to(repo)).replace("\\", "/")

    # Rename on disk
    old_path.rename(new_path)

    # Update annotations.json
    ann_path = ai_ctx / "annotations.json"
    ann_updated = 0
    if ann_path.exists():
        try:
            ann_data = json.loads(ann_path.read_text(encoding="utf-8"))
            if old_rel in ann_data:
                ann_data[new_rel] = ann_data.pop(old_rel)
                ann_updated = len(ann_data[new_rel])
                ann_path.write_text(
                    json.dumps(ann_data, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
        except Exception:  # noqa: BLE001
            pass

    return {
        "ok":                  True,
        "old_path":            old_rel,
        "new_path":            new_rel,
        "annotations_updated": ann_updated,
    }


def _doc_ingest_watch_tick(
    repo: Path,
    watch_dir: Path,
    state: dict[str, float],
    *,
    glob_patterns: tuple[str, ...] = ("*.md", "*.txt", "*.rst"),
    mode: str = "python",
    overwrite: bool = True,
    dry_run: bool = False,
) -> dict:
    """One sweep over watch_dir: ingest any new or modified files; update state.

    Args:
        state: mutated in place — maps relpath → last-seen mtime.

    Returns {scanned, ingested[], skipped[], errors[]} where each list contains
    per-file dicts.
    """
    if not watch_dir.is_dir():
        return {"error": f"not a directory: {watch_dir}"}

    seen: set[Path] = set()
    candidates: list[Path] = []
    for pat in glob_patterns:
        for p in sorted(watch_dir.glob(pat)):
            if p.is_file() and p not in seen:
                seen.add(p)
                candidates.append(p)

    ingested: list[dict] = []
    skipped:  list[dict] = []
    errors:   list[dict] = []

    for p in candidates:
        rel = str(p.resolve())
        try:
            mtime = p.stat().st_mtime
        except OSError:
            continue

        prev = state.get(rel)
        if prev is not None and abs(prev - mtime) < 1e-6:
            skipped.append({"path": rel, "reason": "unchanged-mtime"})
            continue

        # File is new or modified — ingest with --if-changed so the doc-hash
        # layer dedups when mtime changed but content didn't.
        try:
            res = ingest_document(
                repo,
                p,
                overwrite=overwrite,
                dry_run=dry_run,
                update_claude_md=False,
                mode=mode,
                if_changed=True,
            )
        except Exception as exc:  # noqa: BLE001
            errors.append({"path": rel, "error": str(exc)})
            continue

        if "error" in res:
            errors.append({"path": rel, "error": res["error"]})
            continue

        # Always update state on a successful sweep — even if doc-hash skip
        # fired, we don't want to keep retrying every tick.
        state[rel] = mtime
        if res.get("unchanged"):
            skipped.append({"path": rel, "reason": "unchanged-content"})
        else:
            ingested.append({
                "path":           rel,
                "files_written":  res.get("files_written", 0),
                "memories_added": res.get("memories_added", 0),
            })

    return {
        "scanned":  len(candidates),
        "ingested": ingested,
        "skipped":  skipped,
        "errors":   errors,
    }


def _doc_touch(
    repo: Path,
    name: str,
    *,
    reason: str = "",
    author: str = "",
) -> dict:
    """One-shot 'needs review' annotation wrapper.

    Quick way to flag a curated/generated file for follow-up without writing a
    full annotate command. The note text is fixed to "needs review[: <reason>]"
    so reviewers can grep for it consistently.
    """
    note = f"needs review: {reason}" if reason else "needs review"
    return _doc_annotate(repo, name, add_note=note, author=author)


def _doc_copy(repo: Path, source_name: str, new_name: str) -> dict:
    """Duplicate a curated .ai-context/ file under a new name (annotations not copied).

    Returns:
        {ok, source_path, new_path}
    or {'error': ...}
    """
    cur_dir = repo / ".ai-context" / "curated"
    if not cur_dir.exists():
        return {"error": "no .ai-context/curated/ directory — nothing to copy"}

    src_stem = source_name.removesuffix(".md") if source_name.endswith(".md") else source_name

    src_path: Path | None = None
    for p in sorted(cur_dir.glob("*.md")):
        if src_stem.lower() in p.stem.lower():
            src_path = p
            break
    if src_path is None:
        return {"error": f"no curated file matching '{source_name}' in .ai-context/curated/"}

    new_stem = new_name.removesuffix(".md") if new_name.endswith(".md") else new_name
    new_path = cur_dir / f"{new_stem}.md"
    if new_path.exists():
        return {"error": f"target file already exists: {new_path.name}"}

    new_path.write_text(src_path.read_text(encoding="utf-8"), encoding="utf-8")

    return {
        "ok":          True,
        "source_path": str(src_path.relative_to(repo)).replace("\\", "/"),
        "new_path":    str(new_path.relative_to(repo)).replace("\\", "/"),
    }


def cmd_doc(args) -> int:
    if args.doc_cmd == "ingest":
        repo = _resolve_repo(args.repo)
        # Note: _not_indexed check intentionally removed — ingest_document auto-inits
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
        # --verify: run doc check immediately after ingest
        if getattr(args, "verify", False) and "error" not in result and not result.get("dry_run"):
            check = _doc_check(repo)
            result["health_check"] = check
        _emit(result, args.json, formatter=_fmt_ingest)
        return 0 if "error" not in result else 2

    if args.doc_cmd == "check":
        repo = _resolve_repo(args.repo)
        result = _doc_check(repo)
        _emit(result, args.json, formatter=_fmt_doc_check)
        return 0 if "error" not in result and result.get("errors", 0) == 0 else 2

    if args.doc_cmd == "ingest-batch":
        repo = _resolve_repo(args.repo)
        # Note: no _not_indexed check — ingest_document auto-inits the scope store
        batch_dir = Path(args.directory).resolve()
        if not batch_dir.is_dir():
            print(f"error: {batch_dir} is not a directory", file=sys.stderr)
            return 2

        # Collect matching files
        patterns = [p.strip() for p in args.glob.split(",") if p.strip()]
        doc_paths: list[Path] = []
        seen: set[Path] = set()
        for pat in patterns:
            for p in sorted(batch_dir.glob(pat)):
                if p.is_file() and p not in seen:
                    seen.add(p)
                    doc_paths.append(p)

        if not doc_paths:
            print(f"no files matching {args.glob!r} found in {batch_dir}", file=sys.stderr)
            return 2

        results: list[dict] = []
        total_files_written   = 0
        total_memories_added  = 0
        total_templates       = 0
        docs_ingested         = 0
        docs_skipped          = 0
        docs_errored          = 0

        for doc_path in doc_paths:
            if not args.json:
                print(f"  → {doc_path.name} …", end=" ", flush=True)
            res = ingest_document(
                repo,
                doc_path,
                overwrite=args.overwrite,
                dry_run=False,
                update_claude_md=not args.no_claude_md,
                mode=args.mode,
                ollama_model=args.ollama_model,
                ollama_url=args.ollama_url,
                if_changed=args.if_changed,
            )
            results.append(res)

            if "error" in res:
                docs_errored += 1
                if not args.json:
                    print(f"ERROR: {res['error']}")
                if args.stop_on_error:
                    break
            elif res.get("unchanged"):
                docs_skipped += 1
                if not args.json:
                    print("unchanged")
            else:
                docs_ingested += 1
                total_files_written  += res.get("files_written", 0)
                total_memories_added += res.get("memories_added", 0)
                total_templates      += len(res.get("templates_created", []))
                if not args.json:
                    print(f"✓  ({res.get('files_written',0)} files, "
                          f"{res.get('memories_added',0)} memories)")

        batch_result = {
            "total_docs":              len(doc_paths),
            "docs_ingested":           docs_ingested,
            "docs_skipped_unchanged":  docs_skipped,
            "docs_errored":            docs_errored,
            "total_files_written":     total_files_written,
            "total_memories_added":    total_memories_added,
            "total_templates_created": total_templates,
            "results":                 results,
        }
        _emit(batch_result, args.json, formatter=_fmt_batch_ingest)
        return 0 if docs_errored == 0 else 1

    if args.doc_cmd == "rebuild":
        repo = _resolve_repo(args.repo)
        # Note: no _not_indexed check — ingest_document auto-inits
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
        result = _doc_export(
            repo,
            layer=args.layer,
            include_header=not args.no_header,
            tag_filter=args.tag,
        )
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
        if "error" not in result:
            # --pinned filter
            if getattr(args, "pinned", False):
                pinned = _read_pinned(repo)
                result["generated"] = [f for f in result.get("generated", [])
                                       if f["path"] in pinned]
                result["curated"]   = [f for f in result.get("curated", [])
                                       if f["path"] in pinned]
                result["total"]     = len(result["generated"]) + len(result["curated"])
            # --tag filter
            tag_filter = getattr(args, "tag", None)
            if tag_filter:
                index_files: list[dict] = []
                idx_path = repo / ".ai-context" / "generated" / "index.json"
                if idx_path.exists():
                    try:
                        index_files = json.loads(
                            idx_path.read_text(encoding="utf-8")
                        ).get("files", [])
                    except Exception:  # noqa: BLE001
                        pass
                ann_data = _load_annotations(repo)
                result["generated"] = [
                    f for f in result.get("generated", [])
                    if tag_filter in _get_file_tags(repo, f["path"], "generated",
                                                    index_files, ann_data)
                ]
                result["curated"] = [
                    f for f in result.get("curated", [])
                    if tag_filter in _get_file_tags(repo, f["path"], "curated",
                                                    index_files, ann_data)
                ]
                result["total"] = len(result["generated"]) + len(result["curated"])
        _emit(result, args.json, formatter=_fmt_doc_list)
        return 0 if "error" not in result else 2

    if args.doc_cmd == "section":
        repo = _resolve_repo(args.repo)
        result = _doc_fetch_section(repo, args.name, args.heading)
        _emit(result, args.json, formatter=_fmt_doc_fetch)
        return 0 if "error" not in result else 2

    if args.doc_cmd == "fetch":
        repo = _resolve_repo(args.repo)
        if getattr(args, "section", None):
            result = _doc_fetch_section(repo, args.name, args.section)
        else:
            result = _doc_fetch(repo, args.name)
        _emit(result, args.json, formatter=_fmt_doc_fetch)
        return 0 if "error" not in result else 2

    if args.doc_cmd == "search":
        repo = _resolve_repo(args.repo)
        result = _doc_search(repo, args.query,
                             layer=args.layer, context_lines=args.context,
                             use_regex=getattr(args, "regex", False),
                             tag_filter=getattr(args, "tag", None))
        _emit(result, args.json, formatter=_fmt_doc_search)
        return 0 if "error" not in result else 2

    if args.doc_cmd == "annotate":
        repo = _resolve_repo(args.repo)
        result = _doc_annotate(
            repo,
            args.file_id,
            add_note=getattr(args, "add_note", None),
            author=getattr(args, "author", ""),
            clear=getattr(args, "clear", False),
        )
        _emit(result, args.json, formatter=_fmt_doc_annotate)
        return 0 if "error" not in result else 2

    if args.doc_cmd == "outline":
        repo = _resolve_repo(args.repo)
        result = _doc_outline(repo, args.name)
        _emit(result, args.json, formatter=_fmt_doc_outline)
        return 0 if "error" not in result else 2

    if args.doc_cmd == "tag":
        repo = _resolve_repo(args.repo)
        result = _doc_tag(
            repo,
            args.file_id,
            add_tags=getattr(args, "add_tags", None),
            remove_tags=getattr(args, "remove_tags", None),
            clear=getattr(args, "clear", False),
        )
        if args.json:
            print(json.dumps(result, indent=2))
        elif "error" in result:
            print(result["error"], file=sys.stderr)
        else:
            tags_str = ", ".join(result["tags"]) if result["tags"] else "(none)"
            print(f"[{result['layer']}] {result['id']}  tags: {tags_str}")
        return 0 if "error" not in result else 2

    if args.doc_cmd == "report":
        repo = _resolve_repo(args.repo)
        result = _doc_report(repo)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif "error" in result:
            print(result["error"], file=sys.stderr)
        elif args.output == "-":
            _fmt_doc_report(result)
        else:
            out = Path(args.output)
            out.write_text(_fmt_doc_report_to_str(result), encoding="utf-8")
            print(f"report written to {out}", file=sys.stderr)
        return 0 if "error" not in result else 2

    if args.doc_cmd == "snapshot":
        repo = _resolve_repo(args.repo)
        sc = args.snap_cmd
        if sc == "save":
            result = _doc_snapshot_save(repo, args.name)
            if args.json:
                print(json.dumps(result, indent=2))
            elif "error" in result:
                print(result["error"], file=sys.stderr)
            else:
                print(f"snapshot saved: '{result['name']}'  "
                      f"({result['total_files']} files)  → {result['path']}")
            return 0 if "error" not in result else 2
        if sc == "list":
            result = _doc_snapshot_list(repo)
            _emit(result, args.json, formatter=_fmt_snapshot_list)
            return 0
        if sc == "delete":
            result = _doc_snapshot_delete(repo, args.name)
            if args.json:
                print(json.dumps(result, indent=2))
            elif "error" in result:
                print(result["error"], file=sys.stderr)
            else:
                print(f"deleted snapshot: '{result['name']}'")
            return 0 if "error" not in result else 2
        print(f"unknown snapshot subcommand: {sc}", file=sys.stderr)
        return 2

    if args.doc_cmd == "diff":
        repo = _resolve_repo(args.repo)
        since = getattr(args, "since", None)
        if since:
            result = _doc_diff_since(repo, since)
            _emit(result, args.json, formatter=_fmt_doc_diff_since)
        else:
            result = _doc_diff(repo)
            _emit(result, args.json, formatter=_fmt_doc_diff)
        return 0 if "error" not in result and not result.get("has_changes") else \
               1 if "error" not in result else 2

    if args.doc_cmd == "pin":
        repo = _resolve_repo(args.repo)
        result = _doc_pin(repo, args.file_id)
        if args.json:
            print(json.dumps(result, indent=2))
        elif "error" in result:
            print(result["error"], file=sys.stderr)
        elif result.get("already_pinned"):
            print(f"already pinned: {result['id']}  ({result['path']})")
        else:
            print(f"pinned: {result['id']}  ({result['path']})")
            print(f"  → {result['note']}")
        return 0 if "error" not in result else 2

    if args.doc_cmd == "unpin":
        repo = _resolve_repo(args.repo)
        result = _doc_unpin(repo, args.file_id)
        if args.json:
            print(json.dumps(result, indent=2))
        elif "error" in result:
            print(result["error"], file=sys.stderr)
        elif result.get("not_pinned"):
            print(f"not pinned: {result['id']}  ({result['path']})")
        else:
            print(f"unpinned: {result['id']}  ({result['path']})")
            print(f"  → {result['note']}")
        return 0 if "error" not in result else 2

    if args.doc_cmd == "fetch-for":
        repo = _resolve_repo(args.repo)
        result = _doc_fetch_for(
            repo,
            args.feature,
            include_memories=not args.no_memories,
            include_scope=not args.no_scope,
        )
        _emit(result, args.json, formatter=_fmt_doc_fetch_for)
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

    if args.doc_cmd == "validate":
        repo = _resolve_repo(args.repo)
        result = _doc_validate(repo)
        _emit(result, args.json, formatter=_fmt_doc_validate)
        return 0 if ("error" not in result and result.get("ok", False)) else \
               1 if "error" not in result else 2

    if args.doc_cmd == "rename":
        repo = _resolve_repo(args.repo)
        result = _doc_rename(repo, args.old, args.new)
        if args.json:
            print(json.dumps(result, indent=2))
        elif "error" in result:
            print(result["error"], file=sys.stderr)
        else:
            print(f"renamed: {result['old_path']}  →  {result['new_path']}")
            if result["annotations_updated"]:
                print(f"  {result['annotations_updated']} annotation(s) re-linked")
        return 0 if "error" not in result else 2

    if args.doc_cmd == "copy":
        repo = _resolve_repo(args.repo)
        result = _doc_copy(repo, args.source, args.new)
        if args.json:
            print(json.dumps(result, indent=2))
        elif "error" in result:
            print(result["error"], file=sys.stderr)
        else:
            print(f"copied: {result['source_path']}  →  {result['new_path']}")
        return 0 if "error" not in result else 2

    if args.doc_cmd == "llm-probe":
        from .core.llm_client import probe_file_path
        result = probe_file_path(args.file, url=args.url, model=args.model)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"file path: {result['path_tried']}")
            print(f"  can_read_path:    {result['can_read_path']}  "
                  f"(Ollama has no built-in path API — you must pass content)")
            print(f"  can_read_content: {result['can_read_content']}  "
                  f"(model={result['model']}, bytes_sent={result['bytes_sent']})")
            if result.get("error"):
                print(f"  error: {result['error']}", file=sys.stderr)
            elif result.get("llm_response"):
                print(f"  llm classified as: {result['llm_response'].get('type','?')}")
        return 0 if not result.get("error") else 2

    if args.doc_cmd == "touch":
        repo = _resolve_repo(args.repo)
        result = _doc_touch(repo, args.name, reason=args.reason, author=args.author)
        _emit(result, args.json, formatter=_fmt_doc_annotate)
        return 0 if "error" not in result else 2

    if args.doc_cmd == "ingest-watch":
        import time as _time
        repo = _resolve_repo(args.repo)
        watch_dir = Path(args.directory).resolve()
        if not watch_dir.is_dir():
            print(f"error: {watch_dir} is not a directory", file=sys.stderr)
            return 2

        glob_patterns = tuple(p.strip() for p in args.glob.split(",") if p.strip())
        state: dict[str, float] = {}

        def _run_sweep(sweep_idx: int) -> dict:
            res = _doc_ingest_watch_tick(
                repo, watch_dir, state,
                glob_patterns=glob_patterns,
                mode=args.mode,
                overwrite=not args.no_overwrite,
                dry_run=args.dry_run,
            )
            if args.json:
                print(json.dumps({"sweep": sweep_idx, **res}, ensure_ascii=False))
            else:
                if "error" in res:
                    print(res["error"], file=sys.stderr)
                else:
                    n_in = len(res["ingested"]); n_sk = len(res["skipped"]); n_er = len(res["errors"])
                    if n_in or n_er or sweep_idx == 1:
                        print(f"  sweep {sweep_idx}: scanned={res['scanned']}  "
                              f"ingested={n_in}  skipped={n_sk}  errors={n_er}",
                              file=sys.stderr)
                    for entry in res["ingested"]:
                        print(f"    + {Path(entry['path']).name}  "
                              f"files_written={entry['files_written']}",
                              file=sys.stderr)
                    for entry in res["errors"]:
                        print(f"    ! {Path(entry['path']).name}: {entry['error']}",
                              file=sys.stderr)
            return res

        if not args.json:
            print(f"watching {watch_dir}  glob={args.glob}  "
                  f"interval={args.interval}s  mode={args.mode}",
                  file=sys.stderr)

        sweep_idx = 0
        try:
            while True:
                sweep_idx += 1
                _run_sweep(sweep_idx)
                if args.once:
                    return 0
                _time.sleep(max(0.05, args.interval))
        except KeyboardInterrupt:
            if not args.json:
                print(f"\nstopped after {sweep_idx} sweep(s).", file=sys.stderr)
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
            half_life_days=getattr(args, "half_life_days", None),
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

    if mc == "federation":
        fc = args.fed_cmd
        if fc == "add":
            result = federation_add(args.path, args.alias)
            if args.json:
                print(json.dumps(result, indent=2))
            elif "error" in result:
                print(result["error"], file=sys.stderr)
            else:
                print(f"registered: {result['alias']}  →  {result['path']}"
                      + (f"  ({result['note']})" if result.get("note") else ""))
            return 0 if "error" not in result else 2

        if fc == "remove":
            result = federation_remove(args.alias)
            if args.json:
                print(json.dumps(result, indent=2))
            elif "error" in result:
                print(result["error"], file=sys.stderr)
            else:
                print(f"removed: {result['removed']}")
            return 0 if "error" not in result else 2

        if fc == "link":
            result = federation_link(args.from_alias, args.to_alias, args.scope)
            if args.json:
                print(json.dumps(result, indent=2))
            elif "error" in result:
                print(result["error"], file=sys.stderr)
            else:
                note = f"  ({result['note']})" if result.get("note") else ""
                print(f"linked: {result['from']} → {result['to']}  scope={result['scope']}{note}")
            return 0 if "error" not in result else 2

        if fc == "list":
            result = federation_list()
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                repos = result["repos"]
                links = result["links"]
                print(f"federation manifest: {result['manifest_path']}")
                print(f"\nrepos ({len(repos)}):")
                for r in repos:
                    print(f"  {r['alias']:<20} {r['path']}")
                print(f"\nlinks ({len(links)}):")
                for lk in links:
                    print(f"  {lk['from']:<20} → {lk['to']:<20}  scope={lk['scope']}")
                if not repos:
                    print("  (none — add repos with `scope mem federation add <path> --alias <a>`)")
            return 0

        if fc == "fetch":
            repo = _resolve_repo(args.repo)
            result = federated_fetch(
                repo,
                feature=args.feature,
                file=args.file,
                symbol=args.symbol,
            )
            if args.json:
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                local = result.get("local_alias") or "(not in federation)"
                print(f"federation fetch for '{local}': {result['total_remote']} remote entries")
                for src in result.get("sources", []):
                    status = f"error: {src['error']}" if src.get("error") else \
                             f"{len(src['entries'])} entries"
                    print(f"  [{src['alias']}] {status}")
                if result.get("note"):
                    print(f"  note: {result['note']}", file=sys.stderr)
            return 0

        print(f"unknown federation subcommand: {fc}", file=sys.stderr)
        return 2

    if mc == "capture":
        result = capture_memory(
            repo,
            signal=args.signal,
            evidence=args.evidence,
            feature=args.feature,
            file=args.capture_file,
            symbol=args.symbol,
            author=args.author,
            dry_run=args.dry_run,
        )
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif result.get("rate_limited"):
            print(result["error"], file=sys.stderr)
        elif "error" in result:
            print(result["error"], file=sys.stderr)
        elif result.get("dry_run"):
            print(f"[dry-run] would capture: [{result['would_capture']['type']}] "
                  f"{result['would_capture']['note'][:80]}")
        else:
            print(f"captured [{result['type']}] {result['id']}  "
                  f"signal={args.signal}  {result['note'][:60]}")
        return 0 if "error" not in result else 2

    if mc == "touch":
        result = touch_memory(repo, args.id)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif "error" in result:
            print(result["error"], file=sys.stderr)
        else:
            eff = result.get("effective_confidence", result.get("confidence", "?"))
            hist = len(result.get("reinforced_at", []))
            print(f"reinforced: {result['id']}  base={result.get('confidence','?')}  "
                  f"reinforcements={hist}")
        return 0 if "error" not in result else 2

    if mc == "prune":
        result = prune_memories(
            repo,
            below=args.below,
            dry_run=args.dry_run,
            half_life_days=getattr(args, "half_life_days", None),
        )
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif "error" in result:
            print(result["error"], file=sys.stderr)
        else:
            label = "[dry-run] would remove" if result["dry_run"] else "pruned"
            print(f"{label} {len(result['removed'])} semantic memories "
                  f"(effective_confidence < {result['threshold']:.2f})  "
                  f"kept={result['kept']}")
            for r in result["removed"]:
                print(f"  {r['id']}  eff={r['effective_confidence']:.4f}  {r['note'][:60]}")
        return 0 if "error" not in result else 2

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
    "graph":       cmd_graph,
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
