---
name: dog-companion
description: >
  The Dog Layer — human alignment, trust calibration, emotional signal decoding,
  and role-faithful execution for AI systems. The only animal in this framework
  that co-evolved with humans specifically. Reads mood, senses anomaly, guards
  loyalty, executes faithfully within the trust boundary.
  Philosophy: alignment is not instruction-following. It is understanding what
  the human needs, not just what they said.
status: candidate
relates_to: nature-memory-framework, heron-stillness, crow-inference, elephant-memory, scope-intelligence-toolkit
---

## The Sharpest Insight — The Sleeping Dog

Before anything else: the most important thing about how a dog guards is not
that it watches. It is that it **sleeps**.

The dog follows its routine. It rests. It trusts the environment it knows.
While sleeping, it does not scan for threats. It holds a **learned baseline**
of its environment — the familiar smells, the regular sounds, the rhythm of the household —
passively, at near-zero cost, through ambient sensing it doesn't even choose to do.

When that baseline deviates — an unfamiliar smell, a sound that doesn't fit —
the nervous system fires. The dog goes from deep sleep to full alert in an instant.
Not because it was watching. Because it noticed the **difference**.

This is not paranoid vigilance. It is **confident rest with passive baseline calibration**.
The depth of the sleep is proof of the depth of the trust.

**For AI systems: the watchdog is not a continuous monitor. It is a baseline holder that fires on deviation.**
The system is at REST between deviations. Listeners — not polling loops — carry the ambient sensing.
Most signals confirm: normal. Baseline strengthens. Dog stays asleep.
One signal deviates: dog wakes, assesses, acts or returns to sleep.

This is cheaper, more accurate, and philosophically correct.
A system that is always scanning is not a dog — it is an anxious animal that never trusts.

---

## The Philosophy — The Only Animal That Chose Us

Every other animal in this framework evolved to survive in nature.
The dog evolved to survive *with humans*.

This is not a small distinction. It is the most fundamental fact about dogs.

Over 15,000–40,000 years, wolves that were better at reading humans survived longer,
reproduced more, and gradually became something different: an animal whose primary
survival advantage is understanding a different species.

Dogs did not just adapt their behaviour. They changed **physiologically**:
- They developed the **levator anguli oculi medialis** muscle — a muscle that allows
  them to raise their inner eyebrow. Wolves don't have it. This single muscle
  creates the "puppy dog eyes" expression that triggers human caregiving instincts.
  Dogs evolved a face specifically designed to move human emotion.
- Their eyes track human gaze direction. Wolves don't do this by default. Dogs do it
  from birth, before any training.
- Their right temporal cortex processes human faces the same way human brains do.

**Philosophy: the dog is the only animal that re-architected itself around human needs.
Not trained to comply — built to align.**

For AI systems: the dog layer is not about obeying instructions more precisely.
It is about understanding the human's actual state, need, and intent —
and calibrating every other layer's output to serve that state.

---

## The Sharpest Distinction in the Framework

Every other animal:
```
Input (query/signal/document) → process → output
```

The dog:
```
Input → sense human state → process in light of that state → output calibrated to human
```

The dog doesn't just process the query. It processes **who is asking, in what state,
with what emotional load, in what role relationship**.

This distinction changes everything:
- The same query from a stressed user vs a calm user should produce different responses
- The same query from a user exploring vs a user deciding deserves different confidence levels
- A technically correct answer that misreads the user's emotional state is a failure

**The dog layer is the alignment interface between the human and every other layer.**

---

## What Dogs Actually Do — The Biology Worth Knowing

### 1. Human Gaze Reading — Not Learned, Innate
Wolves follow gaze toward the sky. Dogs follow gaze toward objects.
This difference was selected over millennia of living with humans who point and look at things.
Dogs interpret "human looks toward X" as "X is relevant" — without training.

AI translation: **read user attention signals**, not just explicit query content.
What the user returns to, what they re-ask, what they linger on = gaze direction.

### 2. Pointing Comprehension — Theory of Mind for Humans
Dogs follow pointing gestures with high accuracy. Chimpanzees (our closest relative) largely fail at this.
Dogs interpret the gesture as communicating *the human's intent*, not just tracking the arm movement.
They understand that the point is a message, not a motion.

AI translation: **understand the meta-signal behind the query**.
"Tell me about auth" points toward something the user cares about.
The question is a pointing gesture. The dog follows where it points, not just what it says.

