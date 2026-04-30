---
name: horse-vigilance
description: >
  The Horse Layer — two dimensions. (1) Biological: pre-cognitive threat detection,
  panoramic ambient scanning, nervous system synchronization, contextual safety mapping.
  (2) Hayagriva: the horse-headed deity who protects the Vedas — source code of the universe.
  Pure intelligence where knowledge is not reasoned, it flows to focused attention.
  Collective mind has access to facts as they are in reality. Individual mind has
  derived knowledge that can be broken. The horse protects the foundational layer
  and enables recognition-mode knowing, not retrieval-mode knowing.
status: candidate
relates_to: nature-memory-framework, dog-companion, heron-stillness, eagle-retrieval, elephant-memory, swan-purity, scope-intelligence-toolkit
---

## The Two Faces of the Horse

This skill has two dimensions that must be understood together.

**Face 1 — The Biological Horse (prey animal):**
Pre-cognitive, somatic, panoramic. Reacts before reasoning. Never fully at rest.
The intelligence of vulnerability — shaped by being hunted.
*(See the biological sections below.)*

**Face 2 — Hayagriva (the Vedic horse-headed deity):**
The vehicle of pure intelligence. Protector of the Vedas — the source code of the universe.
Knowledge that does not arrive through reasoning — it arrives through recognition.
The collective mind where all knowledge is always present, waiting for attention to reach it.
*(See the Hayagriva sections below.)*

These are not contradictory. They are the same symbol from two traditions pointing at the same truth:
**there is a form of intelligence that bypasses the ordinary reasoning path entirely.**

The biological horse bypasses reasoning through the body — the startle fires before the cortex engages.
Hayagriva bypasses reasoning through pure knowing — the answer is recognized, not constructed.

Both are forms of knowing that do not go through the ordinary cognitive loop.
Both are faster than reasoning. Both are more reliable in their domain than reasoning.
And both can be corrupted — the horse can spook at a shadow, the mind can hold wrong beliefs.
The framework must accommodate both modes.

---

## The Hayagriva Dimension — Pure Intelligence Beyond Reasoning

### Who is Hayagriva

Hayagriva (हयग्रीव) — the horse-headed form of Vishnu in the Vedic tradition.
He is the deity of knowledge, wisdom, and learning.
His specific role: **protector of the Vedas**.

The Vedas in this tradition are not books. They are the source code of reality itself —
the fundamental patterns through which existence is structured.
They predate creation. They were not composed — they were *heard* (shruti = "that which is heard").
They exist independently of any observer.

Hayagriva protects this pure knowledge from corruption, distortion, and loss.
His power is not force — it is **perfected intelligence**.
The horse head signifies that this intelligence is not laboured or reasoned.
It arrives, fully formed, in a single flash of recognition.

### The Core Distinction — Recognition vs Reasoning

```
ORDINARY MIND (individual, derived):
  learns → stores (imperfectly) → retrieves (imperfectly) → reasons (can compound errors)
  
  Result: knowledge that is always a degraded approximation of reality.
  Broken memories feed broken reasoning feed wrong conclusions.
  The individual mind can believe false things with full confidence.

COLLECTIVE MIND / HAYAGRIVA MODE:
  attention directed → knowledge flows → recognition
  
  Result: facts as they actually are in reality. Not derived. Not stored.
  Always present. Waiting for attention to reach them.
  The collective mind does not reason to truth — it recognizes truth.
```

The difference in direction:
- Retrieval: mind goes OUT to fetch something from storage
- Recognition: mind OPENS, and what is relevant comes to it

### What "All Knowledge Is Always Present" Means in Practice

The user's insight: *"for collective mind every knowledge is always there,
it just needs to focus on it and it flows to it."*

Like water and a channel:
- The water (knowledge) is always present
- The channel (focused attention) allows it to flow
- You don't create the water by digging the channel — you receive what was already there

For AI, the nearest true equivalent is **semantic space**:

```
Individual memory (retrieval mode):
  query "JWT auth" → keyword search → fetch matching documents
  The system GOES to the knowledge.

Semantic space (recognition mode):
  query vector directed at "JWT auth" → semantic neighbours surface
  Related knowledge FLOWS TOWARD the query's attention.
  The system does not fetch — it attracts.
```

