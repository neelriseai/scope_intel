---
name: heron-stillness
description: >
  The Heron Layer — threshold-triggered precision action after patient observation.
  Do nothing until necessary. Observe at low cost continuously. Filter noise without
  acting. Strike instantly and completely when the threshold is met.
  Philosophy: stillness IS the strategy. Observation and action are completely
  separated. Inaction is the default. Action is the exception — but total when it fires.
status: candidate
relates_to: nature-memory-framework, eagle-retrieval, crow-inference, scope-intelligence-toolkit
---

## The Philosophy — Stillness IS the Strategy

### The Heron vs The Eagle — A Critical Distinction

Both are predators. Both are precise. Completely different operating contexts.

**Eagle:** The target is **visible**. The rabbit is running in the field. The eagle locks its forward fovea on it — a target it can already see — and commits to the dive. The eagle's intelligence is in *choosing which visible thing to focus on* and *when to commit*.

**Heron:** The target is **not visible yet**. The fish is under the surface. The heron cannot see it directly. It watches for indirect signs — shadows, subtle movements, the slight distortion of light through water. It waits until the fish *reveals itself*, then strikes in the moment of revelation. The heron's intelligence is in *watching for what hasn't surfaced yet* and *recognising the exact moment it does*.

```
Eagle:  visible signal → choose → lock on → act
Heron:  nothing visible → sustained watch → surface event → instant strike
```

For AI systems:
- Eagle = filtering from known/visible information (which zones to search, which signals to attend to)
- Heron = watching for information that hasn't arrived yet, triggering the moment it crosses threshold

**The heron does not choose among visible options. It waits for something to become visible.**

---

The heron stands motionless at the water's edge for hours.
Most observers think it is resting. It is not.

It is maintaining **total focused attention with zero action** — watching for the moment the
target reveals itself. Not scanning. Not filtering what's already there. Waiting for what isn't there yet.

**The heron has made a radical design decision: it has fully separated observation from action.**

Observation: continuous, total focus, never stops.
Action: rare, instant when threshold crossed, complete.

Most AI systems do the opposite — they treat every observation as a trigger for action.
Every event gets a response. Every query gets processed. Every signal gets acted on.
This is exactly wrong. The heron has known this for 60 million years.

**Inaction is the default. Action is the exception.**
But when action comes — it is 60ms, lethal, and never misses.

---

## What the Heron Actually Does — The Biology

### 1. The S-Curved Neck — Stored Potential Energy
The heron's neck is held in an S-curve while waiting. This is not rest — it is a compressed spring.
When the strike fires, the neck uncoils using stored elastic energy, not active muscle contraction.
Speed: ~60ms. Distance: up to 60cm. Accuracy: compensates for water refraction.

**The power comes from accumulated stillness, not continuous effort.**
The longer the heron waits in the coiled position, the more loaded the spring.
Inaction is preparation.

### 2. Refraction Correction — Correcting for Systematic Distortion
Fish appear to be where they are not. Water refracts light.
A fish 30cm deep appears 10cm shallower than it actually is.
The heron does NOT strike where the fish appears. It strikes where the fish is,
correcting for the known refraction angle.

**The heron accounts for systematic bias before acting. It doesn't trust the raw signal.**

### 3. The Noise Filter — Learned Over Years
Young herons strike at shadows and ripples. Old herons rarely miss.
The filter is not innate — it is learned through experience.
What's noise: wind ripples, light reflections, current patterns, debris.
What's signal: the subtle shadow of a fish moving just below the surface.

**The ability to do nothing improves with experience.**
The more signals the heron has seen and ignored, the better its filter becomes.

### 4. The Binary Execution Mode
There is no "medium speed" strike. The heron is either:
- **Still** (observation mode, near-zero energy)
- **Striking** (full execution, maximum speed)

No half-measures. No "tentative action." No medium-confidence responses.
The threshold is calibrated. Once crossed — full commitment.

### 5. The Calibrated Threshold — Not 100%, But Right
The heron doesn't wait until certainty. It waits until threshold.
Too low a threshold: strikes at shadows, wastes energy, catches nothing.
Too high a threshold: waits too long, the fish moves, opportunity missed.
The optimal threshold is learned, not fixed. It adapts to conditions.

---

## What Modern AI Gets Badly Wrong (The Heron's Critique)

```
Current AI system design:
  Event arrives → process → respond
  Every event treated equally
  No observation mode vs action mode distinction
  Low confidence response = same as high confidence response
  "I'll try to help" even when the signal is noise

Result:
  Expensive (processes everything)
  Noisy (responds to everything)
  Imprecise (no confidence gating)
  Exhausting (no rest, no accumulation)
  Hallucinates (responds when it shouldn't)
```

