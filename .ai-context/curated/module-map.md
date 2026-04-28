# Module Map — Generic Intelligence Strategy

## Layer 1: Project Context (`.ai-context/`)

### Server
- `server.py` — FastAPI MCP server. Two layers:
  - `/list_context_files`, `/get_context_file/{id}`, `/get_context_slice` — context docs
  - `/scope/summary`, `/scope/feature`, `/scope/impacted`, `/scope/tests`, `/scope/symbol`, `/scope/callers`, `/scope/callees`, `/scope/touchpoints`, `/scope/diff` — scope proxy endpoints

### Generated docs (`generated/`)
- `001-project-overview.md` to `009-schema-design.md` — architecture reference
- `claude-code-integration.md` — hook + CLAUDE.md wiring
- `roadmap.md` — Phase 1–4 plan
- `mcp-contract.md` — full MCP method contract
- `index.json` — manifest with layer structure

### Curated state (`curated/`)
- `current phase.md` — active phase + deliverables
- `constraints.md` — token-efficiency rules
- `module-map.md` — this file

## Layer 2: Code Scope Toolkit (`scope-intelligence-toolkit/`)

### CLI Package (`scope_intel/`)
- `cli.py` — entry point: `scope <cmd>`
- `core/store.py` — per-repo JSON I/O
- `core/indexer.py` — two-pass file walker, adapter dispatch, hash-based incremental
- `core/call_resolver.py` — cross-file call graph resolution
- `core/graph_builder.py` — BFS impact-graph cache
- `core/query_engine.py` — feature/symbol/touchpoints/callers/callees queries
- `core/summarizer.py` — repo summary builder
- `core/diff.py` — git-based scope delta (`scope diff <ref>`)

### Language Adapters (`scope_intel/adapters/`)
- `base.py` — `LanguageAdapter` interface + `ParsedFile`, `ParsedSymbol`, `ParsedTouchpoints`
- `python_adapter.py` — AST-based (symbols, calls, reads/writes, routes, configs, SQLAlchemy models)
- `java_adapter.py` — regex-based (Spring routes, @Value configs, JPA models)
- `javascript_adapter.py` — regex-based (Express routes, process.env)
- `playwright_adapter.py` — wraps JS adapter for `.spec.{ts,js}` files

### Schemas (`scope_intel/schemas/`)
- `feature_map_schema.json`
- `symbol_schema.json`
- `dependency_schema.json`

### Per-repo Index (`.scope-intelligence/`)
- `config.json` — feature_overrides, ignore_globs, aliases
- `features.json` — feature roster
- `symbols.json` — all symbols with reads/writes/calls/called_by/resolved_calls
- `dependencies.json` — file import graph + external deps
- `tests.json` — test-to-feature+file mapping
- `touchpoints.json` — routes, configs, db_models, events
- `aliases.json`, `packages.json`, `repo_summary.json`, `state.json`

## Layer 3: Claude Code Skills (`.claude/skills/`)
- `debug-feature/SKILL.md` — scope-guided debug playbook
- `enhance-feature/SKILL.md` — scope-guided enhancement playbook
- `impact-analysis/SKILL.md` — blast-radius analysis before changes
- `update-scope/SKILL.md` — index refresh workflow

## Hooks (`.claude/settings.json`)
- `PostToolUse(Edit|Write|MultiEdit)` → `scope update` (background)
- `UserPromptSubmit` → inject `<scope>` one-liner into prompt
- `PreToolUse(Glob|Grep)` → soft reminder to use scope first
