---
name: mouse-explorer
description: >
  The Mouse Layer — rapid sandbox exploration, edge-case discovery, and iterative
  probing through tiny reversible experiments. Discovers new knowledge through
  systematic probing rather than inference from existing data. The crow reasons
  backward from evidence. The mouse probes forward into the unknown.
  Philosophy: cautious incremental probing with retreat capability, systematic
  edge-first coverage, and population-level learning from many simultaneous probes.
status: candidate
relates_to: nature-memory-framework, crow-inference, ant-trails, scope-intelligence-toolkit
---

## The Philosophy — Probe Before You Commit

Every other animal in this framework works with what it already knows:
- Elephant remembers what was established
- Eagle filters what's worth looking at
- Bee searches what exists
- Crow infers from partial evidence
- Swan cleans what was found

**The mouse discovers what nobody knew to look for.**

The mouse doesn't wait for a question. It doesn't search existing memory.
It goes into the dark, pokes something carefully, observes the reaction,
retreats to safety, and probes again — slightly differently.

The mouse is the only layer that **generates new knowledge through direct experiment**
rather than through reasoning, retrieval, or storage.

---

## What Mice Actually Do — The Biology That Matters

### 1. Whisker Array — N Simultaneous Micro-Probes
**The single most important mouse biology fact that nobody talks about.**

A mouse has ~56 whiskers (vibrissae). Each maps to a dedicated barrel column in the brain.
The mouse actively sweeps whiskers forward-backward (whisking) at 5–25Hz.
Simultaneously sampling: surface texture, object distance, air currents, spatial geometry, temperature.

**This is not one probe. It is N simultaneous micro-probes on different dimensions.**

The mouse never tests one thing at a time. It samples the entire boundary at once.

AI translation:
```
NOT this:  probe(input=null) → observe → probe(input=empty_string) → observe → ...
THIS:      probe([null, empty, max_int, negative, unicode, 0, "admin"]) simultaneously
           → observe all responses in one pass
           → flag anything that deviated from expected
```

### 2. Thigmotaxis — Edge-First Systematic Exploration
Mice hug walls. Always. When placed in a new environment, they stay at the perimeter,
mapping all edges before venturing inward. This is not fear — it is **strategy**.
The edges define the space. Map the boundary first. Then the interior becomes navigable.

AI translation: **test boundary values before center values.**

```
Input space: integer 0–1000
Mouse strategy:
  Phase 1: edges  → test 0, 1, -1, 1000, 1001, MAX_INT, MIN_INT
  Phase 2: special → test null, NaN, empty
  Phase 3: middle → test 500, 250, 750
  Phase 4: random → test arbitrary values in remaining space
```

This is why boundary value analysis is the most effective software testing strategy:
it is literally how mice explore. Nature optimised it.

### 3. Risk Assessment Probe Cycle — Approach, Retreat, Approach Again
Mice do not charge into unknown territory. They have a strict cycle:
  1. Extend whiskers forward (probe)
  2. Observe any reaction (freeze + assess)
  3. Retreat to safe position
  4. Integrate observation
  5. Approach again (slightly differently)

**The retreat is not failure. It is the design.**

Every probe must be reversible. The mouse never commits to a path it cannot back out of.

AI translation:
```
Probe rule: every test experiment must be REVERSIBLE
  Test in sandbox/dry-run → observe → rollback if dangerous
  Never probe a live system with an irreversible action
  Never probe with an action that could corrupt the environment being tested

Test state tracking:
  before_state = snapshot()
  run_probe(experiment)
  after_state = snapshot()
  if after_state.is_corrupted():
      rollback(before_state)  # mouse retreats
  else:
      record_observation()    # mouse integrates result
```

### 4. The Freeze Response — Anomaly Detection at Every Probe
When a mouse detects something unexpected, it **freezes instantly**.
It doesn't continue. It doesn't ignore. It stops, assesses, and processes
the anomaly before deciding the next move.

AI translation: the mouse engine treats unexpected responses as primary signals:

```python
def probe(experiment: Experiment) -> Observation:
    expected = experiment.expected_behavior
    actual = execute(experiment)

    if is_unexpected(actual, expected):
        # FREEZE — this is the most valuable signal
        flag_anomaly(Anomaly(
            type=classify_anomaly(actual, expected),
            experiment=experiment,
            actual_response=actual,
            severity=rate_severity(actual)
        ))
        # Do NOT continue on the same path — explore this anomaly
        return Observation(type="anomaly", requires_followup=True)

    return Observation(type="normal", result=actual)
```