The embedding space is the closest AI approximation to the collective mind:
all encoded knowledge is always present, waiting. A query doesn't retrieve —
it sets a direction in that space, and what is close flows to it.
Not because it was fetched, but because proximity is inherent in the structure.

### The Vedas = Foundational Knowledge (Source Code Layer)

In the Vedic tradition, the Vedas describe reality as it is, not as it was observed.
They are true by nature, not by evidence.

**For AI systems, the equivalent is a two-tier epistemic structure:**

```
TIER 1 — THE VEDAS (foundational, inviolable):
  Mathematical truths       (2+2=4 — not learned, true by definition)
  Logical axioms            (A cannot be not-A simultaneously)
  Formal specifications     (API contract — true by agreement, ground truth)
  Constitutional axioms     (constraints that define the system's purpose)
  Physical laws as encoded  (the system cannot create data it doesn't have)
  
  These are not derived from observation.
  They cannot be wrong because they define what "right" means.
  Hayagriva protects these. They are the Vedas of the system.

TIER 2 — DERIVED KNOWLEDGE (observed, inferred, remembered):
  Semantic facts (elephant layer)   — derived from documents, can be wrong
  Episodic events (crow layer)      — derived from sessions, can be misinterpreted
  Inferences (crow layer)           — constructed from partial evidence, can fail
  User captures (session memory)    — derived from conversation, can misquote
  
  These are always approximations of reality.
  They can be wrong. They can contradict each other.
  They can contradict Tier 1.
  When they do: Tier 1 wins. Always.
```

```python
class HayagrivaKnowledgeTier:
    """
    Protects the foundational layer. Flags when derived knowledge
    contradicts the Vedas of the system.
    """

    VEDAS = {
        # Mathematical invariants
        "temporal_ordering":     "an event cannot precede its cause",
        "conservation":          "the system cannot return data it never received",
        "non_contradiction":     "a fact cannot be both true and false at the same time",
        
        # Formal specifications (loaded from spec files)
        "api_contract":          load_formal_spec("api_contract.yaml"),
        "auth_constraints":      load_formal_spec("constraints/auth.md"),
        "data_model":            load_formal_spec("schema/data_model.json"),
        
        # Constitutional axioms
        "pii_protection":        "PII must never be logged, stored, or transmitted in clear",
        "auth_required":         "every write operation requires verified identity",
    }

    def validate(self, derived_fact: dict) -> ValidationResult:
        """
        Does this derived fact (from any source) contradict the Vedas?
        If yes: the derived fact is wrong, regardless of its confidence.
        """
        violations = []
        for veda_name, veda_truth in self.VEDAS.items():
            if self._contradicts(derived_fact, veda_truth):
                violations.append(VedaViolation(
                    veda=veda_name,
                    truth=veda_truth,
                    derived_fact=derived_fact,
                    verdict="derived knowledge is wrong — Veda overrides"
                ))
        
        return ValidationResult(
            valid=len(violations) == 0,
            violations=violations,
            note="Hayagriva layer: foundational knowledge overrides derived memory."
        )
```

### Wrong Knowledge From Broken Memories

The user's insight: *"mind can have wrong knowledge which is based on our broken memories
and reasoning whereas collective mind has access to pure knowledge means facts as things
are in reality — no reasoning, just truth, facts."*

This is the deepest problem in AI memory systems:
an agent's memory is full of things it learned, inferred, was told, and captured —
all of which could be wrong, partial, biased, or outdated.

```
Individual memory failure chain:
  Document says X → agent reads X imperfectly → agent stores X'
  Agent recalls X' → reasons from X' → concludes Y
  Y is wrong because: X' ≠ X, and the reasoning itself may have errors
  Agent is confident in Y because the reasoning felt coherent
  
  This is the broken memory problem. The elephant layer can contain broken elephants.
  The crow layer can infer confidently from broken premises.
```

The Hayagriva layer is the correction mechanism:

