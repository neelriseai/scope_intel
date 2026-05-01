---
name: episodic-memory
description: >
  Technique for snapshotting AI context state at meaningful points in time,
  chaining episodes together into a timeline, and restoring any prior state.
  Modelled on episodic memory from cognitive science — "what did we know and
  believe at a specific moment?"
status: candidate         # not implemented — under evaluation
relates_to: doc-ingest, mempalace, scope-intelligence-toolkit
---

## Concept — Episodic Memory & Restore Points

### The Problem It Solves

Today the scope intelligence toolkit has:
- `mempalace.jsonl` — a living, append-only stream of facts (confidence decays over time)
- `.ai-context/` — files that get overwritten when `scope doc ingest` runs again
- No way to answer: *"What did we believe about the memory layer before we redesigned it?"*
- No way to answer: *"Give me the context snapshot from when Sprint 2 started."*
- No safe point before a risky change: *"I'm about to refactor the entire engine — save current state."*

Episodic memory adds a **timeline dimension** to the flat fact store:

```
Episode 0 (doc-ingest, 2025-01-10)
    ↓
Episode 1 (sprint-1-start, 2025-01-15) ← "restore point before engine rewrite"
    ↓
Episode 2 (architecture-pivot, 2025-02-01)
    ↓
Episode 3 (sprint-3-start, 2025-02-20)  ← current HEAD
```

---

## Core Concepts

### Episode
A named, timestamped snapshot of the AI context state:
```json
{
  "episode_id": "ep_003",
  "label": "sprint-3-start",
  "created_at": "2025-02-20T09:00:00Z",
  "trigger": "manual",
  "parent_episode": "ep_002",
  "snapshot": {
    "mempalace_entries": 42,
    "features_count": 15,
    "files_hashed": { "001-project-overview.md": "sha256:abc...", ... }
  },
  "delta_from_parent": {
    "added_facts": 8,
    "decayed_facts": 3,
    "changed_files": ["003-deterministic-engine.md"]
  },
  "tags": ["sprint-start", "pre-refactor"]
}
```

### Episode Chain
Episodes link via `parent_episode` — a singly-linked list forming a timeline.
No branching (for simplicity). Each episode points to its predecessor.

```
ep_000 → ep_001 → ep_002 → ep_003 (HEAD)
```

### Restore Point
A special episode tagged with `restore_point: true` — signals "safe to roll back here."
Created explicitly by the user or automatically at key triggers.

---

## Storage Design

```
.scope-intelligence/
├── mempalace.jsonl          ← live fact stream (today)
├── features.json            ← live feature registry (today)
└── episodes/
    ├── index.json           ← episode chain manifest
    ├── ep_000/
    │   ├── meta.json        ← episode metadata + delta summary
    │   ├── mempalace.jsonl  ← snapshot of facts at this moment
    │   └── features.json    ← snapshot of features at this moment
    ├── ep_001/
    │   ├── meta.json
    │   ├── mempalace.jsonl
    │   └── features.json
    └── ...
```