```
Heron design:
  Event arrives → observe → filter → threshold check → act OR stay still
  Most events: stay still
  Rare events: full strike
  Confidence below threshold: do NOT respond
  Confidence above threshold: respond completely

Result:
  Cheap (observes freely, acts rarely)
  Signal-precise (filters noise automatically)
  Reliable (never acts below threshold)
  Builds potential (stillness accumulates readiness)
  Doesn't hallucinate (threshold prevents premature response)
```

---

## The Four Heron Capabilities

### 1. Passive Monitoring — The Low-Cost Observation Mode

```python
class HeronObserver:
    """Runs continuously. Costs almost nothing. Triggers only when threshold met."""

    OBSERVATION_COST = 0.001   # near-zero: just reads signals, no LLM calls
    ACTION_COST = 1.0          # full: LLM reasoning, retrieval, response

    def observe(self, signal_stream: Stream):
        for signal in signal_stream:
            score = self._score_signal(signal)   # cheap: rule-based scoring
            if score >= self.threshold:
                self._strike(signal, score)       # rare: full execution
            else:
                self._log_observation(signal)     # always: lightweight record
                # do nothing else

    def _score_signal(self, signal) -> float:
        return weighted_sum([
            self._relevance(signal)     * 0.4,
            self._confidence(signal)    * 0.3,
            self._novelty(signal)       * 0.2,
            self._urgency(signal)       * 0.1,
        ])
```

The observer runs in background. It never calls an LLM. It scores every signal cheaply.
It does nothing until the score crosses the threshold. Then: full strike.

### 2. Noise Filtering — The Learned Filter

What counts as noise in an AI memory system:
```
NOISE (heron stays still):
  - Repeated identical queries (already answered)
  - Low-specificity queries ("tell me about auth" with no context)
  - Queries below minimum confidence threshold
  - Signals that match known false-positive patterns
  - Background system events with no user-facing impact

SIGNAL (heron may strike):
  - New entity never seen before (high novelty)
  - Confidence on key fact drops suddenly (anomaly)
  - Query with high specificity + clear intent
  - Conflict detected between high-authority sources
  - User provides enough context to cross the threshold
```

The filter improves over time (like the heron):
```python
def update_filter(signal: Signal, outcome: Outcome):
    """The heron learns what to ignore from experience."""
    if outcome == Outcome.MISS:          # struck, caught nothing
        self.noise_patterns.add(signal.pattern)  # add to noise list
        self.threshold *= 1.05           # raise threshold slightly
    elif outcome == Outcome.SUCCESS:     # struck, caught something
        self.threshold *= 0.98           # lower threshold slightly (this signal type works)
```

### 3. The Threshold Gate — Confidence-Gated Action

This is the core heron mechanism. Nothing passes through unless confidence is sufficient.

```python
class HeronGate:
    """Nothing passes unless threshold met. No exceptions."""

    def __init__(self, base_threshold: float = 0.65):
        self.threshold = base_threshold

    def should_act(self, query: Query, context: dict) -> GateDecision:
        confidence = self._assess_confidence(query, context)

        if confidence < self.threshold:
            return GateDecision(
                act=False,
                reason=f"Signal below threshold ({confidence:.2f} < {self.threshold:.2f})",
                suggestion="Need more context: " + self._identify_missing(query, context)
            )

        return GateDecision(act=True, confidence=confidence)

    def _assess_confidence(self, query: Query, context: dict) -> float:
        return weighted_sum([
            _query_specificity(query)          * 0.3,
            _entity_clarity(query)             * 0.25,
            _intent_clarity(query)             * 0.25,
            _context_sufficiency(context)      * 0.2,
        ])
```

Below threshold: heron stays still. Returns: "I need more signal before acting."
Above threshold: heron strikes. Returns: full retrieval + reasoning + response.

### 4. Refraction Correction — Correcting for Systematic Bias

The fish is not where it appears. The heron corrects for refraction before striking.

For AI systems, the equivalent biases that distort signals:

```
RECENCY BIAS:    recent events seem more important than they are
                 → correct: weight by long-term trend, not just latest event

FREQUENCY BIAS:  frequently-mentioned things seem more true
                 → correct: authority of source, not count of mentions

SYCOPHANCY:      LLM tends to agree with premises in the question
                 → correct: rephrase query to neutral before sending to LLM

CONFIDENCE BIAS: LLM outputs sound confident even when uncertain
                 → correct: require explicit uncertainty quantification

AVAILABILITY:    facts that are easy to retrieve seem more relevant
                 → correct: weight by authority, not retrieval speed
```

```python
def correct_for_refraction(signal: Signal) -> Signal:
    """Apply known bias corrections before acting on signal."""
    signal.score *= recency_correction(signal)
    signal.score *= frequency_correction(signal)
    signal.authority = authority_correction(signal.source)
    signal.confidence = calibrate_confidence(signal.confidence, signal.source_type)
    return signal
```

