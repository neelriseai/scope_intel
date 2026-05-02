# Scope Intelligence Toolkit

`scope_intel` is a zero-dependency Python toolkit that gives AI agents precise
repo context without making them read the whole codebase. It builds a compact
`.scope-intelligence/` index containing file metadata, symbols, dependencies,
tests, touchpoints, memories, LLM-assisted document context, and optional
compact sidecars.

The goal is simple: let an assistant ask, "what do I need to know for this
change?" and get the right files, classes, tests, memories, and design notes in
milliseconds.

## What It Solves

Without a scope index, every new AI session tends to rediscover the same facts:
walk the tree, inspect files, infer features, search tests, and rebuild a mental
model. That burns tokens and time.

With `scope_intel`, the agent can query a prebuilt index:

```bash
scope feature auth --repo .
scope impacted --file src/auth/login.py --repo .
scope tests --feature checkout --repo .
scope inventory --feature billing --repo .
scope mem fetch --feature auth --repo .
```

In the current project logs, scope queries have measured substantial token
savings versus naive whole-repo reading. The older scope-only workflow usually
saves about **65-75%**. When agents consistently use the full stack - inventory
first, scoped source reads, MemPalace/doc retrieval, and compact sidecars -
expected savings can reach **up to about 80-85%** on codebase-context tasks.
Your measured number will depend on repo size, feature boundaries, and how
consistently agents query the index before reading source.

| Strategy | Usual Usage | Typical Saving |
| --- | --- | --- |
| Index inventory | `scope inventory`, MCP `scope_inventory`; inspect files/classes/symbols without source bodies | 80-95% for repo-shape discovery |
| Scoped source reads | `scope feature`, `scope impacted`, `scope tests`, `scope symbol`, `scope touchpoints` | 60-75% for focused code work |
| Memory context | `scope mem fetch/search`; reuse decisions, fixes, procedures, ownership, stable facts | 70-90% for repeated repo knowledge |
| Document context | `scope doc fetch-for/search` after Python or Qwen/Ollama ingest | 60-85% for architecture/design lookup |
| Compact sidecars | `scope compact build/stats/validate`; read DSL before original docs/skills/memory | 30-70% per artifact, supports 80-85% full workflow |

## Core Features

| Area | What It Does | When To Use |
| --- | --- | --- |
| Scope index | Files, languages, features, imports, reverse imports, packages | First step before code exploration |
| Symbol index | Classes, functions, methods, params, calls, callers, callees | Understanding code ownership and call flow |
| Impact analysis | Direct and transitive files affected by a file, symbol, or feature | Before editing shared code |
| Test mapping | Related tests by file or feature | Choosing the smallest useful test set |
| Touchpoints | Routes, config keys, DB models, events | API/config/schema-impact work |
| Inventory | Files/classes/symbols without source reads | Letting agents see repo shape cheaply |
| Graphs | Mermaid/DOT class, dependency, and call graphs | Architecture review and explanations |
| Token tracker | Logs estimated naive vs scoped token cost | Measuring savings over time |
| MemPalace | Semantic, procedural, episodic, and structural memory | Persisting repo facts and past lessons |
| Memory federation | Link memories across related repos | Multi-repo systems |
| Doc ingest | Converts docs into `.ai-context/` using Python mode or Qwen/Ollama LLM classification | Keeping architecture context queryable |
| Compact sidecars | Agent-facing DSL plus exact compressed payload | Reducing prompt/context tokens safely |
| MCP server | 52 JSON-RPC tools over stdio | Letting Claude/Codex call the toolkit directly |

## Install

From inside this package:

```bash
pip install -e .
scope --help
```

Or run without installing:

```bash
python -m scope_intel --help
```

## Quick Start

Index a target repo:

```bash
scope init --repo path/to/repo --write-claude-md
scope index path/to/repo
```

Ask focused questions:

```bash
scope summary --repo path/to/repo
scope features --repo path/to/repo
scope feature auth --repo path/to/repo
scope impacted --file src/users/repository.py --repo path/to/repo
scope tests --feature checkout --repo path/to/repo
scope symbol handle_login --repo path/to/repo
scope inventory --feature auth --repo path/to/repo
```

After edits, refresh only changed files:

```bash
scope update --repo path/to/repo --files src/auth/login.py tests/auth/test_login.py
```

## Command Guide

### Repo and Scope

| Command | Purpose |
| --- | --- |
| `scope init --repo <path>` | Create `.scope-intelligence/` and default config |
| `scope index <path>` | Build a full index |
| `scope update --repo <path> --files A B` | Reparse changed files |
| `scope summary --repo <path>` | Repo totals, languages, top features |
| `scope features --repo <path>` | Feature list with file/symbol/test counts |
| `scope feature <name> --repo <path>` | Files, symbols, entry points, tests for one feature |
| `scope inventory --repo <path>` | Files, classes, symbols from the index only |

