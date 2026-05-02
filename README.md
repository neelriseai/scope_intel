# scope_intel - Scope Intelligence Toolkit

`scope_intel` reduces AI token consumption by giving an assistant a precise,
precomputed map of a repository instead of making it read the whole codebase.
It combines scope indexing, impact analysis, test discovery, repo memory,
LLM-assisted document parsing/classification, and compact sidecars for
agent-facing context.

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

Typical savings depend on repo size and assistant discipline. The older
scope-only workflow usually saves about **65-75%** versus repeatedly reading the
whole repo. With the newer workflow - index inventory first, scoped source reads
second, memory/doc retrieval for stable context, and compact sidecars for large
context artifacts - expected savings can reach **up to about 80-85%** on
codebase-context tasks. The `scope report` dashboard shows the measured value
from local query logs; this repo's local log measured **55.4%** after adding
the index-only inventory estimator, before compact sidecars or regular
memory/doc retrieval were reflected in usage.

| Strategy | Usual usage | Typical token saving |
| --- | --- | --- |
| Index inventory | `scope inventory`, MCP `scope_inventory`; see files/classes/symbols before opening source | 80-95% for roster discovery |
| Scoped source reads | `scope feature`, `scope impacted`, `scope tests`, `scope symbol`, `scope touchpoints` | 60-75% for code navigation |
| Memory context | `scope mem fetch/search`; avoid rediscovering decisions, fixes, ownership, procedures | 70-90% for repeated repo knowledge |
| Document context | `scope doc fetch-for/search` after Python or Qwen/Ollama ingest | 60-85% for architecture/design lookup |
| Compact sidecars | `scope compact build/stats/validate`; read DSL before original docs/skills/memory | 30-70% per artifact, supports 80-85% full workflow |

## Main Features

| Area | What it provides |
| --- | --- |
| Scope index | Files, languages, packages, features, imports, reverse imports |
| Inventory | CLI/MCP file, class, and symbol roster without opening source files |
| Impact analysis | Direct and transitive blast radius for files, symbols, features |
| Test mapping | Related tests for files and features |
| Symbol graph | Classes, functions, methods, callers, callees |
| Touchpoints | Routes, config keys, DB models, events |
| Graph output | Mermaid/DOT class, dependency, and call graphs |
| Token tracking | Query log and savings reports |
| MemPalace | Semantic, procedural, episodic, and structural repo memory |
| Doc ingest | `.ai-context/` architecture context using fast Python mode or Qwen/Ollama LLM classification |
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
scope inventory --repo path/to/repo --feature auth --json
scope features --repo path/to/repo

# Work on a feature
scope feature auth --repo path/to/repo
scope impacted --file src/auth/login.py --repo path/to/repo
scope tests --feature auth --repo path/to/repo
scope mem fetch --feature auth --repo path/to/repo

# Refresh after edits
scope update --repo path/to/repo --files src/auth/login.py tests/auth/test_login.py

# Measure token savings
scope report --repo path/to/repo
scope report --repo path/to/repo --html --output scope-report.html
```

## Inventory Without Reading Source

Yes, the repo roster capability exists. Use `scope inventory` from the CLI or
`scope_inventory` from MCP to list files, classes, and symbols already captured
in the index. This lets an agent understand what exists in any indexed Git repo
without spending tokens on source bodies.

```bash
scope inventory --repo .
scope inventory --repo . --no-symbols
scope inventory --repo . --feature auth --json
```

For MCP clients, call `scope_inventory` with `repo`, optional `feature`, and
`include_symbols=false` when the assistant only needs the file/class roster.

## LLM Document Ingest With Qwen

Document ingest has two modes:

- `python`: fast deterministic parsing/routing, no LLM.
- `llm`: Qwen through Ollama reads chunks, classifies them, extracts richer
  context, and can run a second pass to synthesize `module-map.md`.

```bash
scope doc ingest docs/design.md --repo . --mode llm --ollama-model qwen2.5:7b
scope doc ingest docs/design.md --repo . --mode llm --second-pass --verify
scope doc ingest-batch docs --repo . --mode llm --if-changed
```

The generated `.ai-context/` files can then be queried by `scope doc fetch`,
`scope doc fetch-for`, `scope doc search`, and compacted with
`scope compact build --target ai-context`.

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
If a new design document must be parsed, use `scope doc ingest --mode llm`
with Qwen/Ollama, then use `scope doc fetch-for <feature>` and compact
sidecars before loading large `.ai-context` documents.
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
- `doc_ingest`
- `doc_ingest_batch`

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