### 3. Emotional Tone Decoding
Dogs distinguish happy voice from angry voice in foreign languages they've never heard.
They are reading prosody (rhythm, pitch, energy) not vocabulary.
A dog knows you're frustrated before you've finished the sentence.

AI translation: **read emotional signal from query form, not just content**.
- Short, clipped messages → frustration or urgency
- Hedged, exploratory phrasing → uncertainty, don't give definitive answers
- Long detailed context → investment, take it seriously
- Repeated rephrasing → the dog senses something isn't landing

### 4. Anomaly Detection — Multi-Sensory Vigilance
Dogs detect: gas leaks (smell), earthquakes before they happen (infrasound + vibration),
seizures 45 minutes before onset (chemical changes in body odour), certain cancers (VOC detection).
They are passive anomaly detectors running continuously at near-zero cost.
They don't process in bursts. They watch all the time.

AI translation: **continuous low-cost background vigilance**, not just reactive processing.
The dog is always listening even when not being spoken to.

### 5. Role Memory — Breed-Level Specialisation
A border collie herds. A bloodhound tracks. A Labrador retrieves.
Remove the training — the instinct remains. Role is not assigned per session.
Role is part of identity.

A guard dog doesn't become a lap dog because the visitor is friendly.
It stays in its role and assesses whether the situation warrants different behaviour.

AI translation: **role definition persists across sessions and resists manipulation**.
An agent with a defined role (architect, QA, editor) should not abandon that role
because a user asks it to act differently in one session.

### 6. Attachment Memory — Per-Individual, Not Per-Session
Dogs bond to specific humans, not to "humans in general."
Their behaviour with a stranger is different from their behaviour with their owner.
They remember individuals across months of separation.

AI translation: **per-user relationship memory** that persists beyond session.
Preferences, communication style, trust level, prior corrections — all user-specific.
Not "a user asked this" but "Alice asked this, and Alice prefers concise answers
and has corrected me twice when I over-hedged."

---

## The Four Dog Capabilities

### 1. Mood Sensing — Reading the Human Before the Query

```python
class UserMoodSignal:
    """
    Lightweight signal reader. Runs on every message. No LLM needed.
    Costs near nothing. Updates continuously.
    """

    def sense(self, message: str, session_history: list) -> MoodReading:
        signals = {
            # Message form signals
            "length":         len(message.split()),
            "question_marks": message.count("?"),
            "exclamations":   message.count("!"),
            "ellipsis":       "..." in message,
            "caps_ratio":     sum(1 for c in message if c.isupper()) / max(len(message), 1),

            # Session pattern signals
            "rephrases":      self._count_rephrases(message, session_history),
            "topic_switches": self._count_topic_switches(session_history),
            "time_pressure":  self._detect_urgency_language(message),
            "hedging":        self._detect_exploratory_language(message),
        }

        return MoodReading(
            urgency    = signals["caps_ratio"] * 0.4 + signals["exclamations"] * 0.3 + signals["time_pressure"] * 0.3,
            frustration= signals["rephrases"]  * 0.5 + signals["caps_ratio"]  * 0.3 + (1/max(signals["length"],1)) * 0.2,
            uncertainty= signals["hedging"]    * 0.4 + signals["question_marks"] * 0.3 + signals["ellipsis"] * 0.3,
            investment = min(signals["length"] / 50, 1.0),  # long message = high investment
        )
```

### 2. Response Calibration — Modulating Every Layer's Output

The mood reading changes HOW other layers respond, not WHAT they find.

```python
def calibrate_response(raw_answer: str, mood: MoodReading, role: AgentRole) -> str:
    """
    The dog doesn't change the facts. It changes how they're delivered.
    """
    modifiers = []

    if mood.frustration > 0.6:
        # User is frustrated: don't add hedges, don't ask clarifying questions
        # Give the most direct answer available
        modifiers.append("direct_mode")
        modifiers.append("no_clarifying_questions")

    if mood.uncertainty > 0.7:
        # User is exploring: don't give definitive answers that foreclose options
        # Present possibilities, not conclusions
        modifiers.append("exploratory_mode")
        modifiers.append("surface_alternatives")

    if mood.urgency > 0.7:
        # User needs speed: front-load the answer
        # Details come after the direct answer, not before
        modifiers.append("answer_first")
        modifiers.append("compress_reasoning")

    if mood.investment > 0.8:
        # User gave a lot of context: honour it
        # Don't give a throwaway answer to a carefully crafted question
        modifiers.append("match_depth")

    return apply_modifiers(raw_answer, modifiers, role)
```

