---
name: bee-memory
description: >
  The Bee Layer — distributed swarm retrieval and procedural memory for AI systems.
  No single bee knows everything. Specialised workers each own one domain.
  The queen orchestrates. Consensus aggregates. The hive produces honey.
  Philosophy: collective networked intelligence under guided orchestration.
status: candidate
relates_to: nature-memory-framework, eagle-retrieval, scope-intelligence-toolkit
---

## The Philosophy — Networked Collective Intelligence Under a Queen

The elephant is famous for individual depth of memory.
The bee is famous for something categorically different: **collective intelligence at scale**.

50,000 bees build a hive. No single bee designed it. No single bee knows the blueprint.
Yet the result is geometrically perfect hexagonal structure, precisely temperature-regulated,
with honey produced, stored, and rationed against winter — all without a central planner.

**The Queen's role (corrected from earlier analysis):**
The queen does NOT direct individual worker tasks. She is not a micromanager.
She sets the colony's biological purpose and cohesion — the "why we exist."
Individual workers self-organise within that purpose through local signals.

This maps to an **orchestrator agent** that:
- Receives the high-level intent (the user's question)
- Decomposes it into sub-queries
- Dispatches specialised worker agents
- Receives and aggregates their results
- Returns the synthesised answer (the honey)

**The workers each know one thing deeply — and do it in parallel.**

---

## Verified Biology — What Was Missed Before

- **Queen = orchestrator of purpose, not task.** She emits pheromones that govern colony direction and cohesion. Workers self-route within that signal. This is coordination without micromanagement.
- **Worker castes are specialised by role AND by age.** A young worker bee starts as a nurse (feeds larvae), then becomes a builder (wax comb), then a guard (hive entrance), then a forager (external search). Each caste handles one domain exclusively.
- **Waggle dance = distributed consensus, not single-answer retrieval.** Multiple scouts report back on different flower locations by dancing simultaneously. Better sources attract more followers. The hive converges on the best source through competing, weighted signals — not a single vote.
- **Parallel foraging:** Thousands of forager bees search simultaneously in different directions. The hive doesn't send one scout and wait. It sends thousands — each specialised to one zone — and aggregates.
- **Colony memory is distributed:** No bee holds the colony's full knowledge. Remove any 10,000 bees and the hive continues. The knowledge is in the structure, the roles, and the signalling — not in any individual.

---

## The Two Dimensions of the Bee Principle

### Dimension 1 — Distributed Swarm Retrieval
Specialised worker agents search in parallel, each owning one memory domain.
Results are ranked and combined through a consensus mechanism (waggle dance equivalent).

### Dimension 2 — Procedural Collective Memory
The hive "knows" how to make honey, how to regulate temperature, how to defend —
not because any bee knows it, but because the procedures are encoded in roles and signals.
No individual holds the procedure. The colony is the procedure.

These are the same principle at two levels: retrieval (finding) and memory (knowing).

---

## The Swarm Retrieval Architecture

When a user asks a complex question, one search agent cannot handle it well.
The bee principle: **decompose into specialised workers, run in parallel, aggregate by consensus.**

```
QUEEN AGENT (orchestrator)
  Input:  user query
  Step 1: classify query intent and decompose into sub-queries
  Step 2: dispatch N worker agents in parallel
  Step 3: collect worker results
  Step 4: waggle-dance consensus (weighted ranking)
  Step 5: return synthesised answer
  Output: ranked, aggregated answer with source attribution
```

### The Six Specialised Worker Agents

```
Worker W1 — Recent Docs Agent
  Domain:   documents ingested or updated in last 7–30 days
  Strength: finds what changed recently, catches stale-vs-fresh conflicts
  Searches: episodic layer, doc-ingest timestamps

Worker W2 — People & History Agent
  Domain:   decisions made, who decided, when, and why
  Strength: "we chose JWT because..." attribution + historical context
  Searches: episodic layer, decision records, episode restore points

Worker W3 — Metrics & Events Agent
  Domain:   error logs, performance data, git events, test results
  Strength: quantitative evidence, "auth fails 23% of the time after change X"
  Searches: auto-capture events, commit metadata, numeric facts

Worker W4 — Prior Decisions Agent
  Domain:   architectural decisions, constraints, why-we-built-it-this-way
  Strength: prevents re-litigating resolved decisions, surfaces rationale
  Searches: semantic layer (constraints, decisions), curated docs

Worker W5 — Contradiction Agent
  Domain:   conflicting or contradictory evidence across all layers
  Strength: "there are two contradicting answers — here is both sides"
  Searches: conflict log, low-confidence facts, superseded entries

Worker W6 — External Updates Agent
  Domain:   information from outside the repo (API docs, library changelogs, standards)
  Strength: "the JWT library updated and this constraint may no longer apply"
  Searches: external-tagged semantic entries, recently imported facts
```

Workers run simultaneously. No worker waits for another.

---

## The Waggle Dance — Consensus Aggregation

Multiple workers return competing results. How do you pick the right answer?

In the hive: a scout that found a better source dances longer, more vigorously, attracting more followers. The best source wins through weighted competition — not a single authority deciding.

For AI aggregation:

```python
def waggle_consensus(worker_results: list[WorkerResult]) -> list[RankedResult]:
    """Aggregate results from all workers using weighted consensus scoring."""
    all_candidates = []
    for result in worker_results:
        for entry in result.entries:
            entry.worker_score = (
                entry.relevance_to_subquery * 0.35    # how well it matched the sub-query
                + entry.confidence               * 0.25    # memory confidence
                + entry.recency_score            * 0.20    # how recent
                + entry.cross_worker_frequency   * 0.20    # did multiple workers surface it?
            )
            all_candidates.append(entry)

    # Entries surfaced by multiple workers get consensus boost (waggle reinforcement)
    for entry in all_candidates:
        count = sum(1 for c in all_candidates if c.id == entry.id)
        entry.worker_score *= (1 + 0.15 * (count - 1))  # consensus multiplier

    return sorted(all_candidates, key=lambda e: e.worker_score, reverse=True)[:5]
```

**The key insight:** if W1 and W4 and W5 all return the same fact independently,
that fact is almost certainly the right answer. Cross-worker agreement = confidence.
This is exactly how multiple bees dancing the same direction creates hive consensus.

---

## Procedural Collective Memory — The Hive Knows How

The second dimension: procedures that no individual agent holds fully.

In the hive: the procedure for making honey is not stored in any bee's "brain."
It is encoded in the division of labour + the signalling protocol.

For AI systems: some procedures are too large for one agent's context window.
The colony encodes them as a **workflow across multiple agents**:

```
Procedure: "debug a production auth failure"
  Step 1: W3 (Metrics Agent) finds the error spike timeframe
  Step 2: W1 (Recent Docs Agent) finds what changed in that window
  Step 3: W4 (Decisions Agent) surfaces prior auth decisions that might be relevant
  Step 5: W5 (Contradiction Agent) checks if any constraints were violated
  Queen aggregates: timeline of events + relevant decisions + potential cause
```

No single agent held this procedure. The colony ran it.

This is how `.claude/skills/` work conceptually — each skill is a queen-level procedure
that dispatches work across tools and steps. The bee principle makes this explicit.

---

## Worker Lifecycle — Role Rotation

Young worker bees start with internal hive roles (nurse, builder) and graduate to external foraging.
Role = determined by age and colony need, not fixed assignment.

For AI agent systems: agents can take on different worker roles based on:
- Session context (debugging session → W3 and W5 are primary workers)
- Query type (architecture question → W4 and W2 are primary workers)
- Load (if W1 is busy → another agent picks up the recent-docs role)

Worker roles are not fixed to agent identity. The colony adapts.

---

## Application to Scope Intelligence Toolkit

**Current state**: `scope mem search "auth failure"` → one TF-IDF pass → 10 results.

**With bee swarm retrieval:**

```bash
scope mem search "why does auth fail after the JWT change?" --swarm
```

```
Queen dispatches:
  W1 (recent):       finds 2 entries changed in last 14 days about auth
  W2 (history):      finds decision record: "switched to JWT 2025-03-15"
  W3 (events):       finds git commit: "fix JWT expiry edge case" (3 days ago)
  W4 (decisions):    finds constraint: "JWT tokens must include user_id claim"
  W5 (conflicts):    finds conflict: "auth-module: sessions vs JWT (unresolved)"
  W6 (external):     no relevant external updates found

Waggle consensus:
  All workers agree on "JWT expiry" as the central entity
  W3's git commit + W4's constraint surfaced by 2+ workers → consensus boost

Final answer (5 results, ranked):
  1. [constraint] JWT tokens must include user_id claim (conf: 1.0, cross-worker: 3)
  2. [event]      git: fix JWT expiry edge case (2025-04-27, W1+W3 agree)
  3. [decision]   switched from sessions to JWT on 2025-03-15 (W2)
  4. [conflict]   auth: sessions vs JWT flagged unresolved (W5)
  5. [semantic]   auth-module uses JWT (conf: 0.9, reinforced: 7 times)
```

This is categorically better than a flat TF-IDF search.
Not because it searched more — because it searched in parallel, by role, with consensus.

---

## Application to Multi-Agent Product

The bee model is the native architecture for a multi-agent memory system:

```
User query → Queen Agent (decomposes)
                  ↓
    ┌─────────────┬──────────────┬──────────────┬─────────┐
    W1            W2             W3              W4        W5
    (Recent)      (History)      (Metrics)       (Decisions)(Contradiction)
    ↓             ↓              ↓               ↓          ↓
    results       results        results         results    results
    └─────────────┴──────────────┴──────────────┴──────────┘
                         ↓
                  Waggle Consensus
                         ↓
                  Final ranked answer
```

Each worker agent runs on a different machine, different memory partition, or different specialisation.
They do NOT share working state. They share only the final result pipeline to the queen.
This is the octopus model (local autonomy) combined with bee orchestration (collective output).

---

## Relation to Eagle

The eagle and the bee are complementary:
- **Eagle** narrows the search BEFORE it begins (intent → zone → suppression)
- **Bee** parallelises the search WITHIN the identified zones (swarm → consensus)

```
User query
  → Eagle: intent classification, zone selection (which 3 of 8 zones to search)
  → Bee:   dispatch W1/W4/W5 workers on those 3 zones in parallel
  → Eagle: re-rank final results before returning
```

Eagle is the filter. Bee is the parallelised engine within the filter's output.

---

## Implementation Estimate

| Component | Effort |
|---|---|
| Queen orchestrator (query decomposer) | 3h |
| 6 specialised worker agent templates | 4h |
| Parallel dispatch + result collection | 3h |
| Waggle consensus scoring | 2h |
| Cross-worker agreement detection | 2h |
| Worker role rotation based on query type | 2h |
| CLI: `scope mem search --swarm` | 2h |
| Integration with Eagle (pre/post filter) | 2h |
| Tests | 4h |
| **Total** | **~24h** |