Use `inventory` when an assistant needs to understand what exists in the repo
without spending tokens on file contents:

```bash
scope inventory --repo .
scope inventory --feature checkout --repo .
scope inventory --feature checkout --no-symbols --repo .
scope inventory --repo . --json
```

The same capability is exposed to tool-capable assistants as the MCP tool
`scope_inventory`. Pass `include_symbols=false` for the cheapest file/class
roster, or a `feature` value to restrict the answer to one subsystem.

### Impact, Tests, Symbols, Graphs

| Command | Purpose |
| --- | --- |
| `scope impacted --file <file>` | Direct and transitive impact of changing a file |
| `scope impacted --symbol <name>` | Impact of changing a symbol |
| `scope impacted --feature <name>` | Impact of changing a feature |
| `scope tests --file <file>` | Tests related to a file |
| `scope tests --feature <name>` | Tests related to a feature |
| `scope symbol <name>` | Symbol context with callers/callees |
| `scope callers <name>` | Who calls a symbol |
| `scope callees <name>` | What a symbol calls |
| `scope touchpoints` | Routes/configs/models/events |
| `scope graph <query>` | Mermaid/DOT graph from the index |
| `scope diff HEAD~1` | Changed files plus impacted scope |

Examples:

```bash
scope impacted --file scope_intel/core/mempalace.py --repo .
scope tests --feature scope_intel --repo .
scope graph scope_intel --kind deps --repo .
scope graph handle_login --target symbol --kind calls --repo .
```

### Memory: MemPalace

MemPalace stores repo knowledge in `.scope-intelligence/mempalace.jsonl`.
It supports:

- `semantic`: durable facts, ranked by confidence and decay.
- `procedure`: step-by-step local workflows.
- episodic types: `bug`, `decision`, `failure`, `ownership`, `note`, `fix`.
- structural layer: injected live from the scope index during `mem fetch`.

Useful commands:

```bash
scope mem add --type semantic --note "auth uses HS256 JWT" --feature auth --confidence 0.95
scope mem add --type procedure --note "Add endpoint" --feature api --step "Add route" --step "Add test"
scope mem fetch --feature auth
scope mem search "JWT signing"
scope mem conflicts
scope mem capture --signal validated-claim --evidence "billing uses Stripe SDK" --feature billing
scope mem auto-capture --days 30
scope mem prune --below 0.2 --dry-run
```

### Document Context: `.ai-context/`

`scope doc` ingests design docs and keeps architecture context close to the
repo, instead of repeatedly pasting full documents into chat.

Document ingest has two modes:

- `python`: fast deterministic parser and keyword/router, no LLM.
- `llm`: Qwen through Ollama reads structured chunks, classifies them into
  target context files, extracts richer architecture records, and can run a
  second synthesis pass for `module-map.md`.

```bash
scope doc ingest docs/design.md --repo .
scope doc ingest docs/design.md --repo . --mode llm --ollama-model qwen2.5:7b
scope doc ingest docs/design.md --repo . --mode llm --second-pass --verify
scope doc ingest-batch docs --repo . --mode llm --if-changed
scope doc list --repo .
scope doc fetch overview --repo .
scope doc search "validation" --repo .
scope doc fetch-for auth --repo .
scope doc stats --repo .
scope doc report --repo .
scope doc validate --repo .
```

In LLM mode, Ollama must be running locally. The CLI default model is
`qwen2.5:7b`, and both the CLI and MCP `doc_ingest` tool let you override the
model and server URL. If Ollama is unavailable, ingest falls back to Python mode
and reports the fallback in the result.

The generated layout:

```text
.ai-context/
  generated/
    001-project-overview.md
    002-system-architecture.md
    ...
    index.json
  curated/
    constraints.md
    current-phase.md
    module-map.md
```

Original `.ai-context` files are human-readable and canonical. Compact sidecars
are optional agent-facing artifacts.

### Compact Sidecars

Compact sidecars are designed for your exact concern: reduce what agents read
without deleting or mutating the original artifacts.

Each sidecar contains:

- a readable compact DSL block for the agent;
- an exact `zlib+base64` payload;
- source hash, source path, token estimates, and metadata.

Build sidecars:

```bash
scope compact build --repo . --target ai-context
scope compact build --repo . --target skills
scope compact build --repo . --target memory
scope compact build --repo . --target all
```

Validate losslessness:

```bash
scope compact validate --repo . --target all
```

Show savings:

