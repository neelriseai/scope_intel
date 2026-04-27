# Scope Intelligence Toolkit

A generic, language-adapter-based scope index for any code repository.

The toolkit lives **outside** target repos. For each target repo, it produces a
small, JSON-only `.scope-intelligence/` folder that tools (or Claude Code) can
query instead of scanning the source from scratch every time.

> **Phase 1: CLI only.** The MCP wrapper is intentionally not part of this
> phase — see `docs/roadmap.md`.

## What problem this solves

Without a scope index, a code agent (or any developer dropping into an
unfamiliar repo) has to re-discover the codebase on every session: walk the
tree, read files, build a mental model, find the relevant tests. This wastes
both human and token budget.

This toolkit pre-computes a compact, query-friendly map of what the repo
contains and how its parts depend on each other, so that workflows like
*"what does the `checkout` feature touch?"* or *"if I change this file, what
breaks?"* can be answered in milliseconds and without re-reading source.

## Design rules

- **Generic engine, per-repo data.** One toolkit, many repos. Each target
  repo gets its own `.scope-intelligence/` folder.
- **No source code in the index.** Only paths, names, line numbers, hashes,
  and edges. Safe to commit.
- **Compact JSON.** Diff-friendly, tool-agnostic, no DB required.
- **Language adapters.** New languages plug in via a small `LanguageAdapter`
  interface. Ships with Python, Java, JavaScript/TypeScript, and Playwright.
- **Zero runtime dependencies.** Pure Python ≥3.9, stdlib only.

## Install

```bash
pip install -e .
# or run without install:
python -m scope_intel --help
```

## Quick start (using the bundled sample repo)

```bash
# 1. Drop a .scope-intelligence/ folder into the target repo and a CLAUDE.md hint
scope init --repo examples/sample-repo --write-claude-md

# 2. Build the index (one full pass)
scope index examples/sample-repo

# 3. Query
scope summary               --repo examples/sample-repo
scope feature  auth         --repo examples/sample-repo
scope impacted --file src/users/repository.py --repo examples/sample-repo
scope tests    --feature checkout            --repo examples/sample-repo
scope symbol   handle_login --repo examples/sample-repo

# 4. After editing a file, refresh just that slice
scope update --files src/auth/login.py --repo examples/sample-repo
```

See `examples/sample-repo/README.md` for the full walkthrough with expected
output.

## Per-repo `.scope-intelligence/` layout

```
.scope-intelligence/
├─ config.json          # user-editable: ignore globs, feature overrides, aliases
├─ features.json        # feature index
├─ symbols.json         # classes, functions, methods (no source code)
├─ dependencies.json    # per-file imports + reverse edges + external deps
├─ tests.json           # tests + the files/features they cover
├─ aliases.json         # feature name aliases (auto + user-supplied)
├─ packages.json        # logical package roster
├─ repo_summary.json    # cached repo overview
├─ state.json           # impact-graph cache + metadata
└─ summaries/           # optional per-feature markdown one-liners
```

JSON schemas for the three core files live in `scope_intel/schemas/`.

## CLI reference

| Command | Purpose |
| --- | --- |
| `scope init [--repo PATH] [--write-claude-md]` | Create `.scope-intelligence/`. Optionally drops a `CLAUDE.md` hint into the repo root. |
| `scope index [PATH]` | Full index pass over the repo. |
| `scope update --files A B ...` | Re-parse only the listed files (incremental). |
| `scope summary` | Repo-wide overview: totals, languages, top features, hottest files. |
| `scope features` | List every feature with one-line stats. |
| `scope feature <name-or-alias>` | Files, entry points, deps, and tests for one feature. |
| `scope impacted --file F` / `--symbol S` / `--feature N` | Files transitively impacted by a change. |
| `scope tests --file F` / `--feature N` | Tests that cover the target. |
| `scope symbol <name>` | Callers + callees of a symbol. |

All read commands accept `--json` for machine-readable output.

## Adapters

Each adapter implements:

```python
class LanguageAdapter:
    name: str
    extensions: tuple
    def matches(self, path) -> bool: ...
    def parse_file(self, path, content) -> ParsedFile: ...
    def is_test(self, path) -> bool: ...
    def resolve_import(self, raw, from_file, repo_root, known_files) -> str | None: ...
    def external_deps(self, repo_root) -> list: ...
```

Bundled:

| Adapter | Extensions | Tests detected |
| --- | --- | --- |
| `python` | `.py` | `pytest` (file naming + `tests/` parts) |
| `java` | `.java` | `junit`/`testng` (annotations + naming) |
| `javascript` | `.js .jsx .ts .tsx .mjs .cjs` | `jest`-like (`.test.*` / `.spec.*`) |
| `playwright` | spec files importing `@playwright/test` | runs *before* the JS adapter |

To add a new language, drop a new adapter in `scope_intel/adapters/`, list it
in `default_adapters()`, and you're done. No core changes needed.

## Configuration

`scope init` writes a default `config.json`. Override anything you need:

```json
{
  "ignore_globs": [".git/**", "node_modules/**", "vendor/**"],
  "feature_roots": ["src", "app", "lib", "packages", "modules", "services"],
  "feature_overrides": {
    "src/billing": "payments",
    "tests/e2e": "auth"
  },
  "aliases": {
    "auth": ["login", "signup", "authentication"],
    "payments": ["billing", "charge", "refund"]
  },
  "max_file_size_kb": 512
}
```

`feature_overrides` lets you nail down feature ownership by path prefix when
the directory-based heuristic isn't quite right.

## Feature inference

Out of the box, the indexer infers the feature for each file using these
rules in order:
1. user-supplied `feature_overrides` (path-prefix → feature id)
2. `<feature_root>/<feature>/...` (e.g. `src/auth/...`)
3. `<feature>/<feature_root>/...` (e.g. `checkout/src/...`)
4. `tests/<feature>/...`
5. otherwise the top-level directory

For tests, `covers_files` is built from imports + a naming heuristic
(`test_login.py` → `login.py`, `LoginTest.java` → `Login.java`,
`login.spec.ts` → `login.py`/`login.js` if present), so cross-language
linkage like *"this Playwright spec covers the Python login feature"* works
automatically.

## Claude Code integration

A sample `CLAUDE.md` template (written by `scope init --write-claude-md`)
tells Claude to query the scope index before scanning source. For
auto-refreshing the index after Claude edits a file, see
[docs/claude-code-integration.md](docs/claude-code-integration.md) for a
ready-to-paste hook configuration.

## Roadmap

See [docs/roadmap.md](docs/roadmap.md). Phase 2 adds richer call-graph
edges; Phase 3 wraps everything in an MCP server so Claude Code can call the
toolkit as tools instead of shelling out.

## License

MIT.