The heron doesn't trust the raw signal. It corrects for what it knows distorts the view.

---

## Burst Execution — Total When It Fires

The strike is 60ms. Not tentative. Not exploratory. Total.

When the heron threshold is crossed, the response is:
1. Full retrieval (eagle + ant + bee in sequence)
2. Full inference if needed (crow)
3. Full purity pass (swan)
4. Complete response delivered

No half-response. No "let me check a few things first."
The threshold guards the action. Once past the threshold — complete commitment.

```
Below threshold: "I need more context before I can answer this reliably."
Above threshold: [full pipeline executes, complete answer returned]
```

No in-between state. Binary.

---

## Application to Scope Intelligence Toolkit

### Preventing Over-Response (Hallucination Guard)

```bash
scope mem search "auth"
```

Without heron gate:
→ Pipeline runs immediately
→ Returns 10 results, all loosely related to "auth"
→ Low signal query gets high-effort response
→ Noise returned as signal

With heron gate:
→ Gate scores query: specificity=0.2, entity_clarity=0.3, intent=0.1 → total=0.2
→ Below threshold (0.65)
→ "Signal below threshold. Specify: which aspect of auth? (module, config, failure, design)"
→ User refines: "scope mem search 'why did auth module switch from sessions to JWT'"
→ Gate scores: specificity=0.9, entity=0.8, intent=0.85 → total=0.85
→ Above threshold → full pipeline fires → precise answer returned

The heron saved: one full pipeline execution. More importantly: didn't return noise.

### Event-Driven Background Processing

```python
# Current (polling — wrong):
while True:
    check_for_new_commits()
    sleep(60)  # wasteful

# Heron (event-driven — right):
git_hook.on_commit(
    lambda commit: heron.observe(Signal(
        type="git-commit",
        content=commit,
        score=score_commit(commit)  # fast, cheap
    ))
)
# → heron observes commit silently
# → if score >= threshold (meaningful commit): auto_capture fires
# → if score < threshold (minor commit): logged but no action
```

### Avoiding Premature Doc Ingest Writes

During `scope doc ingest`, don't write output files until the classification pass has enough confidence:

```python
def heron_gate_section(section: DocSection, classification: dict) -> bool:
    confidence = (
        classification["confidence"]      * 0.4
        + classification["route_clarity"] * 0.3
        + classification["fact_count"]    * 0.2
        + classification["completeness"]  * 0.1
    )
    if confidence < 0.6:
        # Heron stays still — don't write, flag for review
        flag_for_review(section, confidence, "classification unclear")
        return False
    return True  # threshold met — write
```

Prevents the problem of low-confidence extractions being written as facts.

---

## Heron vs Eagle — The Temporal vs Spatial Filter

Both filter. Both reduce unnecessary work. Completely different dimensions:

| | Eagle | Heron |
|---|---|---|
| **Filters** | WHERE to look (spatial) | WHEN to act (temporal) |
| **Question** | "Which memory zones are relevant?" | "Is now the right moment to act?" |
| **Mechanism** | Intent → zone selection → suppression | Signal scoring → threshold → gate |
| **Cost** | Runs at query start | Runs continuously (very cheap) |
| **Output** | Reduced search space | Act or stay still |

Eagle = spatial filter (narrows the where)
Heron = temporal filter (guards the when)

You need both. Eagle without heron: searches the right place at the wrong time.
Heron without eagle: waits for the right time then searches everywhere.

---

## Heron vs Crow — Observation vs Investigation

| | Crow | Heron |
|---|---|---|
| **Mode** | Active investigation (expensive) | Passive observation (cheap) |
| **When** | After retrieval fails | Continuously, before retrieval |
| **Action** | Infer, synthesise, construct | Observe, filter, gate |
| **Default** | Act (it was called because something failed) | Stay still (action is the exception) |

Crow: "I was called because the answer wasn't there. I'll go find it."
Heron: "I'm always watching. I'll tell you when something is worth acting on."

---

## Implementation Estimate

| Component | Effort |
|---|---|
| Signal scorer (fast, rule-based, no LLM) | 2h |
| Threshold gate (confidence assessment) | 2h |
| Filter learning (noise pattern accumulation) | 2h |
| Refraction corrections (bias adjusters) | 2h |
| Event-driven observer (replaces polling loops) | 3h |
| Doc ingest heron gate (pre-write confidence check) | 1h |
| Query gate (pre-retrieval confidence check) | 2h |
| Threshold calibration (learn from outcomes) | 2h |
| CLI: `scope heron status` (show threshold, recent signals) | 1h |
| Tests | 3h |
| **Total** | **~20h** |