```bash
scope compact stats --repo . --target all
```

Recover the exact original from a sidecar:

```bash
scope compact decompress .ai-context/compact/generated/001-project-overview.md.scope
```

Important: the DSL is intentionally compact and may omit prose nuance. The
payload is exact. Agents should read DSL first, then fetch/decompress/read the
original when nuance matters.

## How To Ask An AI Assistant To Use It

Yes, you can ask an AI assistant to use this tool as needed. Good instruction:

```text
Before reading source files, use scope_intel to inspect this repo.
Start with `scope summary`, then use `scope inventory`, `scope feature`,
`scope impacted`, `scope tests`, and `scope mem fetch` as needed.
If `.ai-context/compact` exists, read compact sidecars first and fetch originals
only when detail is needed. Do not scan the whole repo unless scope_intel cannot
answer the question.
```

For a coding task:

```text
Use scope_intel before editing. Find the relevant feature, impacted files, and
tests. Make the smallest change, then run the tests returned by `scope tests`.
After editing, run `scope update --files <changed-files>`.
```

For design-doc work:

```text
If a new design document must be parsed, use `scope doc ingest --mode llm`
with Qwen/Ollama. Then use `scope doc fetch-for <feature>` and
`scope compact stats/validate` before loading large design docs. Prefer compact
sidecars when available.
```

For memory:

```text
Use `scope mem fetch` before editing a feature. If you discover a stable repo
fact, capture it with `scope mem capture` or suggest a `scope mem add`.
```

## MCP Server

Run:

```bash
scope serve
```

The MCP server exposes 52 tools over JSON-RPC stdio, including scope queries,
doc context, compact sidecars, memory, graphing, reports, and federation.
Common tools:

- `scope_summary`
- `scope_inventory`
- `scope_feature`
- `scope_impacted`
- `scope_tests`
- `scope_symbol`
- `scope_graph`
- `compact_build`
- `compact_validate`
- `compact_stats`
- `mem_fetch`
- `doc_ingest`
- `doc_ingest_batch`
- `doc_fetch_for_feature`

Use MCP when your AI environment can call tools directly. Use the CLI when the
assistant can run shell commands.

## Storage

```text
.scope-intelligence/
  config.json          # user config
  features.json        # feature index
  symbols.json         # classes/functions/methods; no source code
  dependencies.json    # imports, reverse imports, file metadata
  tests.json           # test files and coverage hints
  aliases.json         # feature aliases
  packages.json        # logical package roster
  touchpoints.json     # routes/config/model/event touchpoints
  repo_summary.json    # cached summary
  state.json           # impact cache and config snapshot
  mempalace.jsonl      # long-term memories
  query_log.jsonl      # local token-savings log; usually ignored
```

`.ai-context/compact/`, `.agents/compact/`, and
`.scope-intelligence/mempalace.compact.scope` are generated sidecars.

## What To Commit

Recommended:

- Commit source code.
- Commit curated team memories if they are useful to everyone.
- Commit design docs or curated `.ai-context` if your team wants shared context.
- Ignore `query_log.jsonl`; it is machine-local usage telemetry.
- Treat compact sidecars as generated artifacts unless your team explicitly
  wants agents to consume them from git.

## Language Support

Bundled adapters:

| Adapter | Extensions | Notes |
| --- | --- | --- |
| Python | `.py` | AST symbols, calls, imports, pytest heuristics |
| Java | `.java` | Classes/methods, JUnit/TestNG-style tests |
| JavaScript/TypeScript | `.js .jsx .ts .tsx .mjs .cjs` | Functions/classes/imports, Jest-like tests |
| Playwright | specs importing `@playwright/test` | Runs before the JS adapter |

To add a language, implement `LanguageAdapter` in `scope_intel/adapters/` and
register it in `default_adapters()`.

## Development And Tests

Compile:

```bash
python -m compileall -q scope_intel tests
```

Run the core suite:

```bash
python -m pytest -q tests/test_suite.py
```

Run document-ingest tests without live Ollama checks:

```bash
python -m pytest -q tests/test_doc_ingest.py -k "not TestLLMIngestLive"
```

Live Ollama tests are intentionally gated and require a running Ollama server
with the configured model.

## Known Operational Notes

- If pytest temp dirs sit inside a parent Git checkout, tests that expect a
  non-Git temp repo may see the parent `.git`. Use a temp path outside the repo
  for full regression runs.
- The index can become stale after new files are added. Run `scope index .` or
  `scope update --files <changed-files>` before relying on `impacted` for those
  files.
- Compact sidecar validation fails when the original source changes after the
  sidecar was built. Rebuild compact sidecars after source/context edits.

## License

MIT