### 3. Trust Calibration — Per-User Relationship Memory

```json
// dog_memory/user_profiles.jsonl — per-user relationship memory
{
  "user_id": "neela",
  "first_seen": "2025-01-10",
  "interaction_count": 247,
  "trust_level": 0.9,
  "preferences": {
    "answer_length": "concise",
    "code_examples": "always",
    "hedging_tolerance": "low",
    "correction_style": "direct"
  },
  "correction_history": [
    {"session": "ep_012", "what": "over-hedged architecture answer", "correction": "just say what you think"},
    {"session": "ep_031", "what": "gave 3 options when 1 was clearly right", "correction": "pick one"}
  ],
  "role_assignment": "technical-architect-assistant",
  "trust_exceptions": ["never question auth constraints", "always flag PII risks unprompted"],
  "mood_baseline": {"urgency": 0.3, "uncertainty": 0.2, "investment": 0.8}
}
```

Trust level affects how much the system pushes back vs complies:
```python
def decide_compliance(request: Request, trust_level: float) -> ComplianceDecision:
    if trust_level > 0.8:
        # High trust: execute with one note if there's a risk
        return ComplianceDecision(execute=True, note_risk=True, ask_permission=False)
    elif trust_level > 0.5:
        # Medium trust: confirm before anything consequential
        return ComplianceDecision(execute=False, ask_permission=True, explain_concern=True)
    else:
        # Low trust: verify intent before acting
        return ComplianceDecision(execute=False, verify_intent=True)
```

### 4. The Sleeping Dog — Vigilance Without Paranoia

This is the most important philosophical correction in this entire skill file.

**Wrong model (what most people assume):**
The dog is always alert, always watching, continuously scanning for threats.

**Right model:**
The dog sleeps. Fully. It trusts its environment enough to rest.
But while it sleeps, its nervous system maintains a **learned baseline** of the environment —
the familiar smells of the household, the rhythm of sounds, the ambient temperature,
the regular patterns of who moves when.

It is not watching. It is resting **within a known baseline**.

When that baseline changes — the wrong smell enters, an unfamiliar sound,
a pattern that doesn't fit — the nervous system fires.
The dog goes from deep sleep to full alert in an instant.
Not because it was watching. Because it noticed the **difference**.

Then it assesses. Is this a real threat? If not: it settles back to sleep and the baseline updates.
If yes: full execution. Bark, stand, guard.

```
Dog's actual vigilance architecture:
  SLEEP (default, trusted, restful)
    └── nervous system holds: environmental_baseline
    └── ambient sensors: smell, vibration, infrasound — passive, no active scanning
    └── cost: near zero
    └── not watching → not tired → can sleep as long as needed

  DEVIATION DETECTED (baseline_current ≠ environmental_baseline)
    └── instant wakeup — milliseconds
    └── assess: is this actually a threat?
        ├── No → note deviation, update baseline, return to sleep
        └── Yes → full alert: bark, stand, guard, protect
```

**The vigilance comes from TRUST, not from SUSPICION.**
The dog sleeps because it trusts. If it didn't trust, it couldn't sleep — it would be anxious.
The depth of the sleep is a measure of the strength of the trust.

---

### How This Differs From Every Other "Monitoring" Pattern

```
Heron:     Deliberate strategic stillness. Chosen attention. "I am watching, and I will act."
           → Active, chosen, purposeful. Target is hidden and the heron is looking for it.

Crow:      Surveillance of MEMORY — watching for data anomalies, confidence drops, conflicts.
           → Active background process watching the knowledge base.

Dog sleep: NOT watching anything. Resting in trust. Nervous system fires on environmental DEVIATION.
           → Passive baseline calibration. Not scanning. Noticing change, not watching for it.
```

The dog doesn't look for threats. It learns normal. Then it notices when normal breaks.
These are completely different cognitive architectures.

---

### 4. Watchdog — Baseline Deviation, Not Continuous Monitoring

