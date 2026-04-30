---
name: eagle-retrieval
description: >
  The Eagle Layer — selective attention and multi-stage retrieval for AI memory.
  The eagle does not store memory — it governs HOW memory is accessed.
  Filters aggressively before committing to deep retrieval.
  "Elephant stores. Eagle chooses."
status: candidate
relates_to: nature-memory-framework, elephant-memory, spider-memory, bee-memory, scope-intelligence-toolkit
---

## The Critical Insight — Eagle Locks On to What It Can Already See

### Eagle vs Heron — The Sharpest Distinction in the Framework

Both are precision predators. Both filter aggressively. Completely different contexts.

**Eagle:** The target is **visible**. The rabbit is already in the field, already moving.
The eagle's job is to *choose which of the visible targets to commit to*, lock its forward fovea
on it, suppress everything else, and dive at the right moment.
The eagle operates on **existing, visible signals** — it selects from what's already there.

**Heron:** The target is **not yet visible** — it's under the water surface.
The heron watches for the *moment something reveals itself*, then strikes instantly.
The heron operates on **hidden signals that haven't surfaced yet**.

```
Eagle:  query arrives (visible signal) → choose what to focus on → lock → act
Heron:  nothing visible yet → sustained watch → threshold crossed → strike
```

For AI:
- Eagle runs **at query time** — a query has arrived, eagle decides which memory zones to open
- Heron runs **before the query** — watching passively until something is worth acting on

**"Elephant stores. Eagle chooses what to retrieve from what's visible."**

---

Every other nature-inspired layer (elephant, crow, spider, bee) is about STORAGE.
The eagle is different. It is the **retrieval governor** — it sits above all layers
and decides what gets looked at, in what order, with how much attention.
It operates on the **query that has already arrived** — the signal is visible, the eagle chooses.

This distinction matters enormously in system design:
- Without eagle: every query hits all memory layers, returns N results, user filters
- With eagle: query is pre-processed, only the 2–3 most relevant memory zones are touched, results are already ranked

---

## What the Eagle Actually Does (Fact Check)

Verified biology:

- **4–8× better visual acuity** than humans — but not because they have more pixels. They have a denser fovea (more photoreceptors per mm²) in a smaller focus zone. They see *more in the target area*, not more overall.
- **Two foveas** (humans have one): a forward fovea for focused lock-on, and a lateral fovea for wide-angle peripheral scan. Pre-filter with peripheral, then lock with forward fovea.
- **Static suppression**: Eagles are neurologically wired to suppress non-moving background. The forest literally does not register — only the moving rabbit does. They filter first, then see.
- **Commitment under uncertainty**: Eagles commit to a dive before they have 100% certainty. They make probabilistic decisions at the right threshold — not waiting for perfect information.
- **Perch-and-scan strategy**: Not always flying and always scanning. They perch high (low energy), do a wide passive scan, detect a signal worth pursuing, THEN commit (high energy dive). Attention has a cost — they spend it selectively.
- **Track moving targets in noise**: A rabbit running through undergrowth is visually noisy. Eagle locks onto the motion vector, not the static frame.

---

## The Two-Fovea Architecture — Most Important Biological Fact

This is the detail most analyses miss. The eagle has two distinct attention modes:

```
LATERAL FOVEA (wide angle, low resolution, fast)
  Purpose: ambient scanning, anomaly detection
  Cost:    very low
  Output:  "something is moving in zone 3"

FORWARD FOVEA (narrow angle, high resolution, slow)
  Purpose: target lock-on, precise tracking
  Cost:    high
  Output:  "rabbit, 47cm, moving SE at 8mph, 200m away"
```

These run in sequence, not in parallel. First lateral, then forward.

**For AI retrieval, this maps to two-stage retrieval:**

```
STAGE 1 — Wide scan (lateral fovea equivalent)
  Operation: cheap keyword match / BM25 across all memory zones
  Cost:      O(n), milliseconds
  Output:    "likely relevant zones: semantic/auth, episodic/last-7-days"

STAGE 2 — Focused retrieval (forward fovea equivalent)
  Operation: deep semantic search / LLM re-ranking within selected zones only
  Cost:      expensive, but on 50 candidates, not 50,000
  Output:    top-3 highly relevant results
```

The expensive operation is reserved for the final candidates.
This is the core architecture of modern RAG (Retrieval-Augmented Generation)
when done correctly — but here it has a principled biological justification.

---

## Static Suppression — What Gets Ignored by Design

The eagle ignores the forest. It is not lazy — it is neurologically suppressing it.