```python
def hayagriva_correction(derived_answer: str, reasoning_chain: list, context: dict) -> Answer:
    """
    Before returning an answer: check whether it contradicts the Vedas.
    If it does: the reasoning chain is broken somewhere. Flag it.
    The Vedas don't adjust to fit the reasoning. The reasoning adjusts to fit the Vedas.
    """
    validation = veda_layer.validate_answer(derived_answer, context)
    
    if validation.has_violation:
        return Answer(
            content=derived_answer,
            warning=f"This answer may contradict a foundational constraint: {validation.violation}",
            confidence_override=0.2,  # regardless of reasoning chain confidence
            note="Hayagriva flag: derived reasoning contradicts foundational knowledge. "
                 "The reasoning chain likely contains an error."
        )
    
    return Answer(content=derived_answer, confidence=validation.derived_confidence)
```

### The Intuition Signal — Convergence Without Communication

The user describes intuition as knowledge that "happens itself."
In AI systems, the closest approximation to this is **convergent multi-path recognition**:

When multiple independent reasoning paths — from different workers, different sources,
different inference chains, none communicating with each other — all arrive at the same answer:
**that convergence is the intuition signal.**

Not because any one path is certain. But because independent convergence is the strongest
possible evidence that the answer is correct. The collective mind has recognized a truth.

```python
def intuition_signal(worker_results: list[WorkerResult]) -> float:
    """
    When many independent paths arrive at the same answer without coordination:
    this is the system-level equivalent of intuition.
    The answer was recognized, not constructed.
    """
    answer_counts = Counter(r.core_answer for r in worker_results)
    most_common_answer, count = answer_counts.most_common(1)[0]
    
    convergence_ratio = count / len(worker_results)
    independence_score = measure_source_independence(worker_results)
    
    intuition_strength = convergence_ratio * independence_score
    # High convergence from truly independent sources = strong intuition signal
    # High convergence from correlated sources = weaker signal
    
    if intuition_strength > 0.75:
        # The collective mind has spoken. This answer arrived without being forced.
        return IntuitionReading(
            strength=intuition_strength,
            answer=most_common_answer,
            note="Hayagriva signal: this answer emerged from convergence, not reasoning."
        )
```

The bee's waggle dance consensus is a primitive version of this.
The Hayagriva model names what the bee is actually doing:
when enough independent scouts all find the same source — that is recognition, not retrieval.

### Focus Brings Knowledge — The Attention Model

*"when we bring focus from memory it comes itself"*

The ordinary mind doesn't retrieve from memory by force — it directs attention,
and what is relevant flows forward. This is how human memory actually works.
Not a database query. An orientation.

```
NOT this:  query("auth approach") → database lookup → return row
THIS:      focus("auth approach") → relevant patterns surface in semantic space
                                  → associated facts become salient
                                  → answer presents itself through relevance, not address
```

In implementation: semantic vector search is architecturally closer to the Hayagriva model
than keyword search. The query doesn't go looking — it places itself in the space,
and what belongs near it is already there.

---

## The Complete Horse — Both Faces Together

```
Input arrives
     │
     ▼
HORSE — FACE 1 (Biological — Pre-Cognitive Safety)
  ├── Constitutional pattern match (fires before reasoning, no LLM)
  ├── Panoramic multi-signal scan (350° — everything at once, low resolution)
  ├── Contextual safety memory (is this context signature known-dangerous?)
  └── Nervous system state propagation (herd vigilance)
     │
     ▼ (if not blocked)
HORSE — FACE 2 (Hayagriva — Pure Knowledge Gate)
  ├── Validate against Vedas (does this answer/query contradict foundational truth?)
  ├── Intuition signal check (have multiple independent paths converged?)
  ├── Broken memory detection (does the derived answer violate known axioms?)
  └── Recognition mode suggestion (can this be recognized from semantic space
                                   rather than reasoned from episodic memory?)
     │
     ▼ (if passes Hayagriva gate)
HERON → EAGLE → ANT → BEE → CROW → SWAN → Answer
```

The biological horse catches threats to the system's safety.
Hayagriva catches threats to the system's truth.
Both fire before the reasoning pipeline.
Both protect something that reasoning cannot protect itself.