Unexpected behavior is not a test failure — it is a **discovery**.
The mouse that found the anomaly has found something no one knew to look for.

### 5. Rapid Breeding — Population-Level Learning
Mouse generations: 3 weeks. The population itself is the learning algorithm.
Many variants live simultaneously. Successful variants propagate.
Unsuccessful variants die. The population converges on solutions through
sheer parallel iteration.

AI translation: **run many probe variants simultaneously, let successful ones generate children:**

```python
def population_probe(seed_experiment: Experiment, population_size: int = 50):
    """Genetic algorithm-style probe population."""
    population = mutate(seed_experiment, n=population_size)
    results = [execute(e) for e in population]  # parallel

    # Interesting = found an anomaly, unexpected behavior, or new path
    interesting = [r for r in results if r.is_interesting]
    boring = [r for r in results if not r.is_interesting]

    # Breed from interesting variants (mutate their parameters)
    next_generation = []
    for result in interesting:
        next_generation.extend(mutate(result.experiment, n=3))

    # Prune boring paths
    return next_generation, interesting  # interesting = discoveries
```

This is genetic fuzzing — the most effective form of automated edge-case discovery.
It finds bugs that no human would think to test for, because it evolves toward
whatever the system finds hardest to handle.

---

## The Maze vs The Wall — Two Operating Modes

### Mode 1: Maze Exploration (Structured Environment)
Known system, unknown coverage. The mouse knows the schema, the API contract,
the input types — but hasn't mapped all the paths through them.

```
Given: OpenAPI spec for auth endpoint
Mouse goal: find all paths through the input space that produce interesting behavior
Strategy: thigmotaxis (edge values first), then center, then random
Output: coverage map + anomaly log
```

### Mode 2: Wall Navigation (Unstructured Territory)
Unknown system, unknown behavior. The mouse has no prior map.
It builds the map as it goes.

```
Given: black-box system (no spec)
Mouse goal: discover what inputs produce what behaviors
Strategy: population probe → observe → classify responses → form hypotheses
Output: inferred behavior map + interesting input catalog
```

---

## The Six Mouse Use Cases

### 1. QA Automation — Systematic Edge-Case Coverage
```
After code change: mouse runs systematic probe against the changed module
  Phase 1: boundary values for all parameters
  Phase 2: null/empty/type-mismatch for all inputs
  Phase 3: concurrent calls (race conditions)
  Phase 4: resource limits (large payload, timeout, OOM)
Output: coverage report + anomalies discovered
Auto-integrates: discovered anomalies → crow pending inferences → tracked to resolution
```

### 2. Software Fuzz Testing — Population-Level Discovery
```
Input: any function signature
Mouse generates: 1000 variant inputs through mutation
Parallel execution: run all 1000 against function
Flag: any input that causes crash, error, hang, or unexpected output
Output: curated anomaly set sorted by severity
```

### 3. A/B Testing — Controlled Variant Probing
```
Question: "Does prompt version A or B produce better results?"
Mouse: run both versions on N=100 identical inputs simultaneously
Compare: output quality metrics (accuracy, confidence, consistency)
Output: statistical significance + recommendation + edge cases where B fails
```

### 4. Vulnerability Scanning — Penetration Probing
```
Mode: adversarial (what should NOT work but might?)
Strategy: probe auth boundaries, injection points, privilege escalation paths
Each probe: minimal footprint, immediate retreat if detected
Output: vulnerability catalog with reproduction steps
Constraint: every probe is sandboxed + reversible — never live system
```

### 5. API Contract Validation — Spec vs Reality
```
Given: API spec (expected behavior)
Mouse: systematically probe all endpoints + edge cases
Compare: actual behavior vs spec
Output: deviation report — where does the implementation differ from spec?
This is particularly valuable after doc ingest: "does the system actually match
what the doc said it would do?"
```

### 6. Configuration Drift Detection
```
After deployment: mouse probes known-good behaviors from pre-deployment baseline
Any deviation: flagged as configuration drift
Output: "these 3 behaviors changed between v1.2 and v1.3 that weren't in the changelog"
```

