---
name: crow-inference
description: >
  The Crow Layer — multi-step inference, tool improvisation, and gap-bridging
  for AI memory retrieval. Triggered when no direct answer exists in any memory
  layer. The crow constructs an answer by reasoning across incomplete evidence
  from unexpected sources. Philosophy: don't accept the problem as stated —
  reframe it, find new tools, synthesise from what does exist.
status: candidate
relates_to: nature-memory-framework, eagle-retrieval, bee-memory, ant-trails, scope-intelligence-toolkit
---

## The Philosophy — Don't Accept the Problem As Stated

Every other layer in this framework assumes the answer exists somewhere in memory:
- Eagle narrows where to look
- Ant pre-stages a known chain
- Bee searches in parallel across zones

**The crow starts where all of them fail.**

When Betty the crow was shown a tube with food at the bottom — too deep for her beak —
she didn't try harder. She didn't call for help. She didn't give up.
She paused. She looked at a straight wire nearby. She picked it up. She bent it into a hook.
She retrieved the food.

This had never been observed before. She improvised a tool that wasn't in the original problem.
She **reframed what resources were available**, then solved it with the new framing.

**Philosophy: the answer you need may not exist in the form you're asking for.
But it can often be constructed from what does exist — if you reason across it differently.**

The crow is the inference agent. It bridges missing data, invents query paths,
and synthesises answers from partial evidence across unexpected sources.

---

## What Crows Actually Do (Verified Facts — More Than GPT Captured)

