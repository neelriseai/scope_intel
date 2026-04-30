---
name: horse-vigilance
description: >
  The Horse Layer — pre-cognitive threat detection, panoramic ambient scanning,
  nervous system synchronization, and contextual safety mapping. The only animal
  in this framework shaped entirely by being prey. Reacts before reasoning.
  Scans everything simultaneously at low resolution. Nervous system couples to
  surrounding state. Safety memory is contextual, not categorical.
  Philosophy: the prey animal's intelligence — not optimised for hunting,
  but for never being caught off guard.
status: candidate
relates_to: nature-memory-framework, dog-companion, heron-stillness, eagle-retrieval, scope-intelligence-toolkit
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