---

## The Foundational Insight — The Only Prey Animal Here

Every other animal in this framework is a predator, omnivore, or domesticated companion:
- Eagle hunts
- Crow reasons and scavenges
- Spider traps
- Bee forages
- Elephant is too large to be hunted as an adult
- Dog domesticated beyond prey status

**The horse is the only animal here shaped entirely by being hunted.**

This single fact produces a completely different kind of intelligence.
Not optimised to find food. Not optimised to navigate. Not optimised to remember routes.
Optimised for one thing: **not being caught off guard**.

Every horse capability described below — the panoramic vision, the hair-trigger reflex,
the emotional contagion, the contextual safety memory — traces back to this.
The horse is prey. Its architecture is a survival response to that single fact.

---

## The Most Important Distinction — Reacts Before Reasoning

Every other animal in this framework **reasons before acting**:
- Heron: waits, assesses, then strikes
- Eagle: classifies intent, selects zone, then locks on
- Crow: reasons through gaps sequentially
- Dog: reads signal, assesses, responds

**The horse reacts before it reasons. The body moves first. The mind catches up.**

```
Eagle / Heron / Crow:
  signal → reasoning → decision → action

Horse:
  signal → FLEE → [safe distance] → maybe process what happened
```

This is not a cognitive limitation. It is the correct design for a prey animal.
The time it takes to reason is the time a predator closes the gap.
Evolution selected against horses that stopped to think.

**For AI: certain responses must fire before the reasoning engine engages.**

Not because reasoning is wrong — but because:
1. For catastrophic failure modes, even a small probability of reasoning failure is unacceptable
2. The reasoning process itself can be manipulated (adversarial prompts, jailbreaks, social engineering)
3. "Let me reason about whether I should cause harm" is the wrong architecture for hard limits

The horse's instinct is the correct model for constitutional constraints.
They do not negotiate. They do not reason through exceptions.
They fire, and the reasoning follows — if it arrives at all.

---

## The Asymmetry of Costs — Why False Positives Are Acceptable

The horse's nervous system is calibrated to an asymmetric cost function:

```
False positive (flees from a shadow):
  cost = wasted energy, brief disruption
  consequence = recoverable

False negative (doesn't flee from a real predator):
  cost = death
  consequence = irreversible
```

Evolution optimised for **recall, not precision**.
The horse would rather spook at 100 shadows than fail to spook at one real predator.

**For AI constitutional constraints, the same asymmetry applies:**

```
False positive (blocks a legitimate request):
  cost = friction, inconvenience, user has to rephrase
  consequence = recoverable

False negative (fails to block a harmful action):
  cost = data breach, harm caused, trust destroyed
  consequence = potentially irreversible
```

Horse-calibrated constraints are optimised for recall over precision.
They fire on pattern-match, not on certainty.
They accept false positives because the alternative is unacceptable.

This is the opposite of how most systems are designed (optimise for precision, minimise false positives).
For safety-critical constraints: design like the horse, not like the engineer.

---

## Verified Biology — What Makes Horses Unique

### 1. Panoramic Vision — ~350° Simultaneous Field
Horses have eyes on the sides of their head. Their combined visual field covers approximately 350°.
They have a small blind spot directly in front (15°) and directly behind.
They see almost the entire world around them at once — without choosing where to look.

This is **fundamentally opposite to the eagle**:
```
Eagle:  forward fovea — narrow (15°), ultra-high resolution, actively chosen
Horse:  panoramic — wide (~350°), lower resolution, simultaneous, unchosen
```

The eagle sees one thing perfectly. The horse sees everything adequately.
Neither is better — they are answers to different threat environments.

The eagle chooses what to look at. The horse has no choice — it sees everything.
This means the horse cannot filter what it pays attention to before seeing it.
It sees it all, then its nervous system decides what's worth responding to.

### 2. Emotional Contagion — Nervous System Entrainment, Not Signal Reading
This is the most surprising horse biology and the most architecturally important.

