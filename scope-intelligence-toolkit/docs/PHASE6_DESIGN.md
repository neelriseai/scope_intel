# Phase 6 — Memory that Persists, Decays, and Listens

Status: design / not yet implemented
Predecessor: Phase 5 (`scope doc *` — design-doc ingestion + curation surface)

## Why now

Phase 4 gave us **MemPalace**: per-repo `mempalace.jsonl` with four memory
types (`semantic`, `procedure`, `episodic`, `structural`). It works inside a
single repo but breaks down on three real-world failure modes:

1. **One team, many repos.** A bug fix recorded in `repo-A` is invisible
   when the same engineer (or agent) is working in `repo-B`, even though
   the underlying constraint (e.g. "don't store JWTs in localStorage")
   is universal.
2. **Memories rot silently.** `confidence: 0.9` from 18 months ago and
   `confidence: 0.9` from yesterday are not equal, but `mem fetch`
   treats them the same. Stale `semantic` entries pollute results.
3. **Capture is manual.** `scope mem add` requires an explicit human
   action. The most valuable observations — the ones an agent makes
   *while* solving a problem — are lost the moment the conversation ends.

Phase 6 addresses all three.

## Pillars

### 1. Cross-repo memory links

**Goal:** a memory in repo A can be retrieved when working in repo B,
without merging the JSONLs.

**Approach:** introduce a *memory federation manifest* —
`~/.scope-intelligence/federation.json`:

```json
{
  "repos": [
    { "path": "/work/payments-svc",  "alias": "payments" },
    { "path": "/work/billing-ui",    "alias": "billing"  },
    { "path": "/work/shared-libs",   "alias": "shared"   }
  ],
  "links": [
    { "from": "billing", "to": "shared", "scope": "semantic+procedure" },
    { "from": "payments","to": "shared", "scope": "all"                }
  ]
}
```

`scope mem fetch --feature X` first reads the local `mempalace.jsonl`,
then walks declared `links` and merges results, tagging each entry with
its source alias. No data is duplicated; lookup is read-only across
repos.

**Conflict handling:** when two repos disagree (e.g. one says
`always validate` confidence 0.9, the other says `validation optional`
confidence 0.4), surface both in the layered fetch output rather than
auto-resolving — let the agent or human pick.

**New CLI:**
- `scope mem federation add <path> --alias <a>`
- `scope mem federation link --from <a> --to <b> --scope semantic`
- `scope mem federation list`
- `scope mem federation remove <alias>`

### 2. Confidence decay

**Goal:** old `semantic` memories rank below new ones unless explicitly
reinforced.

**Approach:** every `semantic` entry already carries a `ts` (write
timestamp). Add an effective-confidence calculation at fetch time:

```
effective = base_confidence * exp(-age_days / half_life_days)
```

Defaults: `half_life_days = 90`. Configurable per-entry via
`--half-life N` on `scope mem add`, and globally via
`.scope-intelligence/config.json::semantic_half_life`.

Reinforcement: `scope mem touch <mp_id>` updates the timestamp without
losing history (record kept under `reinforced_at`). When `mem fetch`
returns a result, the engine *optionally* offers reinforcement
("this memory has decayed to 0.4 — was it useful? `scope mem touch
mp_X`").

**Decay does not delete.** It re-ranks. A separate `scope mem prune
--below 0.1` does the deletion, gated on a confirm or `--force`.

**Backwards compatibility:** entries without `ts` get a synthetic
ts of "now - half_life" so they're treated as moderately decayed but
not zero.

### 3. Agent-triggered captures

**Goal:** agents (Claude Code, Claude API harnesses) emit memory
entries automatically when high-signal events occur.

**Approach:** a thin **capture protocol** that agents invoke instead
of full `scope mem add`:

```
scope mem capture --signal <signal_type> --evidence <text> [--feature X]
```

Where `<signal_type>` is one of:

| Signal             | Trigger                                      | Auto memory type |
|--------------------|----------------------------------------------|------------------|
| `repeated-error`   | same exception 3+ times in one session        | `episodic` (failure) |
| `surprising-fix`   | bug fix + commit message contains "actually" | `episodic` (decision) |
| `validated-claim`  | user said "yes that's right" to an assertion | `semantic` (conf 0.7) |
| `repeated-lookup`  | same `scope mem fetch` 3+ times              | n/a — promote to a `procedure` from prior lookups |
| `scope-mismatch`   | feature inferred from changed files differs from declared feature | `episodic` (note) |

The capture command is **rate-limited** (max N per signal per hour) and
**confidence-capped** (auto entries cap at 0.7 to never outrank human
ones).

**Hooks:**
- Settings.json hook fires after each `Bash` exit code != 0 (capture
  `repeated-error`).
- Settings.json hook fires after each `git commit` (capture
  `surprising-fix` if message matches pattern).
- MCP tool `mem_capture` exposes the same surface to agents that
  speak JSON-RPC instead of shell.

## Cross-cutting changes

- `mempalace.jsonl` schema gets two optional fields per entry:
  - `source: "human" | "agent" | "imported"` (default `human` for legacy)
  - `half_life_days: int | null`
- `scope mem list` gains `--source agent`, `--decayed-below 0.3`.
- HTML report (`scope report --html`) adds a "Memory health" panel:
  count of decayed-below-threshold entries, ratio of agent vs human
  capture, top-10 reinforced entries.

## Open questions

1. **Federation security.** A user with read access to repo A's
   `mempalace.jsonl` shouldn't necessarily see repo B's. Do we need
   per-link visibility rules, or is "you've already cloned both repos"
   the threat model?
2. **Decay function shape.** Exponential is the obvious default, but
   a step function ("trustworthy for 30 days, then halve daily") may
   match human intuition better. Worth a quick A/B before locking in.
3. **Agent capture spam.** What's the recovery story when an agent
   floods the store with low-quality captures? Probably:
   `scope mem prune --source agent --below 0.4` + a hard cap on
   agent-source entries per repo.

## Out of scope for Phase 6

- Vector embeddings / semantic similarity search.
- Multi-tenant remote MemPalace (a hosted server). Federation is
  filesystem-local in this phase.
- Replacing the JSONL store with SQLite. Zero-dep is still a hard
  constraint.

## Rollout plan

1. **6.1 — decay only.** Add `effective_confidence` to fetch output;
   no schema changes other than the optional `half_life_days`. Ship,
   gather feedback for ~2 weeks.
2. **6.2 — agent capture.** Add `mem capture` + the hook recipes;
   include a worked example in `docs/AGENT_HOOKS.md`.
3. **6.3 — federation.** Last because it touches the most surface
   area and benefits most from the previous two being in place.

Each sub-phase ships independently with its own test sweep and
incrementing `tests/test_doc_ingest.py` count.