For AI memory retrieval, the equivalent of "static background":
- Facts that haven't changed in 90+ days and haven't been accessed recently
- Semantic facts with confidence = 1.0 that are never questioned (they're background truth)
- Procedural memory for task types not matching the current query intent
- Episodic events outside the relevant time window

```python
def apply_static_suppression(memory_zones, query_context):
    """Filter out background memory before the focused retrieval pass."""
    active_zones = []
    for zone in memory_zones:
        # Only include if: recently changed, or directly entity-matched, or anomalous
        if (zone.last_updated_days < 30
                or zone.entity in query_context.entities
                or zone.confidence_volatility > 0.2):  # "moving target"
            active_zones.append(zone)
    return active_zones
    # Suppressed zones are not fetched at all — they don't exist for this query
```

---

## The Full Multi-Stage Retrieval Pipeline

When a user asks "why is the auth module failing after the JWT change?":

```
STAGE 1 — Intent Detection
  input:  raw query text
  detect: intent=debug, not design/understand/decide
  output: retrieval mode = "recent + anomalous + error-pattern"

STAGE 2 — Entity Extraction  
  input:  query + intent
  detect: entities = ["auth-module", "JWT"]
  output: primary_entity="auth-module", secondary_entity="JWT"

STAGE 3 — Time Relevance
  input:  query + entities
  detect: "after the JWT change" → time_scope = last_change_to_JWT
  output: time_window = "2025-03-15 to now"

STAGE 4 — Task Type Classification
  input:  intent + entities + time
  classify: task = "debug-failure" (not "understand-architecture")
  output:  memory_zones = [episodic/recent, semantic/auth, bee/debug-procedures]
           skip_zones  = [roadmap, procedural/onboarding, relational/unrelated-modules]

STAGE 5 — Static Suppression (lateral fovea)
  input:  memory_zones
  suppress: zones unchanged and not entity-matched
  output: 3 active zones instead of all 8

STAGE 6 — Coarse Retrieval (still lateral fovea)
  input:  3 active zones
  method: BM25 keyword match within each zone
  output: top-20 candidates (not top-1000)

STAGE 7 — Focused Re-ranking (forward fovea — expensive)
  input:  20 candidates
  method: semantic similarity + recency + confidence × relevance_to_intent
  output: top-3 ranked results

STAGE 8 — Response Assembly
  input:  3 results + query context
  output: answer with citations to source memory entries
```

Total memory loaded into Claude's context: 3 entries, not 200.

---

## Attention Gating — Spending Attention Where It Earns

The eagle doesn't fly for hours scanning everything. It has an energy budget.
Attention is the eagle's most expensive resource — it gates it deliberately.

For AI retrieval, the equivalent is compute budget:

```
CHEAP OPERATIONS (lateral fovea — run on everything):
  - Keyword match
  - Tag filter
  - Timestamp range filter
  - Entity presence check
  Cost: O(n), always runs

MEDIUM OPERATIONS (run on filtered set — top 50):
  - TF-IDF scoring
  - Confidence-weighted ranking
  - Time-decay adjusted score
  Cost: O(filtered_n)

EXPENSIVE OPERATIONS (forward fovea — run on top 10 only):
  - Semantic embedding similarity
  - LLM re-ranking
  - Cross-reference validation
  Cost: LLM call — only worth it if you've narrowed down to real candidates
```

**Attention gating rule**: never run an expensive operation on an unfiltered set.
The eagle never locks its forward fovea on a leaf that the lateral fovea already suppressed.

---

## Anomaly Focus — Moving Targets in Noise

Eagles are tuned to detect movement against a static background.
The "moving target" in AI memory = **recently changed, volatile, or contradicting facts**.

```python
def anomaly_score(memory_entry) -> float:
    """How 'moving' is this entry? High score = eagle should lock on."""
    return (
        _confidence_change_rate(entry)  * 0.4  # confidence fluctuating = uncertain
        + _recency_of_update(entry)     * 0.3  # just updated = worth checking
        + _conflict_flag(entry)         * 0.3  # flagged as conflicting = dangerous
    )
```

When debugging a failure: high-anomaly entries get retrieved first, before stable background facts.
When answering "what is the auth approach?" stable entries get retrieved (low anomaly = reliable).

**The retrieval mode switches based on intent:**
- `intent=debug` → sort by anomaly_score DESC (find the moving target)
- `intent=understand` → sort by confidence DESC (find the stable truth)
- `intent=decide` → sort by recency DESC (find what's most current)

---

## Commitment Under Uncertainty — When to Stop Refining

Eagles commit to the dive at the right threshold — not too early (miss the target), not too late (wasted energy + missed window).

For AI retrieval, the equivalent is knowing when to stop refining and return results:

```python
def should_commit(candidates, min_confidence=0.6, min_count=2):
    """Has the retrieval narrowed enough to commit?"""
    high_confidence = [c for c in candidates if c.relevance_score > min_confidence]
    if len(high_confidence) >= min_count:
        return True   # commit — we have enough high-quality candidates
    if len(candidates) < 5:
        return True   # commit — we've exhausted the relevant memory
    return False      # refine again — too many low-confidence candidates
```

Commitment threshold is context-sensitive:
- High-stakes query (architecture decision): threshold = 0.85 (wait for high confidence)
- Low-stakes query (quick fact check): threshold = 0.5 (commit early, save compute)

---

## The Perch-and-Scan Mode — Passive Monitoring

Not all eagle attention is active retrieval. Eagles spend most of their time perched —
doing a low-cost ambient scan, not committing attention until a signal is worth pursuing.

For AI memory systems, the equivalent is **passive indexing vs active retrieval**:

```
PERCH MODE (background, always on, cheap):
  - Monitor memory for new conflicts
  - Track anomaly scores as they change
  - Maintain a "hot list" of recently-changed entries
  - Update entity indexes when new facts arrive
  Cost: background thread, no LLM calls

SCAN MODE (triggered by perch signal):
  - Run lateral fovea (stages 1–5) when a query arrives
  - Build candidate set
  Cost: cheap, runs on every query

DIVE MODE (triggered by scan result):
  - Run forward fovea (stages 6–7) on selected candidates
  - Re-rank, validate, assemble response
  Cost: expensive, only when candidates identified
```

Most queries use Scan → Dive. Some use Perch output directly (if hot list already has the answer).

---

## Application to Scope Intelligence Toolkit

**Current state**: `scope mem search "auth"` → TF-IDF over entire mempalace.jsonl → 10 results.

**With eagle retrieval**:
```bash
scope mem search "why is auth failing after JWT change"
```
```
Eagle pipeline:
  intent:    debug
  entities:  [auth, JWT]
  time:      recent (last 30 days)
  zones:     [episodic/recent, semantic/auth, bee/debug-procedures]
  suppressed: [roadmap, onboarding, unrelated semantic facts]
  coarse:    20 candidates via keyword match
  fine:      3 results via confidence × recency × entity-match
  returned:  3 entries, not 10

Result:
  [sem_041] auth-module changed from sessions to JWT on 2025-03-15 (conf: 0.9)
  [ep_203]  git commit 2025-03-16: "fix JWT expiry handling" (type: fix)
  [proc_07] debug-auth-failure: check token expiry → refresh → re-auth (conf: 0.88)
```

Immediately useful. No noise.

---

## Application to Multi-Agent Product

In a multi-agent system, the eagle is the **query router + context loader** for each agent:

```
Claude agent starts a session:
  1. Eagle scans: what is this session about? (intent classification)
  2. Eagle identifies: active entities in this session
  3. Eagle loads: only the relevant memory zones (not all 4 layers)
  4. Eagle suppresses: background memory (unchanged facts, unrelated procedures)
  5. Agent works with: 3–5 highly relevant entries, not 200

Result: agent context window stays small, costs stay low, relevance stays high
```

This is how the scope intelligence toolkit already works conceptually (scoped context),
but the eagle gives it a principled, multi-layer, intent-aware retrieval engine.

---

## How Eagle Interacts With Each Memory Layer

| Layer | Eagle's role |
|---|---|
| Elephant (semantic) | Selects which semantic facts are relevant to this query's entities + intent |
| Crow (episodic) | Narrows time window + filters by event type matching query intent |
| Spider (relational) | Determines traversal depth (blast radius 1 hop vs 3 hops) based on query scope |
| Bee (procedural) | Matches procedures by trigger pattern, not by scanning all procedures |
| Episode restore | Determines if a past episode is relevant to compare against current state |

Without the eagle, loading all layers for every query is prohibitively expensive.
With the eagle, each layer is accessed surgically.

---

## Implementation Estimate

| Component | Effort |
|---|---|
| Intent classifier (rule-based first, LLM optional) | 2h |
| Entity extractor (regex + known entity list) | 2h |
| Time relevance detector | 1h |
| Task type classifier → zone selector | 2h |
| Static suppression filter | 1h |
| Coarse retrieval (BM25 over selected zones) | 2h |
| Fine re-ranking (score formula, no LLM needed) | 2h |
| Anomaly score computation | 1h |
| Commitment threshold logic | 1h |
| CLI: `scope mem search` upgrade to eagle pipeline | 2h |
| Tests | 3h |
| **Total** | **~19h** |

---

## Decision Gate

Build the eagle layer if:
- [ ] Memory has grown beyond a single file (multiple layers exist)
- [ ] Search results feel noisy or irrelevant (high recall, low precision)
- [ ] Token budget is being hit by loading too much context
- [ ] Multiple agents need fast, scoped context loading at session start
- [ ] Query volume is high enough that expensive full-scan is a bottleneck

Stay with flat TF-IDF if:
- [ ] Memory is still a single small file (< 200 entries)
- [ ] All queries are simple keyword searches with no intent nuance
- [ ] Single-developer, single-session, no multi-agent