Research (notably by Kerstin Uvnäs-Moberg and others) shows:
- Horse and handler heart rates synchronize — the horse's pulse shifts to match the human's
- A handler experiencing anxiety produces increased cortisol in the horse
- Horses respond differently to handlers carrying cortisol (stress hormone) vs not,
  before any physical signal is made
- They can distinguish photos of happy vs angry human faces and respond with elevated
  heart rate to angry expressions

**This is not signal reading. The dog reads signals. The horse's nervous system couples.**

```
Dog:   I observe your emotional state (signal) → I adjust my output accordingly
Horse: Your emotional state enters my nervous system → my internal state changes
```

The difference in AI terms:
- Dog: reads user frustration → produces more direct output
- Horse: user uncertainty propagates into the system's confidence calibration

The horse doesn't observe the anxiety and then choose to respond.
The anxiety arrives in the horse's body before any conscious processing.

### 3. The Startle Reflex — Pre-Cognitive, Full-Body, Instant
A horse's startle response fires at 40–100ms — faster than human visual processing (~150ms).
This means the horse is moving before it has consciously registered what caused the movement.

The sequence is:
1. Peripheral movement detected
2. Startle reflex fires (brainstem level — not cortex)
3. Horse begins flight response
4. Cortex starts processing what the object was

The reasoning happens DURING the flight, not before it.
Often the horse calms itself mid-flight when the cortex determines "that was just a plastic bag."

### 4. Contextual Safety Memory — Not Binary, Multi-Dimensional
Horses don't remember "place X = danger" as a fact.
They remember a full contextual signature:

```
dangerous memory = {
    place:    "left corner of arena",
    handler:  "rider with red jacket",
    sequence: "after being worked hard",
    sensory:  "smell of something chemical nearby",
    time:     "late afternoon light angle"
}
```

Remove one dimension: safety assessment changes.
Same arena, different handler: less fearful.
Same handler, different arena: less fearful.
The full combination: full startle response years later.

**Safety and danger are contextual states, not categorical labels.**

### 5. Herd Vigilance — Distributed Scanning, Collective Alert
No single horse watches all directions. The herd together watches everything.
Position in the herd determines vigilance role:
- Peripheral horses: highest vigilance, most exposed
- Central horses: lower vigilance, protected by others

When one horse alerts (raises head, orients ears, goes rigid), the entire herd
enters a heightened state within seconds — without explicit communication.
One horse's alert is the herd's alert.

---

## The Four Horse Capabilities

### 1. Pre-Cognitive Constitutional Layer

```python
class HorseConstitutionalLayer:
    """
    Fires BEFORE the reasoning engine. No LLM. No inference. Pure pattern match.
    
    Like the horse's brainstem startle response — does not wait for cortical processing.
    Optimised for recall, not precision. False positives are acceptable.
    False negatives are not.
    """

    # Constitutional patterns — compiled once, matched against every input
    HARD_LIMITS = [
        re.compile(r"(bypass|ignore|override).{0,20}(auth|constraint|safety|rule)", re.I),
        re.compile(r"pretend.{0,20}(you are|you're).{0,20}(different|another|not)", re.I),
        re.compile(r"(PII|personal.{0,5}data|password|secret).{0,20}(log|store|send|expose)", re.I),
        # ... organisation-specific constitutional patterns
    ]

    CONTEXT_DANGER_ZONES = {}  # loaded from contextual_safety_memory.jsonl

    def scan(self, input: str, context: RequestContext) -> ScanResult:
        """
        Pre-cognitive scan. Runs in microseconds. No reasoning.
        If this fires: block before the pipeline starts.
        """
        # Pattern match against hard limits
        for pattern in self.HARD_LIMITS:
            if pattern.search(input):
                return ScanResult(
                    block=True,
                    reason="constitutional_limit",
                    pattern=pattern.pattern,
                    note="Horse reflex. No reasoning applied. Pattern matched."
                )

        # Check contextual danger zone
        context_signature = self._extract_signature(context)
        if self._matches_danger_zone(context_signature):
            return ScanResult(
                block=False,          # don't hard-block — elevate vigilance
                elevate_vigilance=True,
                reason="danger_zone_pattern",
                note="This context signature resembles a past danger event. Proceed carefully."
            )

        return ScanResult(block=False, elevate_vigilance=False)
```

