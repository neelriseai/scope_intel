# scope_intel — Scope Intelligence Toolkit

A zero-dependency Python CLI that reduces AI token consumption by giving Claude (or any AI) precise, scoped context instead of entire codebases.

## What it does

Instead of reading every file in your repo (thousands of tokens), `scope_intel` tells an AI exactly which files, symbols, and tests are relevant to a specific feature, file change, or symbol — typically saving **60–80% of tokens per query**.

## Phases

| Phase | Features |
|---|---|
| 1+2 | Index, query engine, language adapters (Python/Java/JS/Playwright), call graph |
| 3 | Token savings tracker, `scope report` (terminal + HTML), MCP stdio server |
| 4 | MemPalace — four-type long-term memory (semantic/procedure/episodic/structural) |
| 5 | Auto-capture from git, confidence decay, TF-IDF search, export/import, conflict detection |

## Install

```bash
pip install -e "path/to/scope-intelligence-toolkit"
```

## Quick start

```bash
# Set up a repo
scope init && scope index .

# Query
scope feature auth
scope impacted --file src/auth/login.py
scope mem fetch --feature auth

# MemPalace
scope mem add --type semantic --note "auth uses HS256 JWT" --feature auth --confidence 0.95
scope mem search "JWT signing"
scope mem auto-capture --days 30

# Dashboard
scope report
scope report --html --output report.html
```

## MCP server

```bash
scope serve   # JSON-RPC 2.0 over stdio, 21 tools
```

## Key commands

| Command | What it does |
|---|---|
| `scope feature <name>` | Files, symbols, tests for a feature |
| `scope impacted --file <f>` | Transitive impact of a file change |
| `scope symbol <name>` | Callers, callees, reads, writes |
| `scope diff HEAD~1` | Scope impact of recent git changes |
| `scope mem fetch --feature <f>` | Layered memories for a feature |
| `scope mem search "query"` | TF-IDF search across all memories |
| `scope mem auto-capture` | Auto-create memories from git log |
| `scope mem conflicts` | Detect contradicting semantic memories |
| `scope report --html` | Token savings HTML dashboard |
| `scope global-report --repo p1 --repo p2` | Cross-repo savings dashboard |

## Storage

All data is plain JSONL — no database, no external dependencies.

```
.scope-intelligence/
  features.json       # feature index
  symbols.json        # symbol index
  dependencies.json   # file dependency graph
  mempalace.jsonl     # team knowledge (commit this)
  query_log.jsonl     # machine-local savings log (gitignore this)
```

## Test suite

```bash
python -m pytest scope-intelligence-toolkit/tests/test_suite.py -v
# 95 tests, 0 failures
```