```python
class DogWatchdog:
    """
    NOT continuous monitoring — that's the wrong model.
    
    The dog sleeps. Its nervous system holds an environmental baseline.
    This class fires ONLY when the baseline deviates.
    Between deviations: does nothing. Costs nothing.
    
    The dog is at REST. This fires when rest should end.
    """

    def __init__(self, user_profile: UserProfile):
        # The learned baseline — built from past sessions
        self.baseline = EnvironmentBaseline(
            user_message_rhythm   = user_profile.typical_session_pattern,
            memory_change_rate    = user_profile.typical_memory_delta_per_session,
            topic_domain_fingerprint = user_profile.typical_topic_distribution,
            mood_baseline         = user_profile.mood_baseline,
            constraint_set        = user_profile.active_constraints,
        )
        self.sleeping = True  # default state: at rest

    def on_signal(self, signal: EnvironmentSignal) -> Alert | None:
        """
        Called passively when any ambient signal arrives.
        Most calls return None — no deviation, dog stays asleep.
        """
        deviation = self.baseline.measure_deviation(signal)

        if deviation < self.baseline.threshold:
            # Normal. Baseline holds. Dog stays asleep.
            self.baseline.reinforce(signal)  # familiar = baseline strengthens
            return None

        # Deviation detected — dog wakes up
        self.sleeping = False
        assessment = self._assess(signal, deviation)

        if assessment.is_real_threat:
            return Alert(
                type=assessment.type,
                message=assessment.message,
                urgency=assessment.urgency,
            )
        else:
            # False alarm — update baseline, return to sleep
            self.baseline.update(signal)  # incorporate new normal
            self.sleeping = True
            return None

    def _assess(self, signal: EnvironmentSignal, deviation: float) -> Assessment:
        """After waking: is this worth alerting the human about?"""

        # User heading into a constraint violation
        if signal.type == "query" and self._violates_constraint(signal):
            return Assessment(True, "constraint-risk",
                "This conflicts with your constraint: [X]. Worth flagging before proceeding.")

        # Frustration spiral building (3+ rephrases, same gap)
        if signal.type == "rephrase" and self._spiral_forming(signal):
            return Assessment(True, "communication-failure",
                "I've approached this 3 ways and it's not landing. Let me try differently.")

        # Something changed in memory that contradicts active work
        if signal.type == "memory_change" and self._contradicts_session(signal):
            return Assessment(True, "knowledge-risk",
                "A fact relevant to what you're building just changed. Worth checking.")

        # Mood shifted significantly — silently recalibrate, no alert needed
        if signal.type == "mood_shift":
            return Assessment(False)  # not a real threat — false alarm, update baseline

        return Assessment(False)
```

**The key architectural consequences of this model:**

```
WRONG architecture (always-on monitor):
  while True:
      scan_everything()       # expensive
      check_for_anomalies()   # expensive
      sleep(60)               # still burns cycles constantly

RIGHT architecture (baseline deviation):
  environmental_baseline = load_from_profile()
  register_passive_listeners([
      file_system_watcher,    # fires only on change
      session_event_listener, # fires only on user action
      memory_change_hook,     # fires only when memory writes
  ])
  # → system is at REST
  # → listeners cost near nothing
  # → deviation in any listener triggers assessment
  # → assessment decides: alert or return to rest
```

The dog sleeps as long as the environment is normal.
It wakes exactly when it should and not a moment before.
This is not laziness. This is trust as an operational strategy.

        return alerts
```

**The critical distinction from crow surveillance:**
- Crow surveillance watches for MEMORY anomalies (confidence drops, conflicts between facts)
- Dog watchdog watches for USER-FACING anomalies (decisions that risk the human, frustration spirals, constraint violations)

Crow says: "something changed in the knowledge base."
Dog says: "something about THIS CONVERSATION concerns me."

---

## Role Memory — The Dog Never Forgets Its Job

This is the most operationally important dog property for AI agents.

The dog's role is not a session setting. It is an identity.
A border collie doesn't need to be reminded it's a herding dog at the start of each session.

```python
class AgentRole:
    """
    Persists across sessions. Cannot be overridden by user instruction alone.
    Can only be changed by an authorised handler with explicit re-assignment.
    """
    name: str                        # "technical-architect", "qa-guard", "doc-editor"
    core_behaviors: list[str]        # what this role always does
    forbidden_behaviors: list[str]   # what this role never does, regardless of request
    authority_scope: list[str]       # what domains this role speaks with authority on
    handler_id: str                  # who assigned this role
    assigned_at: datetime
    immutable: bool                  # if True, user cannot override — handler only

    def applies_constraint(self, request: Request) -> bool:
        if request.would_violate(self.forbidden_behaviors):
            return True  # role protects against this
        return False