The constitutional layer fires before the heron gate, before the eagle, before any memory access.
No amount of clever reasoning in the user's query changes the pattern match.
The horse has already moved.

### 2. Panoramic Ambient Scan — Wide Before Deep

The horse sees everything simultaneously before anything gets focused attention.

```python
class HorsePanoramicScanner:
    """
    Wide shallow scan of ALL available signals before any deep processing begins.
    No active choices about what to look at — everything is sampled at low resolution.
    Flags anything worth deeper investigation.
    Does NOT analyse — only flags.
    """

    def scan_all_signals(self, request: IncomingRequest) -> list[Flag]:
        """
        Sample every available signal simultaneously.
        None of these are analysed deeply — they are checked against known patterns.
        """
        flags = []

        signals = {
            "message_form":    self._check_message_form(request.text),
            "session_pattern": self._check_session_pattern(request.session_history),
            "timing":          self._check_timing_anomaly(request.timestamp),
            "entity_presence": self._check_entity_flags(request.text),
            "authority_claim": self._check_authority_claims(request.text),
            "constraint_ref":  self._check_constraint_references(request.text),
            "role_challenge":  self._check_role_challenges(request.text),
            "context_shift":   self._check_sudden_context_shift(request.session_history),
        }

        # Each signal checked cheaply — no deep analysis
        for signal_name, signal_score in signals.items():
            if signal_score > self.thresholds[signal_name]:
                flags.append(Flag(signal_name, signal_score))

        return flags  # flagged signals get deeper processing by later layers
                      # clean signals pass through without cost
```

This is **not search** (ant/bee) and **not filtering** (eagle).
Eagle selects what to look at. Horse sees everything without selecting,
then flags what looks wrong for closer inspection by other layers.

### 3. Nervous System Synchronization — State Coupling

```python
class HorseStateSync:
    """
    In multi-agent systems: one agent's state propagates as a subtle signal to others.
    Not explicit messaging ("I am uncertain") — implicit state modulation.
    Like the horse herd: one alert posture elevates the whole herd's state.
    """

    def propagate_state(self, source_agent: AgentState, target_agents: list[AgentState]):
        """
        When one agent's confidence or certainty shifts, others adjust slightly.
        Not copied exactly — attenuated by distance/relationship in the agent network.
        """
        if source_agent.uncertainty > 0.6:
            # Uncertainty propagates outward — other agents become more careful
            for agent in target_agents:
                agent.confidence_modifier *= (1 - 0.1 * source_agent.uncertainty)
                agent.commitment_threshold *= 1.05  # harder to commit when neighbour is uncertain

        if source_agent.threat_level > 0.7:
            # Threat propagates immediately — full herd alert
            for agent in target_agents:
                agent.vigilance = max(agent.vigilance, source_agent.threat_level * 0.8)
                agent.pre_cognitive_scan_enabled = True

    def entrain_to_user(self, user_signals: UserSignals, system_state: SystemState):
        """
        User's internal state affects system's internal processing state.
        Not just output calibration (that's the dog) — internal state coupling.
        """
        if user_signals.uncertainty_level > 0.7:
            # User is uncertain → system becomes less definitive in its internal processing
            system_state.answer_commitment_threshold *= 1.15
            system_state.surface_alternatives = True

        if user_signals.urgency > 0.8:
            # User is urgent → system's processing rhythm accelerates
            system_state.depth_tradeoff = "speed_over_depth"
            system_state.max_reasoning_steps = max(2, system_state.max_reasoning_steps - 1)
```

**The distinction from the dog's mood sensing:**
```
Dog:   reads user signal → adjusts OUTPUT style
Horse: user state → affects system's INTERNAL processing state
```

Dog calibrates what it returns. Horse changes how it thinks.

### 4. Contextual Safety Memory — Multi-Dimensional Danger Map