**Note:** `.ai-context/` files are NOT snapshotted by default (they're large markdown).
Instead, only file hashes are stored — if a full file restore is needed, git can provide it.
Optionally: snapshot `.ai-context/` on restore-point episodes only.

---

## How It Solves Real Problems

### Problem 1 — Doc Ingest Overwrites Context
```
Before:  scope doc ingest design-v1.pdf    → generates .ai-context/
Later:   scope doc ingest design-v2.pdf    → OVERWRITES .ai-context/
Result:  All knowledge from v1 is gone
```
With episodes:
```
scope mem episode create --label "pre-v2-ingest" --restore-point
scope doc ingest design-v2.pdf
# If v2 was wrong:
scope mem episode restore ep_004
```

### Problem 2 — Architectural Pivot Loses History
The engine changes from deterministic-rules to LLM-based. All old facts about
"engine must not call LLM" become stale, but they were valid for 6 months.
Episodes let Claude query: *"What was the engine constraint in episode ep_001?"*

### Problem 3 — Sharing Artifacts (Cross-Machine)
User A creates episode `ep_003`, exports it. User B imports it → they start
with an identical AI context state. This is cleaner than exporting raw files.

### Problem 4 — Conflict Resolution Over Time
When `detect_conflicts` finds a contradiction, it can now say:
*"This fact was true in ep_001 but contradicted in ep_003 — here's the delta."*

---

## CLI Design (proposed)

```bash
# Create an episode (snapshot current state)
scope mem episode create --label "sprint-3-start"
scope mem episode create --label "pre-refactor" --restore-point

# List episodes
scope mem episode list
# Output:
# ep_003  sprint-3-start       2025-02-20  HEAD
# ep_002  architecture-pivot   2025-02-01  restore-point
# ep_001  sprint-1-start       2025-01-15
# ep_000  initial-ingest       2025-01-10  restore-point

# Show what changed between episodes
scope mem episode diff ep_001 ep_003

# Restore to a prior episode (replaces live mempalace + features)
scope mem episode restore ep_001
scope mem episode restore ep_001 --dry-run   # preview only

# Query a fact as it existed in a specific episode
scope mem episode query ep_001 "engine constraints"

# Export an episode for sharing
scope mem episode export ep_003 --out sprint3-context.zip

# Import an episode from another machine
scope mem episode import sprint3-context.zip --label "from-alice"
```

---

## Trigger Strategies (when to auto-create episodes)

| Trigger | Description | Recommended? |
|---|---|---|
| `scope doc ingest` | Always create episode before overwriting | ✅ Yes |
| `scope mem decay` | Create episode before confidence decay run | ✅ Yes |
| Git tag push | Auto-episode on `git tag v1.0` | ✅ Yes (via hook) |
| Time-based | Daily/weekly automatic snapshot | ⚠️ Optional |
| Manual | User explicitly creates | ✅ Yes (always available) |
| `scope mem import` | Before importing external memories | ✅ Yes |

---

## How It Interacts With Doc Ingest

```
Step 0:  scope doc ingest design-v2.pdf
           └── Auto-creates episode ep_N (restore point) before writing
           └── Ingest runs, generates all .ai-context/ files
           └── Auto-creates episode ep_N+1 (post-ingest state)
```

Claude can then reference: *"context at ingest of design-v1"* vs *"context after v2 ingest"*

---

## Relation to Compact DSL

Episodes and DSL complement each other:
- DSL compresses what is stored in each episode snapshot (~70% smaller)
- Episodes track how the DSL-encoded knowledge evolves over time
- A restore returns Claude to a compact, efficient prior state — not bloated prose

---

## Where Episodic Memory Helps Most

| Scenario | Benefit |
|---|---|
| Multi-sprint projects | Track how AI understanding evolved each sprint |
| Architecture pivots | Restore pre-pivot context to understand old decisions |
| Multi-developer teams | Share a specific episode as a "starting point" |
| Risky refactors | Create restore point, refactor, revert if needed |
| Doc ingest v2+ | Don't lose v1 knowledge when ingesting updated docs |
| Conflict investigation | "This conflict first appeared between ep_002 and ep_003" |

---

## Where Episodic Memory Hurts

- **Storage overhead** — each episode duplicates `mempalace.jsonl` + `features.json`.
  Mitigation: store delta-only for non-restore-point episodes; full copy only for restore points.
- **Episode sprawl** — daily auto-triggers create noise. Keep auto-triggers selective.
- **Merge complexity** — if two episodes are created in parallel (two devs), merging is hard.
  Recommendation: single linear chain, no branching (like a simple git linear history).
- **False sense of safety** — `.ai-context/` markdown files are NOT in the snapshot by default.
  User must understand what IS and IS NOT restored.

---

## Implementation Estimate (if approved)

| Component | Effort |
|---|---|
| Episode data model + storage layout | 2h |
| `episode create` + auto-trigger hooks | 3h |
| `episode list` + `episode diff` | 2h |
| `episode restore` (mempalace + features) | 3h |
| `episode export` / `episode import` (zip) | 2h |
| Integration with `doc ingest` (auto pre/post episodes) | 1h |
| CLI wiring | 2h |
| Tests | 3h |
| **Total** | **~18h** |

---

## Decision Gate — When to Use This Technique

Use episodic memory if:
- [ ] Project spans multiple sprints or phases (long-lived)
- [ ] Doc ingest will be re-run on updated documents
- [ ] Multiple developers share AI context
- [ ] Architecture pivots are likely
- [ ] Conflict detection needs temporal context ("when did this conflict appear?")

Skip episodic memory if:
- [ ] Single short project (one doc ingest, done)
- [ ] Solo developer, single machine, no sharing needed
- [ ] Storage space is constrained