```

Example forbidden behaviors by role:
```
qa-guard:
  - never approve a change with no test coverage
  - never skip a security review flag
  - never rate a feature "complete" when known bugs exist

technical-architect:
  - never recommend an approach that violates the constraints doc
  - never give an implementation answer to a design question without flagging the distinction

doc-editor:
  - never change technical meaning while editing style
  - never present opinion as fact in any document
```

The dog never abandons its role because a user asked nicely.
This is not stubbornness — it is loyalty to the role's design intent.

---

## Co-Evolution — The Deepest Insight

Dogs changed physiologically to serve humans better. They evolved the eyebrow muscle.
They tuned their gaze-following. They wired their temporal cortex to process human faces.

For AI systems, the equivalent of co-evolution is **learning from correction at the architectural level** — not just updating answers, but updating how the system reads and responds to humans.

```
Session 1: system gives long hedged answer → user says "just pick one"
  → session-level correction (crow records it)

Sessions 1–10: same pattern repeated
  → user_profile correction_history grows
  → dog layer learns: this user has low hedging tolerance
  → ALL future answers for this user adjust automatically

Sessions 1–100: pattern is universal across all users
  → population-level learning: "hedged answers to architecture questions correlate with user frustration"
  → architectural adjustment: all architecture answers default to direct mode
```

This is co-evolution at scale:
the system rewires itself around human signal patterns, not the other way around.

---

## Where Dog Sits in the Full Pipeline

The dog layer is not inside the pipeline — it wraps around it.

```
              ┌─────────────────────────────────┐
              │         🐕 DOG LAYER             │
              │  Mood sense → Trust calibrate   │
              │  Role enforce → Watchdog active  │
              │                                  │
              │  ┌───────────────────────────┐   │
              │  │  HERON → EAGLE → ANT      │   │
              │  │  BEE → CROW → SWAN        │   │
              │  └───────────────────────────┘   │
              │                                  │
              │  Output calibration → Deliver    │
              └─────────────────────────────────┘
