---
name: octopus-memory
description: >
  The Octopus Model — distributed autonomous memory for multi-agent systems.
  No central coordinator. Each agent has local autonomy + shared collective state.
  GPT missed this entirely. The most important model for multi-agent architecture.
status: candidate
relates_to: nature-memory-framework, scope-intelligence-toolkit
---

## Why the Octopus Model — GPT's Biggest Miss

GPT described a society of memories but then implied a central coordinator routes everything.
That's not how nature solved it. The octopus is.

**Verified biology:**
- 500 million neurons total. Only 50 million in the central brain. The other 450 million (90%) are distributed across 8 arms.
- Each arm can taste, feel, grip, and react to objects independently — without consulting the brain
- If you sever an octopus arm, it continues reacting to stimuli for an hour — the local memory and reflexes persist
- The central brain sets high-level intent: "explore that crevice"
- The arm executes locally: grip, probe, texture-sense, recoil from danger — without waiting for brain approval
- Global coherence: the brain knows the arm's general state but not every micro-decision

**This is the correct model for multi-agent AI systems.**

---

## The Central Problem With Centralized Routing

```
❌ Centralized model (GPT's implicit assumption):
   All agents → central coordinator → routes to right memory layer → returns answer

Problems:
  - Coordinator is a single point of failure
  - Every query must pay the round-trip to coordinator
  - Coordinator must know about every memory layer (tight coupling)
  - Doesn't scale to many agents
  - If coordinator is offline, no agent can access any memory
```

```
✅ Octopus model:
   Each agent has LOCAL memory (fast, autonomous)
   Agents share a THIN collective state (slow sync, eventual consistency)
   No central coordinator needed for local decisions
   Coordinator only needed for: conflict resolution + global compaction

Benefits:
  - Agent can act immediately on local memory
  - No network round-trip for common queries
  - Coordinator failure = agents still function (degraded, not dead)
  - Scales horizontally (add more agents, each brings local capacity)
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  OCTOPUS MULTI-AGENT MEMORY                                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Agent A               Agent B               Agent C             │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐   │
│  │LOCAL MEMORY  │      │LOCAL MEMORY  │      │LOCAL MEMORY  │   │
│  │  episodic    │      │  episodic    │      │  episodic    │   │
│  │  procedures  │      │  procedures  │      │  procedures  │   │
│  │  local graph │      │  local graph │      │  local graph │   │
│  └──────┬───────┘      └──────┬───────┘      └──────┬───────┘   │
│         │                     │                      │            │
│         └─────────────────────┴──────────────────────┘           │
│                               │                                   │
│                   ┌───────────▼────────────┐                     │
│                   │  SHARED COLLECTIVE     │                     │
│                   │  MEMORY (thin sync)    │                     │
│                   │  • semantic facts      │                     │
│                   │  • relational graph    │                     │
│                   │  • conflict log        │                     │
│                   └───────────┬────────────┘                     │
│                               │                                   │
│                   ┌───────────▼────────────┐                     │
│                   │  CONSOLIDATION AGENT   │                     │
│                   │  (async, not required  │                     │
│                   │   for normal operation)│                     │
│                   └────────────────────────┘                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## What Goes Local vs Shared

### Local Memory (per agent — fast, no sync needed)
- Recent episodic events for this agent's session
- Frequently-used procedures (cached locally after first pull from shared)
- Working context: what this agent is currently doing
- Agent-specific scratch space

### Shared Collective Memory (slow, eventually consistent)
- Semantic facts (elephant layer) — the stable truths all agents need
- Relational graph (spider layer) — structure that spans agents
- Conflict log — contradictions detected by any agent
- High-confidence procedures that have been promoted from local

### Never Shared
- Agent's in-progress work (like an octopus arm's micro-decisions)
- Agent-specific user preferences
- Ephemeral context (what Claude is currently thinking about)

---

## The Sync Protocol (thin and async)

```
Agent A writes a new fact:
  1. Writes to local episodic immediately (no wait)
  2. Queues an async sync event: "new fact: auth uses OAuth (confidence: 0.7)"
  3. Continues working — does not wait for sync

