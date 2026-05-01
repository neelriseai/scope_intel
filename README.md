# scope_intel - Scope Intelligence Toolkit

`scope_intel` reduces AI token consumption by giving an assistant a precise,
precomputed map of a repository instead of making it read the whole codebase.
It combines scope indexing, impact analysis, test discovery, repo memory,
document context, and compact sidecars for agent-facing context.

In practice, this lets an assistant ask:

- Which files/classes/functions exist for this feature?
- What will be impacted if this file or symbol changes?
- Which tests should I run?
- What stable repo facts or architecture notes already exist?
- Is there a compact version of this context I can read first?

## Why It Saves Tokens

Without a scope index, each AI session usually spends tokens rediscovering the
same repo structure: walking directories, opening source files, finding tests,
and rebuilding feature ownership. `scope_intel` moves that work into compact
JSON indexes and optional sidecar files.

Typical savings depend on repo size and assistant discipline. The biggest gains
come when agents query `scope inventory`, `scope feature`, `scope impacted`,
`scope tests`, `scope mem fetch`, and compact sidecars before reading source.

## Main Features

| Area | What it provides |
| --- | --- |
| Scope index | Files, languages, packages, features, imports, reverse imports |
| Inventory | File/class/symbol roster without opening source files |
| Impact analysis | Direct and transitive blast radius for files, symbols, features |
| Test mapping | Related tests for files and features |
| Symbol graph | Classes, functions, methods, callers, callees |
| Touchpoints | Routes, config keys, DB models, events |
| Graph output | Mermaid/DOT class, dependency, and call graphs |
| Token tracking | Query log and savings reports |
| MemPalace | Semantic, procedural, episodic, and structural repo memory |
| Doc ingest | `.ai-context/` architecture and design context |
| Compact sidecars | Agent-readable compact DSL plus exact compressed payload |
| MCP server | 52 JSON-RPC tools for AI environments that support tools |

## Install

```bash
pip install -e "path/to/scope-intelligence-toolkit"
```

Or from this repository:

```bash
cd scope-intelligence-toolkit
pip install -e .
```

## Quick Start

```bash
# Create config and build the index
scope init --repo path/to/repo --write-claude-md
scope index path/to/repo

# Inspect the repo cheaply
scope summary --repo path/to/repo
scope inventory --repo path/to/repo --no-symbols
scope features --repo path/to/repo

# Work on a feature
scope feature auth --repo path/to/repo
scope impacted --file src/auth/login.py --repo path/to/repo
scope tests --feature auth --repo path/to/repo
scope mem fetch --feature auth --repo path/to/repo

# Refresh after edits
scope update --repo path/to/repo --files src/auth/login.py tests/auth/test_login.py
```

## Compact Context Workflow

The compact workflow keeps original artifacts unchanged and creates generated
sidecars for agents:

```bash
scope compact build --repo . --target ai-context
scope compact build --repo . --target skills
scope compact build --repo . --target memory
scope compact build --repo . --target all

scope compact stats --repo . --target all
scope compact validate --repo . --target all
scope compact decompress .ai-context/compact/generated/001-project-overview.md.scope
```

Each sidecar contains a compact DSL summary and an exact `zlib+base64` payload.
The DSL reduces prompt/context size. The payload lets tests and agents restore
the original exactly, so validation can prove no context was lost.

## How To Ask An AI Assistant To Use It

You do not need to write compressed DSL prompts manually in a chat window. Write
normal instructions and ask the assistant to use `scope_intel` before reading
large files.

Example:

```text
Before editing, use scope_intel. Start with scope summary and scope inventory.
Then query scope feature, scope impacted, scope tests, and scope mem fetch for
the relevant area. If compact sidecars exist, read those first and only open the
original docs or source files when detail is needed.
```

For a coding task:

```text
Use scope_intel to identify the impacted files and tests, make the smallest
safe change, run the relevant tests, and update the scope index for changed
files before finishing.
```

For architecture or design-doc work:

```text
Use scope doc fetch-for <feature> and scope compact stats/validate before
loading large .ai-context documents.
```

## MCP Server

```bash
scope serve
```

The MCP server exposes 52 tools, including:

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
- `doc_fetch_for_feature`

Use the MCP server when your AI environment can call tools directly. Use the CLI
when the assistant can run shell commands.

## Storage

```text
.scope-intelligence/
  config.json
  features.json
  symbols.json
  dependencies.json
  tests.json
  aliases.json
  packages.json
  touchpoints.json
  repo_summary.json
  state.json
  mempalace.jsonl
  query_log.jsonl
```

Generated compact sidecars can also appear at:

```text
.ai-context/compact/
.agents/compact/
.scope-intelligence/mempalace.compact.scope
```

`query_log.jsonl` is local usage telemetry and should usually stay ignored.
Compact sidecars are generated artifacts; commit them only if your team wants
agents to consume them directly from git.

## Tests

```bash
cd scope-intelligence-toolkit
python -m compileall -q scope_intel tests
python -m pytest -q tests/test_suite.py
python -m pytest -q tests/test_doc_ingest.py -k "not TestLLMIngestLive"
```

Live Ollama tests are optional and require a running Ollama server with the
configured model.

## More Detail

See [scope-intelligence-toolkit/README.md](scope-intelligence-toolkit/README.md)
for the full command guide, storage policy, language adapter notes, compact
sidecar details, and operational guidance.