- **Betty the hook experiment**: bent a straight wire into a hook to extract food from a tube. The specific shape required was not learned — it was invented on the spot. This is **tool manufacture to a novel specification.**
- **Multi-step sequential planning**: New Caledonian crows plan 3–5 steps ahead. Critically, they observe the result of step 1 before committing to step 2. This is **sequential reasoning with mid-course observation and adjustment** — fundamentally different from bee parallelism.
- **Causal reasoning (Aesop's fable test)**: drop stones into a tube to raise water level. Crows select heavy/solid stones over light/hollow ones. They understand the *mechanism*, not just the outcome. They have a **causal model of their tools.**
- **Theory of mind**: crows know whether they were observed while caching food. If watched, they re-cache later in private. They **model what another agent knows** and act on that model.
- **Face recognition + grudge holding**: crows remember specific human faces for years and recruit other crows to mob specific individuals. Memory of past agent behavior informs future interaction.
- **Learning from others' failures**: crows observe dead crows and treat the location and circumstances as a warning signal. They **learn from failure events they didn't personally experience.**
- **Insight before action**: crows show a distinct "pause and stare" before solving novel problems — suggesting mental simulation of the solution before physical execution. The answer is **constructed mentally first.**
- **The "aha" property**: unlike ants (incremental) or bees (parallel), crows have moments of discontinuous insight — the solution arrives whole, not iteratively.

---

## The Critical Difference — Sequential With Observation

This is what separates crow from all other layers and is the most important architectural insight:

```
Bee (parallel, no observation between steps):
  W1, W2, W3, W4, W5, W6 all run simultaneously
  Results collected at end
  No step adjusts based on what a prior step found

Crow (sequential, observes result before next step):
  Step 1: query X → observe result → THEN decide step 2
  Step 2: query Y (adjusted based on step 1 result) → observe → THEN decide step 3
  Step 3: query Z (different source, chosen because step 2 revealed a gap)
  Step 4: synthesise across step 1 + 2 + 3 results
```

The bee is good when you know which workers to send.
The crow is necessary when you don't know what the next step is until the previous one completes.
This is the **exploratory reasoning loop** that the other layers cannot do.

---

## When the Crow Is Triggered

The crow is NOT the first layer — it's the last resort. It activates when:

```python
def should_invoke_crow(query_result: dict) -> bool:
    """Is the answer incomplete enough that crow inference is needed?"""
    return (
        query_result["confidence"] < 0.5         # low confidence in found answer
        or query_result["completeness"] < 0.6    # answer is partial / has gaps
        or query_result["has_why"] is False       # answer lacks rationale
        or query_result["sources_count"] < 2      # only one source — risky
        or query_result["contradictions"] > 0     # conflicting signals found
    )
```

Standard pipeline for a query that reaches the crow:

```
Eagle: narrows intent → "auth failure after JWT change"
Ant:   no strong trail for this exact problem type
Bee:   6 workers search → W3 finds error spike, W1 finds recent commit, W4 finds JWT constraint
       BUT: "why did this specific combination cause failure?" is not in any memory

Crow triggered:
  Observation: have error spike timestamp + JWT commit + JWT constraint
  Gap identified: missing — the mechanism connecting these three
  Step 1: query git diff for that commit → finds expiry field removed
  Step 2: query JWT constraint → "tokens must include user_id + expiry"
  Step 3: query error logs for "missing claim" → confirms expiry missing = 401
  Inference: JWT commit removed expiry field, violating constraint, causing 401s
  Synthesised answer: constructed from 3 sources + 2 inference steps
```

The bee found the pieces. The crow assembled them into an answer.

---

## The Multi-Source Synthesis Schema

When the crow runs, it builds a **reasoning chain** — not just a result:

```json
{
  "question": "Why did auth fail after the JWT change?",
  "direct_answer_found": false,
  "crow_reasoning": [
    {
      "step": 1,
      "query": "git diff for JWT-related commit in time window",
      "source": "episodic/git-events",
      "finding": "expiry field removed from token generation",
      "confidence": 0.9
    },
    {
      "step": 2,
      "query": "JWT constraints in semantic memory",
      "source": "semantic/constraints",
      "finding": "constraint: token must include user_id AND expiry claim",
      "confidence": 1.0
    },
    {
      "step": 3,
      "query": "error log pattern 'missing claim'",
      "source": "episodic/events",
      "finding": "401 errors with 'missing expiry claim' in body",
      "confidence": 0.85
    }
  ],
  "synthesised_answer": "The JWT commit removed the expiry field. The system constraint requires expiry in every token. Its absence caused 401 responses with 'missing claim' error.",
  "confidence": 0.88,
  "reasoning_chain_length": 3,
  "sources_used": ["git-events", "constraints", "error-logs"]
}
```

This is not just an answer — it is an **auditable reasoning chain** showing exactly
how the conclusion was reached and from which sources. The crow leaves its tracks.

---

## Tool Improvisation — Inventing the Query

The most powerful crow capability is not finding answers in existing queries —
it's **inventing queries that weren't pre-defined.**

When the ant trail says "check ticket → logs → config → deploy" for production issues,
the crow might discover a better tool: "the config file has a version timestamp —
check if config version changed within 5 minutes of the error spike."

That query wasn't in any trail. The crow invented it by reasoning about causality:
"errors need a cause, config changes cause errors, timestamp correlation = evidence."

```python
class CrowInferenceAgent:
    def infer(self, question: str, partial_results: list) -> InferenceResult:
        # Step 1: identify what's missing from partial results
        gaps = self._identify_gaps(question, partial_results)

        # Step 2: for each gap, reason about what type of evidence could fill it
        evidence_types = self._reason_about_evidence(gaps)

        # Step 3: for each evidence type, invent an appropriate query
        invented_queries = self._improvise_queries(evidence_types)

        # Step 4: execute queries sequentially, observe, adjust
        chain = []
        for query in invented_queries:
            result = self._execute(query)
            chain.append(result)
            # adjust next query based on what this one found
            invented_queries = self._adjust_remaining(invented_queries, result)

        # Step 5: synthesise across chain
        return self._synthesise(question, partial_results, chain)
```

The crow is the only layer that **generates new query strategies at runtime.**
All other layers execute pre-defined strategies. The crow improvises.

---

## Theory of Mind — Modelling the User's Knowledge Gap

Crows model what other agents know. The crow inference layer does the same:

**What the user knows** (explicit in their question):
- They mentioned "auth failure" → they know there's a failure
- They mentioned "JWT change" → they know there was a change
- They're asking "why" → they don't know the mechanism

**What the system knows** (in memory):
- The git commit, the constraint, the error logs

**The gap** (what neither knows yet):
- The causal chain connecting them

The crow agent explicitly models this gap:
```python
user_knowledge = extract_from_query(question)          # what they told us
system_knowledge = collect_from_memory(partial_results) # what we found
gap = user_knowledge.union(system_knowledge).complement(full_answer)
# gap = "the mechanism — how does A cause B?"
```

This allows the crow to generate precisely targeted inference steps — not random exploration,
but directed reasoning toward the identified gap.

---

## Learning From Failed Queries

Crows learn from others' deaths. The crow inference agent learns from its own failed steps:

```python
def on_step_failure(step: InferenceStep, error: str):
    """When a crow query finds nothing useful, record the dead end."""
    dead_end = {
        "question_type": step.question_type,
        "query_attempted": step.query,
        "source_searched": step.source,
        "why_failed": error,
        "context": step.context_tags
    }
    append_to_dead_ends_log(dead_end)
    # Next time a similar question arises, skip this dead-end path immediately
```

Over time, the crow builds a **dead-ends registry** — queries that reliably fail for
specific question types. These become negative trails (anti-pheromone equivalent):
the crow avoids them the next time it faces the same inference challenge.

This pairs with the ant layer: ant reinforces successful trails, crow registers dead ends.
Together they narrow the search space from both directions.

---

## Application to Scope Intelligence Toolkit

### Gap-bridging in doc ingest

When `scope doc ingest` processes a document and finds a section that says:
"We chose this approach because of the constraints described in the compliance section."

No direct answer to "why." The crow:
1. Notices: causal reference ("because of") with no local resolution
2. Searches: finds "compliance section" in document structure
3. Bridges: extracts relevant constraint from compliance section
4. Links: connects decision → constraint in the semantic layer

Without crow: the "why" is lost (mempalace gets the decision but not its rationale).
With crow: the full causal chain is captured.

### Gap-bridging in memory search

```bash
scope mem search "why did we abandon the original session-based auth?" --crow
```

```
Bee workers find: semantic/auth (JWT), episodic/sprint-1, decision-records/auth
Missing: the abandonment reason — no "why we stopped sessions" in memory

Crow inference:
  Step 1: search semantic for "sessions" → finds old fact [superseded]: auth used sessions
  Step 2: search episodic for events near the supersession date
           → finds: "performance issue: sessions too heavy for stateless API" commit note
  Step 3: cross-reference: stateless API constraint in curated/constraints.md
           → confirms: system constraint required stateless, sessions violated it

Synthesised:
  "Sessions were abandoned because they violated the stateless API constraint.
   The decision was implicit in sprint 1 — no formal decision record created.
   Evidence: commit note + constraints doc + superseded semantic fact."

Reasoning chain: 3 steps, 3 sources, 1 inferred connection (no explicit record existed)
```

---

## How Crow Interacts With Every Other Layer

```
Eagle:  → "intent=why-question, entity=auth, time=sprint-1 era"
Ant:    → "no trail for implicit-decision questions"
Bee:    → 6 workers, partial results: decisions/auth, semantic/auth, episodic/sprint-1
          BUT: no direct "why we stopped sessions" found
Crow:   → takes bee's partial results as starting evidence
          → identifies gap: the abandonment rationale
          → invents step-by-step queries to bridge the gap
          → returns synthesised answer + reasoning chain
Ant:    → new trail reinforced: "implicit-decision questions → [superseded-facts, near-date-events, constraints]"
          (crow's successful path becomes an ant trail for next time)
```

**The crow feeds the ant.** Every successful crow inference creates a candidate trail —
if this reasoning path worked once, it's worth remembering as a pattern.
The crow invents new paths. The ant formalises them.

---

## Relation to Episodic Memory (Crow's Own Memory)

The crow's episodic memory in biology: it remembers individual humans who were hostile.
For the crow inference layer:

- Each successful inference is logged as an episodic event
- The reasoning chain is preserved (not just the answer)
- Next time a similar gap appears, the crow checks: "have I reasoned through this gap type before?"
- If yes: reuse the reasoning pattern (faster than re-inventing)
- If no: invent from scratch and log the new pattern

The crow builds its own case law — "this type of question with this type of gap was solved this way."

---

## Implementation Estimate

| Component | Effort |
|---|---|
| Gap identification (what's missing from partial results) | 2h |
| Evidence-type reasoning (what could fill the gap) | 2h |
| Query improvisation (generate candidate queries) | 3h |
| Sequential execution with mid-course adjustment | 3h |
| Multi-source synthesis with reasoning chain | 3h |
| Theory of mind (user knowledge vs system knowledge gap) | 2h |
| Dead-ends registry (failed query logging) | 1h |
| Crow → Ant feedback (successful paths become trails) | 2h |
| CLI: `scope mem search --crow` with reasoning chain display | 2h |
| Tests | 4h |
| **Total** | **~24h** |

---

## Extended Philosophy — Four Deeper Crow Dimensions

### 1. You Cannot Catch the Crow — Adversarial Awareness

Crows recognise and avoid traps — even novel ones they've never seen.
They watch humans set a trap, then refuse to approach it.
They communicate the trap's location to other crows.
They are genuinely difficult to deceive.

This maps to a **first-response skepticism** in the inference layer:

```python
def validate_answer(answer: InferenceResult) -> bool:
    """The crow doesn't trust the first thing it finds."""
    red_flags = [
        answer.confidence > 0.95 and answer.sources_count == 1,  # too clean from one source
        answer.reasoning_chain_length == 0,                        # no reasoning = probably wrong
        answer.age_days > 180 and answer.never_reinforced,        # old + unconfirmed
        answer.contradicts_known_constraint,                        # violates what we know
    ]
    if any(red_flags):
        # Don't return this answer. Crow sees the trap. Investigate further.
        return False
    return True
```

The crow is suspicious of easy, clean, single-source answers to complex questions.
**The first answer is always a candidate, never a conclusion.**

This is especially important when the elephant layer has a confident fact that
contradicts evidence in the episodic layer. The crow doesn't trust the confident
fact just because it has high confidence — it investigates the contradiction.

---

### 2. Surveillance — Proactive Monitoring, Not Just Reactive Retrieval

Crows perch high and watch continuously. They communicate to household members
about approaching strangers *before* the stranger arrives.
The crow doesn't wait to be asked "is anyone coming?" — it signals proactively.

This is the dimension that separates crow from every other layer:
**every other layer is reactive (responds to queries). The crow also runs proactively.**

```
REACTIVE mode (all layers): user asks → system answers
PROACTIVE mode (crow only):  system watches → crow signals → user informed without asking
```

For AI memory systems, the crow's surveillance role:

```python
class CrowSurveillance:
    """Runs as a background watcher. Signals anomalies before they're queried."""

    def watch(self, memory_stream: EventStream):
        for event in memory_stream:
            signals = []

            # New entity never seen before
            if event.entity not in self.known_entities:
                signals.append(Alert("new-entity", event.entity, "first appearance"))

            # Confidence on a key fact suddenly dropped
            if event.type == "confidence_change" and event.delta < -0.2:
                signals.append(Alert("fact-destabilised", event.fact_id, event.delta))

            # Two agents wrote conflicting values to same fact
            if event.type == "write" and self.conflicts_with_existing(event):
                signals.append(Alert("conflict-detected", event.fact_id, "immediate"))

            # A semantic fact that many things depend on was just superseded
            if event.type == "supersession" and self.downstream_count(event) > 3:
                signals.append(Alert("high-impact-change", event.fact_id, "review needed"))

            for signal in signals:
                self.notify(signal)  # proactive — no query needed
```

Applied to scope-intel: the crow watches `.scope-intelligence/` for changes
and alerts Claude at the start of a session:
*"Since last session: 2 facts changed confidence, 1 new conflict detected, 1 key semantic fact was superseded. Review before proceeding."*

The user didn't ask. The crow told them anyway.

---

### 3. Karma Persistence — The Pending Inference Registry

This is the most philosophically unique crow dimension.

In Indian philosophy, karma follows a person and doesn't exhaust until resolved.
The crow in folklore is associated with this — it stays with you, circles back,
appears again until the debt is paid or the question is answered.

For AI inference: **unresolved questions do not close. They stay in orbit.**

```json
// pending_inferences.jsonl — the karma registry
{"id": "pi_001", "question": "why was session-based auth abandoned?", "status": "partial", "evidence_found": ["semantic/jwt-switch", "episodic/sprint-1"], "missing": "explicit rationale — no decision record found", "created": "2025-01-15", "last_attempted": "2025-03-10", "attempt_count": 3, "trigger_on": ["auth", "sessions", "decision"]}
{"id": "pi_002", "question": "what caused the memory leak in v1.2?", "status": "open", "evidence_found": [], "missing": "no memory about v1.2 incident in any layer", "created": "2025-02-20", "last_attempted": "2025-02-20", "attempt_count": 1, "trigger_on": ["memory-leak", "v1.2", "performance"]}
```

The crow revisits pending inferences when new information arrives:

```python
def on_new_information(event: MemoryEvent):
    """When new data enters any layer, check if it resolves a pending inference."""
    pending = load_pending_inferences()
    for pi in pending:
        if any(trigger in event.tags for trigger in pi["trigger_on"]):
            # New information is relevant — crow attempts inference again
            result = crow_agent.infer(pi["question"], context=event)
            if result.completeness > 0.8:
                # Gap is now closed
                pi["status"] = "resolved"
                pi["resolved_by"] = event.id
                promote_to_semantic(result)  # resolved inference becomes a fact
            else:
                # Still partial — update evidence, stay pending
                pi["evidence_found"].append(result.new_evidence)
                pi["last_attempted"] = now()
```

**The karma exhausts when the gap is filled. Not before.**

This solves a real problem in AI memory: questions that couldn't be answered
at time T (because evidence didn't exist) get auto-resolved at time T+N
when the evidence finally appears. The system learns retroactively.

Example:
- Jan 10: crow tries to answer "why was auth changed?" — no decision record exists → pending
- Mar 15: new doc ingested that mentions "we moved to JWT for stateless API compliance"
- Mar 15: crow surveillance detects new event with tag "auth" + "JWT" + "decision"
- Mar 15: crow re-attempts pi_001 → answer found → resolved → promoted to semantic fact
- User on Apr 1 asks "why was auth changed?" → answered immediately from semantic layer

The pending inference created in January is resolved in March without any user action.
**The crow came back. The karma exhausted.**

---

### 4. No Own Nest — The Crow Owns Nothing

*Note: biologically, crows DO build their own nests. The brood parasitism
(laying eggs in other birds' nests) is the cuckoo, not the crow.
However, the philosophical principle from the folklore is captured here regardless.*

The crow produces outputs but never stores them itself:
- Successful inference → promoted to **elephant semantic layer** (becomes a stable fact)
- Reasoning chain → stored in **episodic layer** (becomes an event record)
- Successful retrieval path → donated to **ant trail** (becomes a reinforced route)
- Dead end encountered → logged to **ant dead-ends registry** (negative trail)
- Proactive alert → written to **conflict log** (owned by the event stream)
- Pending inference → lives in **pending_inferences.jsonl** (shared registry)

**The crow has no private storage.** Everything it produces belongs to another layer.

Why this matters architecturally: the crow is **stateless between invocations**.
It doesn't maintain its own memory. It reads from all layers, reasons, and writes
back to the appropriate layer. The next crow invocation starts fresh — with nothing
of its own — but finds a richer world because of what previous crow runs deposited elsewhere.

This is exactly like the cuckoo egg: the crow's intelligence hatches in other layers
and is raised by them. The crow never comes back to claim it.

```
Crow runs → produces insight
         → insight deposited in elephant/semantic
         → crow is done, holds nothing
         → next crow session reads from elephant (finds its own prior work)
         → but doesn't know it — just finds a richer world to reason in
```

---

## Decision Gate

Use the crow layer if:
- [ ] "Why" questions are common (rationale often not explicitly stored)
- [ ] Knowledge is spread across heterogeneous sources (docs + code + logs + git)
- [ ] Users ask for analysis, not just facts ("what caused X?")
- [ ] The system grows complex enough that no single doc has complete answers
- [ ] You want the system to get smarter at inference over time (dead-ends + new trails)

Skip if:
- [ ] All questions are simple fact lookups ("what does auth use?")
- [ ] Knowledge is fully explicit and structured
- [ ] System is early-stage and memory is small