Consolidation agent runs (async, on schedule):
  1. Pulls sync queues from all agents
  2. Deduplicates + merges (new fact reinforces existing or triggers conflict)
  3. Promotes to shared semantic layer
  4. Broadcasts delta: "semantic layer updated: auth now uses OAuth"

Agent B receives delta:
  1. Invalidates its local cache for "auth" facts
  2. Next time it queries auth → pulls from shared semantic
```

This is identical to how distributed databases work (eventual consistency) but designed specifically for AI memory semantics.

---

## Conflict Resolution Without a Central Coordinator

In the octopus: when an arm encounters a contradiction (push vs pull), local reflexes resolve it. The brain is only notified of the outcome.

For multi-agent memory:

```python
# Agent A discovers: "auth uses JWT"
# Agent B discovered earlier: "auth uses OAuth"
# Both write to shared semantic layer

# Conflict detected (same subject+predicate, different object):
conflict = {
  "subject": "auth",
  "predicate": "uses",
  "value_a": "JWT",    "source_a": "Agent A, 2025-04-01",
  "value_b": "OAuth",  "source_b": "Agent B, 2025-03-15",
  "resolution": "pending"
}

# Resolution options (no central authority needed):
# 1. Latest wins: JWT (more recent) supersedes OAuth
# 2. Higher confidence wins
# 3. Flag for human review (if both high confidence)
# 4. Both are true: they coexist in different contexts (auth-internal vs auth-external)
```

The consolidation agent applies resolution rules and logs the outcome — no human coordinator required for common cases.

---

## The "Severed Arm" Property — Resilience

If one agent loses network access to the shared memory:
- It continues functioning on local memory (like a severed octopus arm)
- Its recent work is queued for sync when connection resumes
- Other agents are unaffected
- No work is lost — local buffer preserves events until sync succeeds

This is a critical property for:
- Multi-developer teams where one person is offline
- Agents working on separate features in parallel
- Edge deployments (agents on different machines, different networks)

---

## Application to Scope Intelligence Toolkit (Near Term)

The toolkit currently runs as a single agent on a single machine.
The octopus model becomes relevant when:
1. Multiple Claude sessions run simultaneously on the same repo
2. Multiple developers each run Claude with scope-intel on the same codebase
3. A MCP server runs as a persistent background agent while Claude is ephemeral

Immediate application even in single-agent use:
- Local memory = in-session working context (not persisted)
- Shared memory = `.scope-intelligence/` files (persisted, the "collective")
- Session start: load shared memory into local context
- Session end: push session facts to shared memory

This is already how it works implicitly — the octopus model just makes it explicit and extensible to true multi-agent.

---

## Application to Multi-Agent Product (New Product)

If building a new multi-agent memory system:

```
Product name (suggestion): NeuralHive or OctoMem
Core abstraction: Agent with LocalBrain + shared HiveMind
Key APIs:
  agent.remember(fact)          → writes to local episodic
  agent.sync()                  → push local events to shared
  agent.recall(query)           → local first, shared fallback
  agent.consolidate()           → async: local episodic → shared semantic
  hive.resolve_conflict(id)     → conflict resolution protocol
  hive.broadcast(delta)         → push shared update to all agents
```

---

## Comparison: Centralized vs Octopus

| Property | Centralized | Octopus |
|---|---|---|
| Single point of failure | Yes | No |
| Query latency | Always network round-trip | Local first (fast) |
| Consistency | Strong | Eventual |
| Scalability | Limited by coordinator | Horizontal |
| Conflict resolution | Central decides | Distributed + async |
| Offline resilience | Agent dies without coordinator | Agent degrades gracefully |
| Complexity | Simple routing, complex coordinator | Simple agents, async sync |

---

## Implementation Estimate (for multi-agent product)

| Component | Effort |
|---|---|
| Local memory store per agent | 3h |
| Shared collective memory (file-based or DB) | 4h |
| Async sync protocol + event queue | 5h |
| Conflict detection + resolution rules | 4h |
| Consolidation agent | 5h |
| Broadcast / delta notification | 3h |
| Offline resilience (local buffer + catchup) | 3h |
| Tests | 5h |
| **Total** | **~32h** |
