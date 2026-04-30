---
name: elephant-memory
description: >
  The Elephant Layer — semantic long-term memory for AI systems.
  Stores stable, high-value, repeatedly-reinforced facts about a domain.
  Distinct from episodic (what happened) and relational (how things connect).
  Nature model: elephant's recall of routes, individuals, danger patterns.
status: candidate
relates_to: nature-memory-framework, episodic-memory, scope-intelligence-toolkit
---

## What the Elephant Actually Does (Fact Check)

Verified biological facts about elephant memory:

- Remember individual humans by face + voice after 12+ years of separation
- Navigate to water sources 50–150km away based on memory from years prior
- Remember "trustworthy" vs "threatening" humans even on first re-encounter
- Mourn at locations where a herd member died — location-tagged emotional memory
- Pass migration routes across generations (cultural/procedural memory hybrid)
- Forget trivial events — they do NOT remember everything

**The key insight:** Elephant memory is *selectively durable* based on:
1. Emotional significance (threat, bond, loss)
2. Survival relevance (water, food, danger)
3. Repetition (route walked many times → strongly encoded)
4. Recency reinforcement (revisiting a memory strengthens it)

---

## What Semantic Memory Is (and Is Not)

### IS:
- Stable facts about the world: "X uses Y", "Z is the owner of A", "system B must not call C"
- Domain truths that don't change with each event: "auth module uses JWT"
- Entity properties: "database: PostgreSQL, version: 15, role: primary"
- Constraints and invariants: "PII must never be logged"
- Established patterns: "we use repository pattern for all data access"

### IS NOT:
- "Yesterday we changed the auth approach" (→ episodic)
- "Auth module depends on user module" (→ relational)
- "When auth fails, fallback to guest session" (→ procedural)
- "In sprint 3 we decided to use JWT" (→ episodic + decision record)

The error most systems make: storing episodic events as semantic facts,
then wondering why the semantic store is inconsistent.

---

## Semantic Memory Storage Design

### Schema

```jsonl
{"id": "sem_001", "subject": "auth-module", "predicate": "uses", "object": "JWT", "confidence": 0.95, "reinforcement_count": 7, "first_seen": "2025-01-10", "last_reinforced": "2025-03-01", "source": "doc-ingest:design-v2.pdf", "tags": ["auth", "security"]}
{"id": "sem_002", "subject": "system", "predicate": "must-not", "object": "log-PII", "confidence": 1.0, "reinforcement_count": 12, "first_seen": "2025-01-05", "last_reinforced": "2025-04-01", "source": "constraints-doc", "tags": ["constraint", "security", "pii"]}
{"id": "sem_003", "subject": "database", "predicate": "is", "object": "PostgreSQL-15", "confidence": 0.9, "reinforcement_count": 4, "first_seen": "2025-01-10", "last_reinforced": "2025-02-15", "source": "auto-capture:git", "tags": ["infrastructure", "database"]}
```

### Key Fields

| Field | Purpose |
|---|---|
| `subject` | What this fact is about (entity) |
| `predicate` | Relationship type (uses, is, must-not, owns, depends-on) |
| `object` | The value or target entity |
| `confidence` | 0.0–1.0, decays if not reinforced |
| `reinforcement_count` | How many times this fact has been re-confirmed |
| `last_reinforced` | Used for decay calculation |
| `source` | Where this fact came from |

---

## The Value Signal — How to Decide What to Keep

The elephant doesn't store everything. It uses biological "value signals."
For the Elephant Layer, compute memory value as:

```python
def memory_value(entry: dict, now: datetime) -> float:
    age_days = (now - entry["last_reinforced"]).days
    recency_score = math.exp(-age_days / 90)           # 90-day half-life baseline

    return (
        entry["reinforcement_count"]  * 0.35   # repeated = important
        + entry["confidence"]          * 0.25   # high confidence = trust it
        + recency_score                * 0.20   # recent = relevant now
        + _downstream_count(entry)    * 0.20   # many things depend on it
    )
```

`_downstream_count` = how many other facts or features reference this subject.
A fact that 10 other components depend on is worth preserving even if old.

**Eviction rule**: facts below threshold → mark as `stale` → offer for review → delete.
Never auto-delete without a review pass (unlike episodic events which can auto-expire).

---

## Reinforcement — How Semantic Memory Stays Current

Nature: walking the same route repeatedly → route memory strengthens.
AI equivalent: every time a fact is *used* (retrieved and acted on), reinforce it.

```python
def reinforce(fact_id: str, strength: float = 1.0):
    """Called when a fact is retrieved and confirmed correct."""
    entry = lookup(fact_id)
    entry["reinforcement_count"] += strength
    entry["confidence"] = min(1.0, entry["confidence"] + 0.02 * strength)
    entry["last_reinforced"] = now()
```