---

## Application to Scope Intelligence Toolkit

### During Development — Automatic Regression Probe
After `scope doc ingest` or any code change:

```bash
scope mouse probe --changed-since HEAD~1 --mode qa
```

```
Mouse detects changed files: cli.py, doc_ingestor.py
Mouse generates probe set:
  Phase 1: boundary inputs for ingest_document()
            → empty doc, missing doc, doc with no headings, doc with only headers
  Phase 2: edge cases for section routing
            → section with matching multiple patterns, section with no pattern match
  Phase 3: output file existence checks
            → are all expected files generated? are no extra files created?

Runs: 47 probes in parallel (all reversible — dry-run mode)
Results: 44 pass, 3 anomalies
  Anomaly 1: doc with unicode heading causes KeyError in _route_section()
  Anomaly 2: doc with empty body after heading generates zero-byte file
  Anomaly 3: --overwrite=False doesn't prevent index.json update

Output: 3 bugs discovered that tests didn't cover
```

These get written to the crow's pending inference registry — "why does unicode cause KeyError?" becomes a pending crow investigation.

### After Mem Operations — State Integrity Probe
```bash
scope mouse probe --target mempalace --mode integrity
```
```
Mouse probes:
  Are all JSONL entries valid JSON?
  Do all entries have required fields (id, kind, subject)?
  Are there duplicate IDs?
  Are confidence values in valid range [0.0, 1.0]?
  Are there entries with last_reinforced in the future?
Output: integrity report + auto-fix suggestions
```

---

## Mouse Discovers, Others Use

The mouse is the only layer that **generates genuinely new knowledge** — not from reasoning, not from storage, but from direct experiment. Everything it discovers feeds the other layers:

```
Mouse discovers anomaly → Crow investigates (why did this happen?) 
Mouse maps input space → Ant reinforces successful probe paths as trails
Mouse finds edge cases → Elephant stores them as constraints ("never input X")
Mouse detects violations → Spider updates dependency graph (X depends on Y unexpectedly)
Mouse output passes swan → Swan deduplicates before promoting to memory
```

The mouse is the **experimental arm** of the system. All other layers are archival or analytical.
The mouse makes the system learn from reality, not just from documents.

---

## Mouse vs Crow — The Critical Distinction

Both discover things that aren't in memory. But fundamentally different mechanisms:

| | Crow | Mouse |
|---|---|---|
| **Method** | Reason backward from existing evidence | Probe forward into the unknown |
| **Input** | Existing memory (partial results) | Live system (direct experiment) |
| **Output** | Constructed inference from what IS known | Discovered behavior from what was NOT known |
| **Cost** | LLM reasoning (expensive per step) | Code execution (cheap, massively parallel) |
| **When** | After retrieval returns incomplete results | Continuously, in background, or on trigger |
| **Risk** | Low (reads memory, doesn't touch system) | Requires sandboxing (touches the system) |

The crow says: "based on what we know, the answer is probably X."
The mouse says: "I ran 1000 experiments, and here's what the system actually does."

---

## Mouse vs Ant — Discovery vs Reinforcement

| | Ant | Mouse |
|---|---|---|
| **Purpose** | Reinforces known-good paths | Discovers unknown paths |
| **Input** | Successful past sessions | Empty (starts with no knowledge) |
| **Output** | Stronger trails on existing paths | New paths + new anomalies |
| **Learns from** | Success | Both success AND failure |

The mouse CREATES paths that the ant can later reinforce.
The ant makes common paths cheaper. The mouse makes unknown paths visible.

---

## Implementation Estimate

| Component | Effort |
|---|---|
| Whisker array (multi-dimensional parallel probe generator) | 3h |
| Thigmotaxis strategy (boundary-first exploration order) | 2h |
| Retreat mechanism (reversible probe + rollback) | 2h |
| Freeze response (anomaly detection + classification) | 2h |
| Population prober (genetic mutation + parallel execution) | 4h |
| Maze mode (structured: spec → probe set) | 3h |
| Wall mode (unstructured: discover behavior empirically) | 3h |
| Anomaly → Crow pending inference pipeline | 1h |
| CLI: `scope mouse probe` with mode flags | 2h |
| Sandbox enforcement (no live system writes) | 2h |
| Tests | 4h |
| **Total** | **~28h** |