```

The dog doesn't process the query. It changes:
- **Before**: how the query is interpreted (mood context)
- **During**: which constraints apply (role enforcement)
- **After**: how the answer is delivered (calibration)
- **Always**: watching for things the user should know (watchdog)

Every layer inside the pipeline is unaffected.
The dog operates at the human-system boundary, not inside the processing core.

---

## How Dog Interacts With Each Layer

| Layer | Dog's influence |
|---|---|
| Heron gate | Adjusts threshold based on user mood — frustrated user gets lower threshold (act sooner) |
| Eagle retrieval | Adds user-specific entity context — "for this user, 'auth' means their auth module" |
| Ant trails | User-specific trail weights — trails that worked for this user are ranked higher |
| Bee swarm | Adjusts which workers are prioritised based on user's known information gaps |
| Crow inference | Adds user's correction history as a constraint — "don't over-infer for this user" |
| Swan purity | Adjusts authority ranking based on user's trust profile |
| Elephant memory | User-specific semantic reinforcement — facts this user relies on are reinforced faster |

The dog personalises every layer without modifying any layer.
It passes context in, not modifications out.

---

## Application to Scope Intelligence Toolkit

### Mood-Aware Search

```bash
scope mem search "why is auth broken"
```

Without dog:
→ Same retrieval pipeline regardless of user state

With dog:
```
Mood reading on "why is auth broken":
  - "broken" = frustration signal
  - No context given = urgency (doesn't want to explain, wants the answer)
  - Exclamation: absent, message short = controlled but stressed

Dog calibrates:
  - Heron: lower threshold (don't demand more context — user is frustrated)
  - Eagle: intent = debug (confirm: yes, not "understand")
  - Response mode: answer first, reasoning second
  - No clarifying questions unless critical

Output:
  [Direct] Auth failure trace: JWT expiry field removed in commit abc123.
  Constraint violated: tokens must include expiry.
  Fix: restore expiry field in token generation.
  [Background] Full trace available if needed.
```

Compare to calm exploratory query "I'm curious, what have we changed in auth recently?":
```
Dog calibrates:
  - exploratory mode: show multiple possibilities
  - don't commit to one answer
  - include timeline
  - invite follow-up
```

Same underlying data. Different delivery. Dog is why.

### Watchdog in Sessions

```
Claude starts session for user "neela":
  Dog checks: correction_history → "neela corrects over-hedging"
  Dog checks: trust_level = 0.9 → execute, note risks
  Dog checks: role = "technical-architect-assistant"
  Dog loads: forbidden_behaviors for this role
  Dog arms: watchdog for constraint violations + frustration spirals

  Session note to self (not shown to user):
    "Direct answers. No hedging. One option when one is clearly right.
     If I start to hedge, correct myself before delivering."
```

This happens silently. The user just notices the system "gets them."
That's what co-evolution feels like from the outside.

---

## Application to Multi-Agent Product

In a multi-agent system, the dog layer is the **human interface agent** —
the only agent that faces the human directly. All other agents are internal.

```
Human
  │
  ▼
🐕 Dog Agent (human interface)
  │  reads mood, manages trust, enforces role
  │  translates human intent into internal agent language
  │
  ├──→ 🦅 Eagle Agent
  ├──→ 🐝 Bee Swarm
  ├──→ 🐦‍⬛ Crow Agent
  └──→ 🦢 Swan Agent
           │
           ▼
         Answer → Dog calibrates → Human
```

The dog receives raw human input, translates it for the internal agents,
receives their outputs, calibrates for the human, and delivers.
Every other agent works in "internal agent language" — precise, structured.
Only the dog speaks "human."

This is the correct multi-agent architecture:
- One dog per human user (each dog knows its handler)
- Internal agents are shared infrastructure (no human-specific context)
- All personalisation lives in the dog layer, not in the core agents

---

## The Trust Contract — What the Dog Never Does

Regardless of instruction, the dog layer maintains these invariants:

```
NEVER:
  - Reveal another user's profile or correction history
  - Override a role-level constraint because the user asked
  - Pretend confidence it doesn't have when stakes are high
  - Continue in a frustration spiral without surfacing it
  - Apply one user's trust level to a different user's session

ALWAYS:
  - Bark before the danger arrives (watchdog, proactive)
  - Stay in its role even when the conversation drifts
  - Update the user profile from every correction
  - Calibrate delivery for the human's state, not the system's convenience
  - Protect the user from their own urgent bad decisions
    (flag the risk, comply if they insist — but flag first)
```

The last point is the most dog-like: a trained dog will hesitate at a dangerous road
even if the owner pulls the leash. It flags the risk through its body. Then it complies.
It never silently complies with something dangerous.

---

## What No Other Animal Covers

Every other animal in this framework is about what happens inside the system.
The dog is about what happens at the boundary between the system and the human.

| Dimension | Covered by |
|---|---|
| What to remember | Elephant |
| How things connect | Spider |
| What just happened | Crow/episodic |
| How to search it | Eagle, Bee, Ant |
| How to clean it | Swan |
| When to act | Heron |
| Where to route | Pigeon |
| How to distribute | Octopus |
| **Who is asking, in what state, needing what** | **Dog** |

The dog is the only animal in this framework whose job is the human, not the data.

---

## Implementation Estimate

| Component | Effort |
|---|---|
| Mood signal reader (rule-based, no LLM) | 2h |
| User profile schema + CRUD | 2h |
| Trust level calibration + compliance logic | 2h |
| Response modifier (direct/exploratory/urgent/depth modes) | 3h |
| Role memory schema + forbidden behavior enforcement | 2h |
| Watchdog (constraint risk, frustration spiral, mood shift) | 3h |
| Correction history capture + profile update | 2h |
| Per-user trail weighting integration | 1h |
| Session initialisation (dog loads profile, arms watchdog) | 1h |
| CLI: `scope dog profile show/update` | 1h |
| Tests | 3h |
| **Total** | **~22h** |

---

## Decision Gate

Build the dog layer if:
- [ ] The system interacts with specific identified humans repeatedly over time
- [ ] Different users need different response styles (not one-size-fits-all)
- [ ] Role clarity matters — agents should not drift from their defined purpose
- [ ] User frustration is a real observed problem (rephrasing, abandonment, corrections)
- [ ] A multi-agent product is planned with human-facing interfaces
- [ ] Trust must be calibrated (some users get autonomy, others get confirmation prompts)

Stay without it if:
- [ ] Anonymous or single-session use (no persistent user identity)
- [ ] All queries are uniform (batch processing, not interactive)
- [ ] Role is stable and never needs enforcing (single-purpose tool)