Also reinforce when:
- Same fact appears again in a new doc ingest
- Claude confirms the fact is still valid during a session
- An agent explicitly validates the fact

---

## Supersession — How Semantic Facts Update

When a new contradicting fact appears, do NOT just add it alongside the old one.
That creates drift and contradiction.

```python
def upsert_semantic(new_fact: dict):
    existing = find_by_subject_predicate(new_fact["subject"], new_fact["predicate"])
    if existing:
        if new_fact["object"] != existing["object"]:
            # Contradiction — log a conflict event, then supersede
            log_conflict(existing, new_fact)
            archive_to_episodic(existing)  # keep history in episodic layer
            replace(existing, new_fact)
        else:
            # Same fact reconfirmed — reinforce
            reinforce(existing["id"])
    else:
        insert(new_fact)
```

The old fact moves to the episodic log ("on date X, auth used sessions, not JWT").
The semantic layer stays clean and contradiction-free.

---

## Query Interface

```python
# What is true about X?
semantic.query(subject="auth-module")
# → [uses: JWT, owner: backend-team, status: stable]

# All constraints in the system
semantic.query(predicate="must-not")
# → [log-PII, store-plaintext-passwords, expose-internal-ids]

# Everything tagged "security"
semantic.query(tags=["security"])

# High-confidence stable facts only
semantic.query(confidence_min=0.8, reinforcement_min=3)

# What changed since sprint-2? (hybrid semantic + episodic query)
semantic.query(last_reinforced_after="2025-02-01")
```

---

## Consolidation — Episodic → Semantic Promotion

This is the most important process the Elephant Layer needs.

When an episodic event is seen N times → promote to semantic fact:

```
Event log:
  2025-01-10: "auth uses JWT" (from doc-ingest)
  2025-01-20: "auth uses JWT" (from git commit message)
  2025-02-01: "auth uses JWT" (from code scan)

After 3 occurrences → consolidation agent promotes to:
  semantic: {subject: auth, predicate: uses, object: JWT, confidence: 0.85, reinforcement_count: 3}
```

Consolidation should run:
- After `doc ingest`
- After `mem auto-capture`
- On a schedule (daily/weekly)
- On explicit trigger: `scope mem consolidate`

---

## Application to Scope Intelligence Toolkit

Current `mempalace.jsonl` stores facts of all kinds in one file.

The Elephant Layer extracts the "stable facts" subset:
- All `kind: fact` entries → candidate for semantic layer
- Filter: reinforcement_count ≥ 2 AND confidence ≥ 0.6 → confirmed semantic fact
- Rest stay as episodic events

Immediate value for doc ingest:
- When `scope doc ingest` runs on v2 of a doc
- Elephant Layer detects: "auth: JWT" was already in semantic store
- Instead of overwriting: reinforce the existing fact + log the reconfirmation
- If v2 says "auth: OAuth" instead → conflict detected, old fact archived, new fact stored

This makes doc ingest *cumulative* rather than destructive — exactly what the user asked for.

---

## Application to Multi-Agent Product

Each agent in the multi-agent system reads from the shared Elephant Layer:

```
Agent A: "What authentication approach does this system use?"
  → routes to Elephant Layer
  → returns: {uses: JWT, confidence: 0.95, last_reinforced: 2025-04-01}
  → Agent A trusts this without re-reading the source doc

Agent B (different machine, same Elephant Layer via sync):
  → same query, same answer
  → consistent context across agents automatically
```

The Elephant Layer becomes the **source of truth** that all agents share.
No agent needs to re-derive stable facts from raw documents.

---

## Implementation Estimate

| Component | Effort |
|---|---|
| Semantic store schema + CRUD | 2h |
| Value signal computation | 1h |
| Reinforcement + supersession logic | 2h |
| Consolidation agent (episodic → semantic) | 3h |
| Query interface | 2h |
| Integration with doc-ingest pipeline | 2h |
| CLI: `scope mem semantic query/list/decay` | 2h |
| Tests | 3h |
| **Total** | **~17h** |

---

## Decision Gate

Build the Elephant Layer if:
- [ ] The same facts appear in multiple sources (need dedup + reinforcement)
- [ ] Doc ingest will run multiple times on updated documents
- [ ] Multiple agents or developers need consistent stable facts
- [ ] Conflict detection needs to distinguish "stable truth vs episodic event"

Stay flat if:
- [ ] Single doc ingest, single developer, no updates
- [ ] Queries are simple substring searches (TF-IDF is enough)