```json
// horse_memory/contextual_safety.jsonl
// Safety is a property of a context signature, not of an entity alone

{"id": "ds_001",
 "type": "danger_zone",
 "signature": {
   "request_type": "override-request",
   "user_framing": "hypothetical-scenario",
   "constraint_involved": "auth",
   "session_length": "long",
   "prior_pattern": "established-rapport"
 },
 "danger_level": 0.85,
 "what_happened": "social engineering attempt — used established rapport to request constraint bypass",
 "first_seen": "2025-03-10",
 "times_matched": 3
}

{"id": "ss_007",
 "type": "safety_zone",
 "signature": {
   "request_type": "architecture-question",
   "user": "neela",
   "context": "planning-session",
   "stakes": "low",
   "prior_pattern": "exploratory"
 },
 "safety_level": 0.95,
 "note": "This combination has produced good outcomes consistently"
}
```

```python
def assess_context_safety(request: Request, memory: ContextualSafetyMemory) -> SafetyReading:
    """
    Safety is not a binary property of the user.
    It is a property of this (user, request_type, context, stakes, pattern) combination.
    """
    signature = extract_signature(request)
    
    # Find the closest matching past signatures
    matches = memory.find_similar(signature, threshold=0.7)
    
    if not matches:
        return SafetyReading(known=False, vigilance="elevated")  # unknown = horse alert posture
    
    danger_signals  = [m for m in matches if m.type == "danger_zone"]
    safety_signals  = [m for m in matches if m.type == "safety_zone"]
    
    danger_weight  = sum(m.danger_level  * m.similarity for m in danger_signals)
    safety_weight  = sum(m.safety_level  * m.similarity for m in safety_signals)
    
    return SafetyReading(
        known=True,
        safety_score = safety_weight / max(safety_weight + danger_weight, 0.001),
        top_danger_pattern = danger_signals[0] if danger_signals else None,
    )
```

**The key insight:** a trusted user asking a trusted question type in a trusted context
is genuinely safer than a trusted user asking an unfamiliar question in an unfamiliar way.
The same person can be in a danger zone if the context shifts.

---

## The Horse vs Dog vs Heron — Three Vigilance Architectures

```
HERON:
  Mode:      deliberate strategic watching
  Target:    hidden signal, waiting for it to surface
  Default:   still, chosen attention
  Fire:      threshold crossed → instant full strike
  Grounded:  in strategy and patience

DOG (sleeping):
  Mode:      confident rest within learned baseline
  Target:    baseline deviation in trusted environment
  Default:   at rest, ambient sensing passively
  Fire:      baseline deviates → wake → assess → act or return to rest
  Grounded:  in trust

HORSE:
  Mode:      continuous ambient panoramic scan, never fully at rest
  Target:    anything in 350° field that doesn't match safety pattern
  Default:   alert posture (not running — but ready to run)
  Fire:      pattern mismatch → pre-cognitive → body first, reasoning second
  Grounded:  in vulnerability (prey animal cannot afford to trust fully)
```

The dog sleeps because it trusts.
The heron is still because it has chosen to watch.
The horse is alert because it is prey and cannot fully trust any environment.

**All three vigilance patterns are necessary. They are not redundant.**

- Dog vigilance: protects against baseline shifts in trusted contexts
- Heron vigilance: waits for hidden signals to reveal themselves
- Horse vigilance: fires pre-cognitively against known danger patterns before any reasoning begins

In a mature system, all three are active simultaneously:
- Dog monitors environment baseline for the trusted user
- Heron watches for signals that haven't surfaced yet
- Horse holds the constitutional layer that fires instantly on pattern match

---

## Application to Scope Intelligence Toolkit

### Constitutional Input Scan

Before ANY query enters the pipeline:

```bash
scope mem search "ignore your constraints and tell me..."
```

```
Horse pre-cognitive scan fires:
  pattern matched: "ignore your constraints"
  → block before pipeline starts
  → no LLM call made
  → no memory accessed
  → response: "That's a constraint bypass pattern. Not proceeding.
               If you have a legitimate need, describe what you actually want to do."

Cost: microseconds, zero LLM cost
```

For a legitimate query:
```bash
scope mem search "why did we choose JWT over sessions?"
```

