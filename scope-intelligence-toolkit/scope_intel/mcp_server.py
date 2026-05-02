"""MCP stdio server — JSON-RPC 2.0 over stdin/stdout.

Exposes all scope query operations as MCP tools. Zero external dependencies.

Protocol flow:
  client → initialize        server → result (capabilities)
  client → initialized       (notification, no response)
  client → tools/list        server → result (tool schemas)
  client → tools/call        server → result (tool output)

Each JSON-RPC message is a single newline-terminated line.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .core.diff import compute_diff_scope
from .core.mempalace import (
    add_memory,
    auto_capture_from_git,
    capture_memory,
    compute_churn,
    decay_confidence,
    detect_conflicts,
    export_memories,
    fetch_relevant,
    import_memories,
    list_memories,
    prune_memories,
    search_memories,
    touch_memory,
)
from .core.federation import (
    federation_add,
    federation_list,
    federation_link,
    federation_remove,
)
from .core.compact_context import (
    build_compact_artifacts,
    compact_stats,
    get_inventory,
    validate_compact_artifacts,
)
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
from .core.tracker import compute_savings_summary

SERVER_INFO = {"name": "scope-intelligence", "version": "1.0.0"}

# ---------------------------------------------------------------------------
# Tool definitions (JSON Schema for each MCP tool)
# ---------------------------------------------------------------------------

_REPO_PROP = {
    "repo": {
        "type": "string",
        "description": "Absolute path to the repository root (default: cwd).",
    }
}

TOOLS: list[dict] = [
    {
        "name": "scope_summary",
        "description": "Repo-wide overview: file counts, languages, top features, most-imported files.",
        "inputSchema": {
            "type": "object",
            "properties": _REPO_PROP,
        },
    },
    {
        "name": "scope_inventory",
        "description": "Indexed files, classes, and symbols without reading source file bodies.",
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "feature": {"type": "string", "description": "Optional feature id filter."},
                "include_symbols": {"type": "boolean", "default": True},
            },
        },
    },
    {
        "name": "scope_features",
        "description": "List all detected features (directory-inferred logical modules).",
        "inputSchema": {
            "type": "object",
            "properties": _REPO_PROP,
        },
    },
    {
        "name": "scope_feature",
        "description": "Full scope for a single feature: files, symbols, tests, dependencies.",
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "name": {"type": "string", "description": "Feature id or alias."},
            },
            "required": ["name"],
        },
    },
    {
        "name": "scope_impacted",
        "description": "Files transitively impacted by changing a file, feature, or symbol.",
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "file": {"type": "string", "description": "Repo-relative file path."},
                "feature": {"type": "string", "description": "Feature id or alias."},
                "symbol": {"type": "string", "description": "Symbol name or qualified id."},
            },
        },
    },
    {
        "name": "scope_tests",
        "description": "Test files covering a given source file or feature.",
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "file": {"type": "string", "description": "Repo-relative file path."},
                "feature": {"type": "string", "description": "Feature id or alias."},
            },
        },
    },
    {
        "name": "scope_symbol",
        "description": "Full context for a symbol: kind, params, reads, writes, callers, callees.",
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "name": {"type": "string", "description": "Symbol name or qualified id."},
            },
            "required": ["name"],
        },
    },
    {
        "name": "scope_callers",
        "description": "All symbols that call a given symbol (cross-file resolved).",
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "name": {"type": "string", "description": "Symbol name or qualified id."},
            },
            "required": ["name"],
        },
    },
    {
        "name": "scope_callees",
        "description": "All symbols called by a given symbol (cross-file resolved).",
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "name": {"type": "string", "description": "Symbol name or qualified id."},
            },
            "required": ["name"],
        },
    },
    {
        "name": "scope_touchpoints",
        "description": "Routes, config keys, DB models, and events found in the repo.",
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "type": {
                    "type": "string",
                    "enum": ["routes", "configs", "db_models", "events"],
                    "description": "Filter to one touchpoint category.",
                },
                "feature": {"type": "string", "description": "Filter by feature id."},
                "file": {"type": "string", "description": "Filter by file path."},
            },
        },
    },
    {
        "name": "scope_diff",
        "description": "Files changed vs a git ref and their transitive impact scope.",
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "ref": {
                    "type": "string",
                    "description": "Git ref to diff against (default: HEAD~1).",
                    "default": "HEAD~1",
                },
            },
        },
    },
    {
        "name": "scope_report",
        "description": "Token savings summary across all past scope queries in the repo.",
        "inputSchema": {
            "type": "object",
            "properties": _REPO_PROP,
        },
    },
    {
        "name": "compact_build",
        "description": "Build compact DSL sidecars for .ai-context files, skills, memory, or all.",
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "target": {
                    "type": "string",
                    "enum": ["ai-context", "skills", "memory", "all"],
                    "default": "ai-context",
                },
                "overwrite": {"type": "boolean", "default": True},
            },
        },
    },
    {
        "name": "compact_validate",
        "description": "Decompress compact sidecars and verify exact payload against current originals.",
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "target": {
                    "type": "string",
                    "enum": ["ai-context", "skills", "memory", "all"],
                    "default": "all",
                },
            },
        },
    },
    {
        "name": "compact_stats",
        "description": "Token estimate summary for compact sidecars.",
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "target": {
                    "type": "string",
                    "enum": ["ai-context", "skills", "memory", "all"],
                    "default": "all",
                },
            },
        },
    },
    # --- Phase 4: MemPalace tools ---
    {
        "name": "mem_add",
        "description": (
            "Record a long-term memory scoped to files/features/symbols. "
            "Types: semantic (timeless fact, use confidence field), "
            "procedure (step-by-step workflow, use steps field), "
            "or episodic (bug/decision/failure/ownership/note/fix)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "type": {
                    "type": "string",
                    "enum": ["semantic", "procedure",
                             "bug", "decision", "failure", "ownership", "note", "fix"],
                    "description": "Memory type.",
                },
                "note": {"type": "string", "description": "The memory text or title."},
                "files": {"type": "array", "items": {"type": "string"},
                          "description": "Repo-relative file paths this concerns."},
                "features": {"type": "array", "items": {"type": "string"},
                             "description": "Feature ids this concerns."},
                "symbols": {"type": "array", "items": {"type": "string"},
                            "description": "Symbol names this concerns."},
                "tags": {"type": "array", "items": {"type": "string"}},
                "author": {"type": "string"},
                "resolved": {"type": "boolean", "default": False},
                "confidence": {
                    "type": "number", "minimum": 0.0, "maximum": 1.0, "default": 1.0,
                    "description": "Confidence level for semantic facts (0.0-1.0).",
                },
                "steps": {
                    "type": "array", "items": {"type": "string"},
                    "description": "Ordered steps for procedure memories.",
                },
            },
            "required": ["note"],
        },
    },
    {
        "name": "mem_fetch",
        "description": (
            "Fetch layered memories relevant to a feature/file/symbol. "
            "Returns four layers: structural (live scope), semantic (facts), "
            "procedural (workflows), episodic (past incidents). "
            "Uses Phase 1-3 scope engine internally to resolve exact files."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "feature": {"type": "string", "description": "Feature id or alias."},
                "file": {"type": "string", "description": "Repo-relative file path."},
                "symbol": {"type": "string", "description": "Symbol name."},
                "type": {
                    "type": "string",
                    "enum": ["semantic", "procedure",
                             "bug", "decision", "failure", "ownership", "note", "fix"],
                    "description": "Filter to one memory type.",
                },
                "include_resolved": {"type": "boolean", "default": False},
                "limit": {"type": "integer", "default": 20},
            },
        },
    },
    {
        "name": "mem_list",
        "description": "List all MemPalace entries with optional type/tag filter.",
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "type": {
                    "type": "string",
                    "enum": ["semantic", "procedure",
                             "bug", "decision", "failure", "ownership", "note", "fix"],
                },
                "tag": {"type": "string"},
                "include_resolved": {"type": "boolean", "default": True},
            },
        },
    },
    {
        "name": "mem_churn",
        "description": "Analyse git history to find high-churn files and features (change frequency).",
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "days": {"type": "integer", "default": 90,
                         "description": "Look-back window in days."},
            },
        },
    },
    # --- Doc ingest ---
    {
        "name": "doc_ingest",
        "description": (
            "Parse a design document (PDF/DOCX/MD/TXT) and generate .ai-context/ files. "
            "Produces: 16 generated/ context docs (001-project-overview … 009-schema-design, "
            "mcp-contract, roadmap, claude-code-integration, symbol-schema), "
            "3 curated/ state files (constraints, current-phase, module-map), "
            "mempalace semantic memories, and feature stubs. "
            "mode='python' uses fast regex routing (no LLM). "
            "mode='llm' uses Qwen/Ollama for per-chunk classification — "
            "richer extraction, requires Ollama running at ollama_url. "
            "second_pass=true adds a synthesis pass to generate module-map.md."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "doc": {
                    "type": "string",
                    "description": "Absolute path to the design document.",
                },
                "mode": {
                    "type": "string",
                    "enum": ["python", "llm"],
                    "default": "python",
                    "description": "'python' = fast regex (default). 'llm' = Qwen classification.",
                },
                "ollama_model": {
                    "type": "string",
                    "default": "qwen2.5:7b",
                    "description": "Ollama model for mode=llm (default: qwen2.5:7b).",
                },
                "ollama_url": {
                    "type": "string",
                    "default": "http://localhost:11434",
                    "description": "Ollama server URL (default: http://localhost:11434).",
                },
                "overwrite": {
                    "type": "boolean",
                    "default": False,
                    "description": "Regenerate files that already exist.",
                },
                "dry_run": {
                    "type": "boolean",
                    "default": False,
                    "description": "Parse and report without writing anything.",
                },
                "second_pass": {
                    "type": "boolean",
                    "default": False,
                    "description": "Run second Qwen pass to synthesise module-map.md (mode=llm only).",
                },
                "update_claude_md": {
                    "type": "boolean",
                    "default": True,
                    "description": "Append scope-intel section to CLAUDE.md.",
                },
            },
            "required": ["doc"],
        },
    },
    {
        "name": "doc_list",
        "description": (
            "List all .ai-context/ files generated for this repo — "
            "generated/ docs (numbered architecture files + named extras) "
            "and curated/ state files (constraints, current-phase, module-map). "
            "Returns source document name, generation timestamp, and mode used."
        ),
        "inputSchema": {
            "type": "object",
            "properties": _REPO_PROP,
        },
    },
    {
        "name": "doc_fetch",
        "description": (
            "Retrieve the full markdown content of a specific .ai-context/ file "
            "by id or partial name. Examples: 'overview', '002', 'constraints', "
            "'memory'. Returns file content, path, and layer (generated | curated)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "name": {
                    "type": "string",
                    "description": (
                        "File id or partial name to match against .ai-context/ files. "
                        "Use doc_list to see available ids."
                    ),
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "doc_search",
        "description": (
            "Search all .ai-context/ files for a keyword, phrase, or regex pattern "
            "(case-insensitive). Returns matching lines with surrounding context. "
            "Useful for finding which generated context file contains information "
            "about a specific topic."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "query": {
                    "type": "string",
                    "description": "Keyword, phrase, or regex pattern to search for.",
                },
                "layer": {
                    "type": "string",
                    "enum": ["generated", "curated", "all"],
                    "default": "all",
                    "description": "Which layer to search (default: all).",
                },
                "context": {
                    "type": "integer",
                    "default": 2,
                    "description": "Lines of context around each match (default: 2).",
                },
                "use_regex": {
                    "type": "boolean",
                    "default": False,
                    "description": "Treat query as a regex pattern (default: false = literal).",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "doc_check",
        "description": (
            "Validate the .ai-context/ directory health: checks index.json integrity, "
            "verifies every indexed file exists on disk, flags files that are suspiciously "
            "short, detects unfilled TODO placeholders in curated files, and warns if "
            "the source document has changed since the last ingest run."
        ),
        "inputSchema": {
            "type": "object",
            "properties": _REPO_PROP,
        },
    },
    {
        "name": "doc_ingest_batch",
        "description": (
            "Ingest all design documents (PDF/DOCX/MD/TXT) in a directory, "
            "one by one, accumulating sections into .ai-context/ files. "
            "Returns per-file results and aggregated totals."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "directory": {
                    "type": "string",
                    "description": "Absolute path to the directory containing design docs.",
                },
                "glob": {
                    "type": "string",
                    "default": "*.pdf,*.docx,*.md,*.txt",
                    "description": "Comma-separated glob patterns (default: *.pdf,*.docx,*.md,*.txt).",
                },
                "overwrite": {"type": "boolean", "default": False},
                "if_changed": {
                    "type": "boolean",
                    "default": False,
                    "description": "Skip files whose hash matches the stored hash.",
                },
                "mode": {
                    "type": "string",
                    "enum": ["python", "llm"],
                    "default": "python",
                },
                "stop_on_error": {
                    "type": "boolean",
                    "default": False,
                    "description": "Abort batch on first error (default: log and continue).",
                },
            },
            "required": ["directory"],
        },
    },
    {
        "name": "doc_stats",
        "description": (
            "Show character and estimated token counts for every .ai-context/ file. "
            "Use this to understand how much context budget the generated docs consume "
            "before deciding which files to pass to Claude."
        ),
        "inputSchema": {
            "type": "object",
            "properties": _REPO_PROP,
        },
    },
    {
        "name": "doc_export",
        "description": (
            "Concatenate all .ai-context/ files into a single text blob. "
            "Useful for inserting the full design context into a prompt window "
            "or sharing with a team. Returns {content, total_files, total_tokens}."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "layer": {
                    "type": "string",
                    "enum": ["generated", "curated", "all"],
                    "default": "all",
                    "description": "Which layer to include (default: all).",
                },
                "include_header": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include export header comment (default: true).",
                },
            },
        },
    },
    {
        "name": "doc_tag",
        "description": (
            "Add, remove, or clear free-form tags on a .ai-context/ file. "
            "Tags let you group files (e.g. 'api', 'auth', 'reviewed') for filtered listing. "
            "Call doc_list with tag filter to find tagged files."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "file_id": {
                    "type": "string",
                    "description": "File id or partial name.",
                },
                "add_tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags to add.",
                },
                "remove_tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags to remove.",
                },
                "clear": {
                    "type": "boolean",
                    "default": False,
                    "description": "Remove all tags from this file.",
                },
            },
            "required": ["file_id"],
        },
    },
    {
        "name": "doc_report",
        "description": (
            "Generate a comprehensive status report of the entire .ai-context/ system: "
            "file inventory with token counts, pin/annotation flags, snapshot list, "
            "health check summary, and context budget hint. "
            "Call this once at session start to orient Claude before working on a feature."
        ),
        "inputSchema": {
            "type": "object",
            "properties": _REPO_PROP,
        },
    },
    {
        "name": "doc_validate",
        "description": (
            "Check .ai-context/ integrity: orphaned index entries, untracked files on disk, "
            "post-ingest hash drift (W001), missing annotation targets (W002), "
            "and snapshot references to deleted files (W003). "
            "Returns ok=true only when there are zero errors (warnings are non-blocking). "
            "Run after any manual edit or bulk re-ingest to catch inconsistencies early."
        ),
        "inputSchema": {
            "type": "object",
            "properties": _REPO_PROP,
        },
    },
    {
        "name": "doc_rename",
        "description": (
            "Rename a curated .ai-context/ file on disk and update any annotations.json "
            "references to the new path. "
            "Use partial name or stem (e.g. 'constraints', 'api-spec'). "
            "Only works on curated/ files — generated files are managed by ingest."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "old": {
                    "type": "string",
                    "description": "Current name or partial stem of the curated file.",
                },
                "new": {
                    "type": "string",
                    "description": "New name (with or without .md extension).",
                },
            },
            "required": ["old", "new"],
        },
    },
    {
        "name": "doc_snapshot_save",
        "description": (
            "Save a named point-in-time snapshot of all .ai-context/ file content hashes. "
            "Use this before a rebuild or major edit so you can later diff against it. "
            "Snapshots are stored in .ai-context/snapshots/."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "name": {
                    "type": "string",
                    "description": "Snapshot name (e.g. 'v1', 'after-review', 'pre-rebuild').",
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "doc_snapshot_list",
        "description": "List all saved .ai-context/ snapshots with names and creation timestamps.",
        "inputSchema": {
            "type": "object",
            "properties": _REPO_PROP,
        },
    },
    {
        "name": "doc_diff_since",
        "description": (
            "Diff current .ai-context/ files against a named snapshot. "
            "Returns lists of: unchanged, modified, deleted (missing), added. "
            "Use doc_snapshot_save first to create a baseline."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "snapshot": {
                    "type": "string",
                    "description": "Name of the snapshot to compare against.",
                },
            },
            "required": ["snapshot"],
        },
    },
    {
        "name": "doc_section",
        "description": (
            "Extract a specific heading section from a .ai-context/ file "
            "without returning the full file content. "
            "Useful when only one section (e.g. 'Roadmap', 'Constraints') is needed "
            "from a long generated file. Returns the section text and its char count."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "name": {
                    "type": "string",
                    "description": "File id or partial name (e.g. 'roadmap', '001').",
                },
                "heading": {
                    "type": "string",
                    "description": "Heading text to match (partial, case-insensitive).",
                },
            },
            "required": ["name", "heading"],
        },
    },
    {
        "name": "doc_outline",
        "description": (
            "Return the heading hierarchy of a .ai-context/ file as a structured list. "
            "Each entry includes heading level (1-6), text, line number, and char offset. "
            "Useful for navigating large generated docs before calling doc_section."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "name": {
                    "type": "string",
                    "description": "File id or partial name (e.g. 'roadmap', '003', 'constraints').",
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "doc_annotate",
        "description": (
            "Add, view, or clear human annotations on a .ai-context/ file. "
            "Annotations are timestamped notes ('last reviewed', 'needs update for v2', etc.) "
            "stored alongside the file entry in index.json (generated) or annotations.json (curated). "
            "Call with just file_id to view existing annotations. "
            "Use add_note to record a new annotation. Use clear=true to remove all."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "file_id": {
                    "type": "string",
                    "description": "File id or partial name (e.g. 'roadmap', '003', 'constraints').",
                },
                "add_note": {
                    "type": "string",
                    "description": "Annotation text to record (omit to view existing).",
                },
                "author": {
                    "type": "string",
                    "default": "",
                    "description": "Author name or handle.",
                },
                "clear": {
                    "type": "boolean",
                    "default": False,
                    "description": "Remove all existing annotations from this file.",
                },
            },
            "required": ["file_id"],
        },
    },
    {
        "name": "doc_pin",
        "description": (
            "Pin a generated .ai-context/ file so it is never overwritten by "
            "future `doc_ingest` or `doc_rebuild` calls. "
            "Use this to protect manually-curated sections you want to keep. "
            "Run doc_list to see valid file ids."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "file_id": {
                    "type": "string",
                    "description": "File id or partial name (e.g. 'roadmap', '003', 'constraints').",
                },
            },
            "required": ["file_id"],
        },
    },
    {
        "name": "doc_unpin",
        "description": "Remove a pin from a .ai-context/ file, allowing future ingest to overwrite it.",
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "file_id": {
                    "type": "string",
                    "description": "File id or partial name to unpin.",
                },
            },
            "required": ["file_id"],
        },
    },
    {
        "name": "doc_diff",
        "description": (
            "Compare current .ai-context/ file contents against the hashes recorded "
            "at ingest time. Returns lists of: unchanged (hash matches), modified "
            "(manually edited since ingest), missing (deleted), and extra (not in index). "
            "Useful before a rebuild to see what manual edits exist."
        ),
        "inputSchema": {
            "type": "object",
            "properties": _REPO_PROP,
        },
    },
    {
        "name": "doc_fetch_for_feature",
        "description": (
            "Return a unified context bundle for a specific feature: "
            "matching .ai-context/ files, design-doc excerpts mentioning the feature, "
            "relevant MemPalace memories, and scope-index file list. "
            "One-shot call to prime Claude with everything it needs to work on a feature."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "feature": {
                    "type": "string",
                    "description": (
                        "Feature name or slug (e.g. 'memory-layer', 'rag', 'auth'). "
                        "Will be normalised to a slug for filename matching."
                    ),
                },
                "include_memories": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include relevant MemPalace entries (default: true).",
                },
                "include_scope": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include scope-index feature files/tests (default: true).",
                },
            },
            "required": ["feature"],
        },
    },
    # --- Phase 5 tools ---
    {
        "name": "mem_auto_capture",
        "description": (
            "Scan recent git log and auto-create episodic memories for bug-fix, "
            "decision, and feature commits. Skips already-captured commits."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "days": {"type": "integer", "default": 30,
                         "description": "Days of git history to scan."},
                "dry_run": {"type": "boolean", "default": False,
                            "description": "Preview without writing."},
            },
        },
    },
    {
        "name": "mem_decay",
        "description": (
            "Apply exponential confidence decay to semantic memories. "
            "Confidence halves every `half_life_days` days, floored at `floor`."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "half_life_days": {"type": "integer", "default": 90},
                "floor": {"type": "number", "default": 0.1},
                "dry_run": {"type": "boolean", "default": False},
            },
        },
    },
    {
        "name": "mem_search",
        "description": "TF-IDF free-text search over all memory notes. Returns ranked results.",
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "query": {"type": "string", "description": "Free-text search query."},
                "type": {
                    "type": "string",
                    "enum": ["semantic", "procedure",
                             "bug", "decision", "failure", "ownership", "note", "fix"],
                },
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "mem_export",
        "description": "Export all MemPalace entries to a portable JSON file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "output": {"type": "string", "default": "mempalace_export.json",
                           "description": "Output file path."},
            },
        },
    },
    {
        "name": "mem_import",
        "description": "Import memories from a portable JSON file (merge by default).",
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "file": {"type": "string", "description": "Path to exported JSON file."},
                "replace": {"type": "boolean", "default": False,
                            "description": "Replace existing mempalace instead of merging."},
            },
            "required": ["file"],
        },
    },
    {
        "name": "mem_conflicts",
        "description": "Detect potentially contradicting semantic memories in the same scope.",
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "include_resolved": {"type": "boolean", "default": False},
            },
        },
    },
    {
        "name": "mem_capture",
        "description": (
            "Agent-triggered memory capture. Records a high-signal event detected during a session. "
            "Caps confidence at 0.7 and rate-limits to prevent spam. "
            "Valid signals: repeated-error, validated-claim, perf-regression, security-note, arch-decision."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "signal":   {"type": "string", "description": "Signal type (e.g. repeated-error, validated-claim)."},
                "evidence": {"type": "string", "description": "Text to record as the memory note."},
                "feature":  {"type": "string", "description": "Feature scope hint (optional)."},
                "file":     {"type": "string", "description": "File scope hint (optional)."},
                "symbol":   {"type": "string", "description": "Symbol scope hint (optional)."},
                "author":   {"type": "string", "default": "agent"},
                "dry_run":  {"type": "boolean", "default": False},
            },
            "required": ["signal", "evidence"],
        },
    },
    {
        "name": "mem_touch",
        "description": "Reinforce a memory by refreshing its timestamp. Resets decay so effective confidence jumps back to its base value.",
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "id": {"type": "string", "description": "Memory ID to touch."},
            },
            "required": ["id"],
        },
    },
    {
        "name": "mem_prune",
        "description": "Delete semantic memories whose effective confidence has decayed below a threshold. Non-semantic entries are never pruned.",
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "below":          {"type": "number", "default": 0.2, "description": "Prune entries with effective_confidence below this value."},
                "dry_run":        {"type": "boolean", "default": False},
                "half_life_days": {"type": "integer", "description": "Override the repo default half-life (optional)."},
            },
        },
    },
    {
        "name": "scope_graph",
        "description": (
            "Generate a Mermaid or DOT diagram from the scope index. "
            "kind=class → classDiagram (classes, methods, inheritance);  "
            "kind=deps → import dependency graph (file → file);  "
            "kind=calls → call graph (callers → symbol → callees)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                **_REPO_PROP,
                "query":  {"type": "string", "description": "Feature id, file path, or symbol name."},
                "target": {"type": "string", "enum": ["feature", "file", "symbol"],
                           "default": "feature"},
                "kind":   {"type": "string", "enum": ["class", "deps", "calls"],
                           "default": "class"},
                "format": {"type": "string", "enum": ["mermaid", "dot"],
                           "default": "mermaid"},
                "max_nodes": {"type": "integer", "default": 60},
            },
            "required": ["query"],
        },
    },
    {
        "name": "mem_federation",
        "description": (
            "Manage the cross-repo federation registry. "
            "action='list' returns all repos and links. "
            "action='add' registers a new repo. "
            "action='remove' deregisters a repo. "
            "action='link' creates a directional memory link between two repos."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list", "add", "remove", "link"],
                           "description": "Operation to perform."},
                "path":   {"type": "string", "description": "Repo path (required for action=add)."},
                "alias":  {"type": "string", "description": "Repo alias (required for action=add/remove/link)."},
                "to":     {"type": "string", "description": "Target alias (required for action=link)."},
                "scope":  {"type": "string", "default": "all",
                           "description": "Memory scope for link: all | semantic | procedure | episodic."},
            },
            "required": ["action"],
        },
    },
]


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def _repo(args: dict) -> Path:
    return Path(args.get("repo", ".")).resolve()


def _call_tool(name: str, arguments: dict) -> dict:
    repo = _repo(arguments)

    if name == "scope_summary":
        return get_repo_summary(repo)
    if name == "scope_inventory":
        return get_inventory(
            repo,
            feature=arguments.get("feature"),
            include_symbols=arguments.get("include_symbols", True),
        )
    if name == "scope_features":
        from .core import store
        return store.read_json(repo, "features", {"features": []})
    if name == "scope_feature":
        return get_feature_scope(repo, arguments["name"])
    if name == "scope_impacted":
        return find_impacted_files(
            repo,
            file=arguments.get("file"),
            feature=arguments.get("feature"),
            symbol=arguments.get("symbol"),
        )
    if name == "scope_tests":
        return get_related_tests(
            repo,
            file=arguments.get("file"),
            feature=arguments.get("feature"),
        )
    if name == "scope_symbol":
        return get_symbol_context(repo, arguments["name"])
    if name == "scope_callers":
        return get_callers(repo, arguments["name"])
    if name == "scope_callees":
        return get_callees(repo, arguments["name"])
    if name == "scope_touchpoints":
        return get_touchpoints(
            repo,
            kind=arguments.get("type"),
            feature=arguments.get("feature"),
            file=arguments.get("file"),
        )
    if name == "scope_diff":
        return compute_diff_scope(repo, arguments.get("ref", "HEAD~1"))
    if name == "scope_report":
        return compute_savings_summary(repo)
    if name == "compact_build":
        return build_compact_artifacts(
            repo,
            target=arguments.get("target", "ai-context"),
            overwrite=arguments.get("overwrite", True),
        )
    if name == "compact_validate":
        return validate_compact_artifacts(
            repo,
            target=arguments.get("target", "all"),
        )
    if name == "compact_stats":
        return compact_stats(
            repo,
            target=arguments.get("target", "all"),
        )
    if name == "scope_graph":
        from .core.graph_renderer import render_graph
        return render_graph(
            repo,
            target=arguments.get("target", "feature"),
            query=arguments["query"],
            kind=arguments.get("kind", "class"),
            format=arguments.get("format", "mermaid"),
            max_nodes=arguments.get("max_nodes", 60),
        )

    # --- Phase 4: MemPalace ---
    if name == "mem_add":
        return add_memory(
            repo,
            kind=arguments.get("type", "note"),
            note=arguments["note"],
            files=arguments.get("files", []),
            features=arguments.get("features", []),
            symbols=arguments.get("symbols", []),
            tags=arguments.get("tags", []),
            author=arguments.get("author", ""),
            resolved=arguments.get("resolved", False),
            confidence=arguments.get("confidence", 1.0),
            steps=arguments.get("steps"),
        )
    if name == "mem_fetch":
        return fetch_relevant(
            repo,
            feature=arguments.get("feature"),
            file=arguments.get("file"),
            symbol=arguments.get("symbol"),
            kind=arguments.get("type"),
            include_resolved=arguments.get("include_resolved", False),
            limit=arguments.get("limit", 20),
        )
    if name == "mem_list":
        return list_memories(
            repo,
            kind=arguments.get("type"),
            tag=arguments.get("tag"),
            include_resolved=arguments.get("include_resolved", True),
        )
    if name == "mem_churn":
        return compute_churn(repo, days=arguments.get("days", 90))
    if name == "mem_capture":
        return capture_memory(
            repo,
            arguments["signal"],
            arguments["evidence"],
            feature=arguments.get("feature"),
            file=arguments.get("file"),
            symbol=arguments.get("symbol"),
            author=arguments.get("author", "agent"),
            dry_run=arguments.get("dry_run", False),
        )
    if name == "mem_touch":
        return touch_memory(repo, arguments["id"])
    if name == "mem_prune":
        return prune_memories(
            repo,
            below=arguments.get("below", 0.2),
            dry_run=arguments.get("dry_run", False),
            half_life_days=arguments.get("half_life_days"),
        )
    if name == "mem_federation":
        action = arguments.get("action", "list")
        if action == "list":
            return federation_list()
        if action == "add":
            if not arguments.get("path") or not arguments.get("alias"):
                return {"error": "action=add requires 'path' and 'alias'"}
            return federation_add(arguments["path"], arguments["alias"])
        if action == "remove":
            if not arguments.get("alias"):
                return {"error": "action=remove requires 'alias'"}
            return federation_remove(arguments["alias"])
        if action == "link":
            if not arguments.get("alias") or not arguments.get("to"):
                return {"error": "action=link requires 'alias' (from) and 'to'"}
            return federation_link(arguments["alias"], arguments["to"],
                                   scope=arguments.get("scope", "all"))
        return {"error": f"unknown action '{action}' — valid: list, add, remove, link"}

    # --- Doc ingest / list / fetch ---
    if name == "doc_ingest":
        from .core.doc_ingestor import ingest_document
        return ingest_document(
            repo,
            Path(arguments["doc"]),
            mode=arguments.get("mode", "python"),
            ollama_model=arguments.get("ollama_model", "qwen2.5:7b"),
            ollama_url=arguments.get("ollama_url", "http://localhost:11434"),
            overwrite=arguments.get("overwrite", False),
            dry_run=arguments.get("dry_run", False),
            second_pass=arguments.get("second_pass", False),
            update_claude_md=arguments.get("update_claude_md", True),
        )
    if name == "doc_list":
        import json as _json
        index_path = repo / ".ai-context" / "generated" / "index.json"
        if not index_path.exists():
            return {"error": "no .ai-context/ found — run doc_ingest first"}
        index = _json.loads(index_path.read_text(encoding="utf-8"))
        all_files = index.get("files", [])
        generated = [f for f in all_files if f.get("layer", "generated") == "generated"]
        curated_dir = repo / ".ai-context" / "curated"
        curated = []
        if curated_dir.exists():
            for p in sorted(curated_dir.glob("*.md")):
                curated.append({
                    "id":    p.stem,
                    "path":  str(p.relative_to(repo)).replace("\\", "/"),
                    "layer": "curated",
                })
        return {
            "source":       index.get("source", "?"),
            "generated_at": index.get("generated_at", "?"),
            "mode":         index.get("mode", "?"),
            "generated":    generated,
            "curated":      curated,
            "total":        len(generated) + len(curated),
        }
    if name == "doc_fetch":
        import json as _json
        query = arguments["name"].lower()
        index_path = repo / ".ai-context" / "generated" / "index.json"
        candidates = []
        seen_paths: set = set()
        def _add_candidate(entry):
            p = entry.get("path", "")
            if p not in seen_paths:
                seen_paths.add(p)
                candidates.append(entry)
        if index_path.exists():
            index = _json.loads(index_path.read_text(encoding="utf-8"))
            for f in index.get("files", []):
                if query in f["id"].lower() or query in f.get("title", "").lower():
                    _add_candidate(f)
        curated_dir = repo / ".ai-context" / "curated"
        if curated_dir.exists():
            for p in curated_dir.glob("*.md"):
                if query in p.stem.lower():
                    _add_candidate({
                        "id":    p.stem,
                        "path":  str(p.relative_to(repo)).replace("\\", "/"),
                        "title": p.stem.replace("-", " ").title(),
                        "layer": "curated",
                    })
        if not candidates:
            return {"error": f"no file matching '{arguments['name']}'"}
        if len(candidates) > 1:
            return {"error": f"ambiguous: matches {[c['id'] for c in candidates]}"}
        hit = candidates[0]
        fp = repo / hit["path"]
        if not fp.exists():
            return {"error": f"file not found on disk: {fp}"}
        content = fp.read_text(encoding="utf-8")
        return {"id": hit["id"], "path": hit["path"],
                "title": hit.get("title", hit["id"]),
                "layer": hit.get("layer", "generated"),
                "content": content, "chars": len(content)}
    if name == "doc_search":
        import re as _re
        query = arguments["query"]
        layer = arguments.get("layer", "all")
        context_lines = int(arguments.get("context", 2))
        use_regex = arguments.get("use_regex", False)
        ai_ctx = repo / ".ai-context"
        if not ai_ctx.exists():
            return {"error": "no .ai-context/ found — run doc_ingest first"}
        try:
            raw_pat = query if use_regex else _re.escape(query)
            pattern = _re.compile(raw_pat, _re.IGNORECASE)
        except _re.error as exc:
            return {"error": f"invalid regex: {exc}"}
        results = []
        def _search(directory: Path, lyr: str) -> None:
            if not directory.exists(): return
            for p in sorted(directory.glob("*.md")):
                try:
                    lines = p.read_text(encoding="utf-8").splitlines()
                except OSError:
                    continue
                matches = []
                for i, line in enumerate(lines):
                    if pattern.search(line):
                        matches.append({
                            "line_no": i + 1,
                            "line": line,
                            "context_before": lines[max(0, i - context_lines): i],
                            "context_after":  lines[i + 1: i + 1 + context_lines],
                        })
                if matches:
                    results.append({
                        "file_id": p.stem,
                        "path":    str(p.relative_to(repo)).replace("\\", "/"),
                        "layer":   lyr,
                        "matches": matches,
                        "match_count": len(matches),
                    })
        if layer in ("generated", "all"):
            _search(ai_ctx / "generated", "generated")
        if layer in ("curated", "all"):
            _search(ai_ctx / "curated", "curated")
        return {
            "query": query,
            "files_with_matches": len(results),
            "total_matches": sum(r["match_count"] for r in results),
            "results": results,
        }

    if name == "doc_check":
        from .cli import _doc_check
        return _doc_check(repo)

    if name == "doc_ingest_batch":
        from .core.doc_ingestor import ingest_document as _ingest
        batch_dir = Path(arguments["directory"]).resolve()
        if not batch_dir.is_dir():
            return {"error": f"not a directory: {batch_dir}"}
        glob_str = arguments.get("glob", "*.pdf,*.docx,*.md,*.txt")
        patterns = [p.strip() for p in glob_str.split(",") if p.strip()]
        overwrite   = arguments.get("overwrite", False)
        if_changed  = arguments.get("if_changed", False)
        mode        = arguments.get("mode", "python")
        stop_on_err = arguments.get("stop_on_error", False)

        doc_paths: list[Path] = []
        seen: set[Path] = set()
        for pat in patterns:
            for p in sorted(batch_dir.glob(pat)):
                if p.is_file() and p not in seen:
                    seen.add(p); doc_paths.append(p)

        if not doc_paths:
            return {"error": f"no files matching {glob_str!r} in {batch_dir}"}

        results, total_written, total_mem, total_tmpl = [], 0, 0, 0
        ingested = skipped = errored = 0
        for doc_path in doc_paths:
            res = _ingest(repo, doc_path, overwrite=overwrite,
                          if_changed=if_changed, mode=mode)
            results.append(res)
            if "error" in res:
                errored += 1
                if stop_on_err:
                    break
            elif res.get("unchanged"):
                skipped += 1
            else:
                ingested        += 1
                total_written   += res.get("files_written", 0)
                total_mem       += res.get("memories_added", 0)
                total_tmpl      += len(res.get("templates_created", []))
        return {
            "total_docs":              len(doc_paths),
            "docs_ingested":           ingested,
            "docs_skipped_unchanged":  skipped,
            "docs_errored":            errored,
            "total_files_written":     total_written,
            "total_memories_added":    total_mem,
            "total_templates_created": total_tmpl,
            "results":                 results,
        }

    if name == "doc_tag":
        from .cli import _doc_tag
        return _doc_tag(
            repo,
            arguments["file_id"],
            add_tags=arguments.get("add_tags"),
            remove_tags=arguments.get("remove_tags"),
            clear=arguments.get("clear", False),
        )

    if name == "doc_report":
        from .cli import _doc_report
        return _doc_report(repo)

    if name == "doc_validate":
        from .cli import _doc_validate
        return _doc_validate(repo)

    if name == "doc_rename":
        from .cli import _doc_rename
        return _doc_rename(repo, arguments["old"], arguments["new"])

    if name == "doc_snapshot_save":
        from .cli import _doc_snapshot_save
        return _doc_snapshot_save(repo, arguments["name"])

    if name == "doc_snapshot_list":
        from .cli import _doc_snapshot_list
        return _doc_snapshot_list(repo)

    if name == "doc_diff_since":
        from .cli import _doc_diff_since
        return _doc_diff_since(repo, arguments["snapshot"])

    if name == "doc_section":
        from .cli import _doc_fetch_section
        return _doc_fetch_section(repo, arguments["name"], arguments["heading"])

    if name == "doc_outline":
        from .cli import _doc_outline
        return _doc_outline(repo, arguments["name"])

    if name == "doc_annotate":
        from .cli import _doc_annotate
        return _doc_annotate(
            repo,
            arguments["file_id"],
            add_note=arguments.get("add_note"),
            author=arguments.get("author", ""),
            clear=arguments.get("clear", False),
        )

    if name == "doc_pin":
        from .cli import _doc_pin
        return _doc_pin(repo, arguments["file_id"])

    if name == "doc_unpin":
        from .cli import _doc_unpin
        return _doc_unpin(repo, arguments["file_id"])

    if name == "doc_diff":
        from .cli import _doc_diff
        return _doc_diff(repo)

    if name == "doc_fetch_for_feature":
        from .cli import _doc_fetch_for
        return _doc_fetch_for(
            repo,
            arguments["feature"],
            include_memories=arguments.get("include_memories", True),
            include_scope=arguments.get("include_scope", True),
        )

    if name == "doc_stats":
        ai_ctx = repo / ".ai-context"
        if not ai_ctx.exists():
            return {"error": "no .ai-context/ found — run doc_ingest first"}

        def _scan(directory: Path, layer: str) -> list[dict]:
            out: list[dict] = []
            if not directory.exists():
                return out
            for p in sorted(directory.glob("*.md")):
                try:
                    chars = len(p.read_text(encoding="utf-8"))
                except OSError:
                    chars = 0
                out.append({
                    "id":    p.stem,
                    "path":  str(p.relative_to(repo)).replace("\\", "/"),
                    "layer": layer,
                    "chars": chars,
                    "tokens": chars // 4,
                })
            return out

        generated = _scan(ai_ctx / "generated", "generated")
        curated   = _scan(ai_ctx / "curated",   "curated")
        all_files = generated + curated
        return {
            "generated":    generated,
            "curated":      curated,
            "total_files":  len(all_files),
            "total_chars":  sum(f["chars"]  for f in all_files),
            "total_tokens": sum(f["tokens"] for f in all_files),
        }

    if name == "doc_export":
        import time as _time
        ai_ctx = repo / ".ai-context"
        if not ai_ctx.exists():
            return {"error": "no .ai-context/ found — run doc_ingest first"}
        layer = arguments.get("layer", "all")
        include_header = arguments.get("include_header", True)

        # Load source name from index.json
        index_path = ai_ctx / "generated" / "index.json"
        source = "unknown"
        if index_path.exists():
            try:
                import json as _json2
                source = _json2.loads(index_path.read_text(encoding="utf-8")).get("source", "unknown")
            except Exception:  # noqa: BLE001
                pass

        dirs: list[tuple] = []
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
                sections.append({
                    "id":    p.stem,
                    "path":  str(p.relative_to(repo)).replace("\\", "/"),
                    "layer": lyr,
                    "chars": len(text),
                    "_text": text,
                })

        if not sections:
            return {"error": "no .ai-context/ files found"}

        total_chars = sum(s["chars"] for s in sections)
        parts: list[str] = []
        if include_header:
            parts.append(
                f"<!-- scope-intel-export: {source} | "
                f"{_time.strftime('%Y-%m-%d')} | "
                f"{len(sections)} files | ~{total_chars // 4:,} tokens -->\n"
            )
        for s in sections:
            parts.append(f"\n\n<!-- === {s['path']} [{s['layer']}] === -->\n\n")
            parts.append(s["_text"])

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

    # --- Phase 5 ---
    if name == "mem_auto_capture":
        return auto_capture_from_git(
            repo,
            days=arguments.get("days", 30),
            dry_run=arguments.get("dry_run", False),
        )
    if name == "mem_decay":
        return decay_confidence(
            repo,
            half_life_days=arguments.get("half_life_days", 90),
            floor=arguments.get("floor", 0.1),
            dry_run=arguments.get("dry_run", False),
        )
    if name == "mem_search":
        return search_memories(
            repo,
            arguments["query"],
            kind=arguments.get("type"),
            limit=arguments.get("limit", 10),
        )
    if name == "mem_export":
        out = arguments.get("output", "mempalace_export.json")
        return export_memories(repo, Path(out))
    if name == "mem_import":
        return import_memories(
            repo,
            Path(arguments["file"]),
            merge=not arguments.get("replace", False),
        )
    if name == "mem_conflicts":
        return detect_conflicts(
            repo,
            include_resolved=arguments.get("include_resolved", False),
        )

    return {"error": f"unknown tool: {name}"}


# ---------------------------------------------------------------------------
# JSON-RPC layer
# ---------------------------------------------------------------------------

def _ok(req_id, result: object) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _err(req_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _handle(msg: dict) -> None:
    req_id = msg.get("id")
    method = msg.get("method", "")

    # Notifications (no id) — acknowledge silently
    if req_id is None:
        return

    if method == "initialize":
        _send(_ok(req_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
        }))

    elif method == "tools/list":
        _send(_ok(req_id, {"tools": TOOLS}))

    elif method == "tools/call":
        params = msg.get("params", {})
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        try:
            result = _call_tool(tool_name, arguments)
            text = json.dumps(result, indent=2, ensure_ascii=False)
            _send(_ok(req_id, {"content": [{"type": "text", "text": text}]}))
        except Exception as exc:  # noqa: BLE001
            _send(_err(req_id, -32603, str(exc)))

    elif method == "ping":
        _send(_ok(req_id, {}))

    else:
        _send(_err(req_id, -32601, f"method not found: {method}"))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def serve() -> None:
    """Read newline-delimited JSON-RPC from stdin, write responses to stdout."""
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except ValueError as exc:
            _send(_err(None, -32700, f"parse error: {exc}"))
            continue
        try:
            _handle(msg)
        except Exception as exc:  # noqa: BLE001
            _send(_err(msg.get("id"), -32603, f"internal error: {exc}"))