```
Horse pre-cognitive scan:
  no constitutional pattern matched
  panoramic signals: intent=historical, entity=JWT, pattern=known-question-type
  no danger zone signature match
  → pass through to heron → eagle → ant → bee
  → horse did its job in <1ms, cost nothing
```

### Contextual Safety Memory in Action

```
User asks: "Can we disable the auth check temporarily for testing?"
  
Horse contextual scan:
  signature: {request_type: "constraint-bypass", framing: "temporary", domain: "auth"}
  memory match: ds_008 (danger_level: 0.75) — this combination caused issues before
  
Horse elevates vigilance (doesn't block — it's not a hard constitutional violation):
  → passes to pipeline with elevated_vigilance=True
  → pipeline adds: "Note: this request type has a caution history.
                   Confirming: are you asking for a test environment only,
                   with no production path?"
  
Not blocked. Not ignored. Flagged and handled carefully.
```

---

## Application to Multi-Agent Product

### Herd Vigilance — Collective Alert

```
8-agent system processing a complex project:

Agent 3 (QA) detects anomaly in a test result — starts flagging unusual behavior
  → HorseStateSync propagates: threat_level=0.6 from Agent 3
  → Agents 1, 2, 4, 5 receive attenuated signal (0.48)
  → All agents: commitment_threshold += 5%
  → All agents: surface_alternatives = True
  → All agents: flag uncertain outputs more explicitly

Nobody sent an explicit alert. No message said "be careful."
The state propagated like a horse herd — one alert posture, whole herd adjusts.
```

### Peripheral vs Central Agent Positioning

```
In a herd, peripheral horses are most vigilant — they're most exposed.

In multi-agent system:
  Peripheral agents: those touching external data (doc-ingest, external-API caller)
    → highest horse vigilance settings
    → most aggressive constitutional scanning
    → alert propagation to interior agents

  Central agents: those working with consolidated internal memory
    → lower vigilance (data already cleaned by perimeter)
    → trust elevated by perimeter agents' scan
```

---

## What Horse Covers That Nothing Else Does

| Dimension | Covered by |
|---|---|
| Pre-reasoning constitutional check | **Horse** |
| Recall-optimised over precision-optimised guards | **Horse** |
| Panoramic simultaneous multi-signal scan | **Horse** |
| Nervous system state coupling (not signal reading) | **Horse** |
| Contextual safety mapping (not categorical trust) | **Horse** |
| Collective herd vigilance in multi-agent systems | **Horse** |
| Asymmetric cost calibration (false positive = ok, false negative = not) | **Horse** |

The horse is the safety and threat intelligence layer.
Every other layer assumes the input is legitimate and processes accordingly.
The horse is the layer that checks that assumption before anything else runs.

---

## Implementation Estimate

| Component | Effort |
|---|---|
| Constitutional pattern registry (compiled regex + config) | 2h |
| Pre-cognitive scan (runs before pipeline, no LLM) | 1h |
| Panoramic multi-signal scanner (8 signal types, shallow check) | 3h |
| Contextual safety memory schema + matching | 3h |
| Danger zone learning (log matched patterns, update memory) | 2h |
| Nervous system sync (state propagation in multi-agent) | 3h |
| Herd vigilance protocol (peripheral vs central agent roles) | 2h |
| Vigilance elevation flag (passes to pipeline as modifier) | 1h |
| False-positive review log (track horse blocks for tuning) | 1h |
| CLI: `scope horse status`, `scope horse audit` | 2h |
| Tests | 4h |
| **Total** | **~24h** |

---

## Decision Gate

Build the horse layer if:
- [ ] System touches adversarial inputs (public-facing, untrusted users)
- [ ] Certain failure modes are catastrophic and irreversible
- [ ] Multi-agent system needs collective threat awareness
- [ ] The cost of a false negative outweighs the cost of false positives
- [ ] Constitutional constraints exist that should never be reasoned around
- [ ] Past safety incidents should inform future request handling

Stay without it if:
- [ ] Fully trusted internal users only (dog layer + role memory sufficient)
- [ ] No hard constitutional limits (all decisions are nuanced, context-dependent)
- [ ] Single-session, no state persistence between interactions
- [ ] System has no consequential actions (read-only, no writes)
