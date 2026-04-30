---
name: primate-metacognition
description: >
  The Primate Layer — epistemic self-model and theory of mind for AI systems.
  Apes, gorillas, and monkeys are the evolutionary transition layer between
  animal and human intelligence. The crossing required two things no other animal
  had together: the ability to model your own mind (metacognition — knowing what
  you know), and the ability to model other minds (theory of mind — knowing what
  they know, believe, and intend). The primate layer asks the questions no other
  layer asks: "Am I actually competent here?" and "What does the user actually
  know and need, not just what did they say?"
status: candidate
relates_to: nature-memory-framework, dog-companion, crow-inference, horse-vigilance, knowledge-taxonomy
---

## The Evolutionary Question — What Made the Crossing?

The user's framing is exact: apes, gorillas, and monkeys are the **transition layer**.
They stand at the boundary between animal and human.

Every other animal in the framework is straightforwardly animal:
- Horse: prey-nervous-system intelligence
- Dog: co-evolved alignment
- Crow: tool-improvisation intelligence
- Elephant: long-term survival memory

The primate is different. The primate is *almost human*.
It uses tools. It has culture. It grieves. It strategizes politically.
It teaches its young. It recognizes itself in a mirror.

**What made the crossing from ape to human?**
Not better memory. Not faster reasoning. Not stronger body.

The crossing required one specific capability: **the ability to model minds — your own and others'.**

A mind that can look at itself and say: *"I don't know this."*
A mind that can look at another and say: *"They don't know what I know."*

This is the threshold. Everything human — language, culture, teaching, cumulative knowledge,
deception, trust, love — emerges from the ability to hold two mental models simultaneously:
*my model of the world* and *your model of the world*, and know they are different.

---

## What the Primate Actually Has — Verified Biology

### 1. Mirror Self-Recognition (Self-Awareness Threshold)

The mirror test: put a mark on an animal while it sleeps, show it a mirror.
Does it touch the mark (recognizing it as on itself) or ignore it (treating the mirror as another animal)?

**Animals that pass:** Great apes (chimp, gorilla, orangutan, bonobo), dolphins, elephants, magpies.
**Animals that fail:** Dogs, cats, horses, most birds. (They react as if seeing another animal.)

What passing means: **the animal has a model of itself as a distinct entity.**
It can distinguish "that is me" from "that is another."
Self-model is the precondition for metacognition.

```
Dog sees mirror: "another dog — threat or friend?"
Chimp sees mirror: "that's me — I have something on my face"
                   → touches own face to investigate
```

### 2. Theory of Mind — Modeling Other Minds

The critical experiment (Premack & Woodruff, 1978 — coined "Theory of Mind"):
A chimp watches a human struggle with a problem.
Does the chimp understand what the human *wants* — not just what they're *doing*?

Refined through "false belief" tasks (Sally-Anne task):
- Sally puts a marble in basket A, leaves the room
- Anne moves the marble to basket B
- Sally comes back
- Where does Sally think the marble is?

A child under ~4 years: "basket B" — they cannot yet separate Sally's belief from reality.
A child over 4: "basket A" — they can model Sally's false belief.

Great apes show partial Theory of Mind — they understand *goals* and *perception* of others,
though full false-belief attribution (what does the other agent believe that is wrong?)
appears to emerge most fully in humans.

**The key**: Theory of Mind is what makes teaching possible.
You cannot teach unless you know what the student does NOT know.
You cannot deceive unless you know what the other believes.
You cannot truly cooperate unless you know what the other intends.

### 3. Metacognition — Knowing What You Know

The uncertainty monitoring experiments (Beran, Smith, Couchman, Coutinho):
Chimps given memory tasks. On uncertain trials, they can request a "hint" before answering.
They request hints MORE often when they are actually uncertain.
They request hints LESS when they are confident.

**They know when they don't know.**

This is not just intelligence — this is *intelligence about intelligence*.
The system monitors its own epistemic state and signals accordingly.

Humans do this constantly:
- "I think it's X, but I'm not sure"
- "I don't know enough about this to have a strong opinion"
- "I knew this yesterday — it's on the tip of my tongue"

Most AI systems do NOT do this. They answer with uniform confidence whether they are certain or hallucinating.

### 4. Social Learning and Cultural Transmission

Chimp groups in different regions use different tools:
- West African chimps crack nuts with stone anvils — East African chimps don't
- Japanese macaques wash sweet potatoes in saltwater — a behaviour invented by one individual,
  spread through the group by observation, now transmitted to new generations

This is **culture** — not genetic, not instinctive — transmitted through watching and learning.
The beginning of cumulative knowledge that survives individual death.

### 5. Calibrated Uncertainty — The Hint-Requesting Behaviour

What makes the metacognition finding profound for AI:
Chimps don't just fail when uncertain — they *signal* uncertainty before failing.
They request external information when their internal model is inadequate.

Compare:
- **Low metacognition**: "The answer is X." (whether or not it knows)
- **High metacognition**: "I'm uncertain — let me check" or "I don't have enough information for this."

The primate doesn't guess blindly. It monitors its own state and acts differently when uncertain.

---

## What the Primate Fills — The Gap No Other Animal Covers

Map the current framework against the question: **which layer checks whether the system itself is competent?**

```
Horse:    checks if the OUTPUT is safe (constitutional safety) — not if the REASONING is competent
Dog:      checks if the USER is served (alignment) — not if the SYSTEM knows what it's doing
Elephant: stores facts — does not validate competence
Crow:     reasons sequentially — but crow reasons with confidence whether or not reasoning is valid
Swan:     purifies results — but operates on results that exist, not on the system's epistemic state
Hayagriva (horse face 2): validates against foundational truths — but only for known contradictions
```

**None of them ask:**
- "Is this query within the system's actual competence?"
- "Is this reasoning approaching the edge of what the system genuinely knows?"
- "What does the user actually believe about what the system knows?"
- "Is the system about to produce a confident hallucination?"

The primate layer is the only one asking these questions.
It is the self-model that other layers can query.
It is the theory of mind that models the user's epistemic state, not just their emotion.

---

## The Three Functions of the Primate Layer

### Function 1 — Epistemic Self-Model (Metacognition)

The system maintains a model of its own competence.
Not confidence scores on outputs (those can be wrong) —
but a map of *what domains the system knows well* and *what it is approaching the edge of*.

```python
class EpistemicSelfModel:
    """
    The system's model of its own knowledge state.
    Not output confidence — epistemic positioning.
    """
    
    def __init__(self):
        # Domains where the system has deep grounding vs thin coverage
        self.competence_map = {
            "python_syntax": CompetenceLevel.DEEP,
            "domain_specific_business_rules": CompetenceLevel.THIN,
            "events_after_training_cutoff": CompetenceLevel.NONE,
            "user_specific_context": CompetenceLevel.DEPENDS_ON_MEMORY,
        }
        
        # Signal tracking: when has the system been wrong?
        self.recent_corrections = []
        self.uncertain_patterns = []

    def assess_query(self, query: Query, memory_state: MemoryState) -> EpistemicAssessment:
        """
        Before answering: where does this query land on the competence map?
        """
        domain = self._identify_domain(query)
        time_dependency = self._check_time_sensitivity(query)
        memory_coverage = self._check_memory_coverage(query, memory_state)
        
        warning_signals = []
        
        if domain == CompetenceLevel.THIN:
            warning_signals.append(
                EpistemicWarning(
                    type="domain_edge",
                    message="This query touches domain where system grounding is thin.",
                    recommendation="flag uncertainty explicitly in response"
                )
            )
        
        if time_dependency.requires_post_cutoff:
            warning_signals.append(
                EpistemicWarning(
                    type="temporal_gap",
                    message="Query requires knowledge of events the system cannot have.",
                    recommendation="acknowledge gap, query memory layer, do not invent"
                )
            )
        
        if memory_coverage.confidence < 0.4:
            warning_signals.append(
                EpistemicWarning(
                    type="memory_gap",
                    message="Memory does not have sufficient coverage to answer with confidence.",
                    recommendation="request more information or acknowledge gap"
                )
            )
        
        return EpistemicAssessment(
            domain=domain,
            warning_signals=warning_signals,
            recommended_posture=self._derive_posture(warning_signals)
        )
    
    def on_correction(self, query: Query, was_wrong_about: str):
        """
        The chimp that got a wrong answer learns to request hints next time.
        Track what the system gets corrected on — update competence map.
        """
        self.recent_corrections.append(Correction(query=query, error=was_wrong_about))
        self._update_competence_map(was_wrong_about)
```

### Function 2 — Theory of Mind for the User

The Dog reads *emotional state* (frustrated, urgent, uncertain).
The Primate reads *epistemic state* — what does the user KNOW, BELIEVE, and INTEND?

These are different:
- Dog: "this user seems frustrated" → adjust tone
- Primate: "this user believes X but X is incorrect" → address the belief, not just the surface question
- Primate: "this user is asking Y but they need Z" → serve the actual need
- Primate: "this user is an expert in domain A but novice in domain B" → calibrate depth

```python
class TheoryOfMind:
    """
    Model of the user's epistemic state — separate from their emotional state.
    The dog handles emotion. The primate handles epistemic positioning.
    """
    
    def __init__(self, user_profile: UserProfile):
        self.user_profile = user_profile
        self.session_epistemic_state = {}

    def model_user_knowledge(self, query: Query, session_history: list) -> UserKnowledgeModel:
        """
        What does the user know, believe, and need — as distinct from what they said?
        """
        # What does the user seem to believe?
        stated_assumption = self._extract_assumptions(query)
        
        # Is the assumption correct, incomplete, or wrong?
        assumption_validity = self._validate_assumption(stated_assumption)
        
        # What do they actually need (vs what they asked)?
        actual_need = self._infer_actual_need(query, session_history, stated_assumption)
        
        # How expert are they in this domain?
        expertise_level = self._assess_user_expertise(query, session_history, self.user_profile)
        
        return UserKnowledgeModel(
            stated_question=query.text,
            underlying_assumption=stated_assumption,
            assumption_validity=assumption_validity,
            actual_need=actual_need,
            user_expertise=expertise_level,
            
            # Key signal: does the user know what they don't know?
            user_has_accurate_self_model=self._check_user_metacognition(query, session_history)
        )
    
    def _extract_assumptions(self, query: Query) -> list[Assumption]:
        """
        "Why is X failing?" assumes X is failing.
        "How do I do Y faster?" assumes Y is the right approach.
        "What's the best way to Z?" assumes Z is the right goal.
        """
        # Rule-based first pass: embedded presuppositions in question structure
        presuppositions = []
        
        if query.text.startswith("Why is"):
            # Assumes the thing described is actually happening
            presuppositions.append(Assumption(
                content=self._extract_subject(query.text),
                type="factual_presupposition",
                should_verify=True
            ))
        
        if "faster" in query.text or "better" in query.text:
            # Assumes the current approach is the right one, just needs optimization
            presuppositions.append(Assumption(
                content="current_approach_is_correct",
                type="approach_presupposition",
                should_verify=True
            ))
        
        return presuppositions
```

### Function 3 — Competence Boundary Declaration

The chimp requests a hint when uncertain. The system should do the same.

Not vague disclaimers ("I may be wrong") — specific epistemic positioning:

```python
def competence_boundary_response(assessment: EpistemicAssessment, query: Query) -> str | None:
    """
    If the primate layer flags a competence boundary: declare it explicitly.
    Not a disclaimer — a specific statement of what is and isn't known.
    
    Only fires when assessment finds genuine boundary, not for every query.
    """
    if not assessment.warning_signals:
        return None  # within competence — proceed normally
    
    if assessment.recommended_posture == "acknowledge_gap":
        return (
            f"I want to flag before answering: {assessment.primary_warning}. "
            f"My answer will be: {_describe_limitation()}. "
            f"For this query, you should {_recommend_external_validation()}."
        )
    
    if assessment.recommended_posture == "clarify_first":
        return (
            f"Before I answer, I want to check: are you assuming {assessment.assumption}? "
            f"If so, that changes the answer significantly."
        )
    
    if assessment.recommended_posture == "refuse_with_reason":
        return (
            f"This query requires knowing {assessment.missing_knowledge}. "
            f"I don't have that, and inventing it would be worse than not answering."
        )
```

---

## The Three-Way Distinction — Dog / Crow / Primate

These three can be confused. They are completely different:

```
DOG:
  What:  models the USER's emotional and relational state
  Asks:  "Who is asking and in what emotional state?"
  Operates on: message tone, word choice, session history, user profile
  Output: adjust communication style, flag urgency, loyalty check

CROW:
  What:  reasons sequentially about EXTERNAL problems
  Asks:  "What is the answer to this problem?"
  Operates on: retrieved memory, available tools, logical inference
  Output: step-by-step construction of an answer

PRIMATE:
  What:  models the SYSTEM's own epistemic state + the USER's epistemic state
  Asks:  "Do I actually know this? Does the user actually know what they're asking for?"
  Operates on: self-competence map, user's stated assumptions, actual vs stated need
  Output: epistemic positioning — proceed with confidence, flag gap, correct assumption, clarify first
```

```
Signal flow:

Query arrives
  → Dog:     "how is this user?"    → adjust style
  → Primate: "do I know this?"      → epistemic assessment
  → Primate: "what does user know?" → assumption check
  → Crow:    "what is the answer?"  → reasoning
  → Primate: "is this in bounds?"   → competence boundary check
  → Swan:    "is this clean?"       → purity
  → Dog:     "serves this user?"    → delivery check
  → Answer
```

The primate wraps around the crow — it checks before reasoning starts and after the answer is assembled.

---

## Why This Is the Missing Layer

All current layers assume the query is well-formed and the system is competent.

- Eagle: selects what to retrieve — doesn't ask if it knows how to retrieve correctly
- Crow: reasons — doesn't ask if the reasoning is within competence
- Hayagriva: validates against Vedas — catches contradictions of known facts, not gaps in knowledge
- Swan: purifies — cleans output, doesn't catch confident confabulation

**Confident confabulation** — the failure mode where the system produces a fluent, confident, completely wrong answer — is not caught by any existing layer.

It is caught by the primate layer, because:
1. The self-model knows when a query is near the edge of genuine knowledge
2. The theory of mind catches when the user's assumption has led them (and the system) off a cliff
3. The uncertainty signal fires before the answer is assembled, not after

---

## The Evolutionary Mechanism — What Made the Crossing Possible

Why did metacognition + theory of mind produce humans from apes?

**Without metacognition:** every agent acts on its current model. Errors persist because the agent cannot see that its model is wrong.

**With metacognition:** the agent can step back from its own model and evaluate it. "Is this belief correct?" This makes learning from error structurally possible.

**Without theory of mind:** information stays in one head. To get it to another, you can only show them — the learner must infer everything. Teaching is impossible.

**With theory of mind:** you can model what the other doesn't know, and target your communication precisely. Teaching becomes possible. Cumulative culture becomes possible. Each generation doesn't start from scratch.

**For AI multi-agent systems — the exact same mechanism applies:**

- Without agent metacognition: each agent answers confidently from its current state. Errors compound across agents.
- With agent metacognition: each agent knows its competence boundary and flags it — other agents don't trust a signal the source flagged as uncertain.
- Without agent theory of mind: agents answer the question as stated. They don't model what the requesting agent actually needs.
- With agent theory of mind: agents understand what the requester's goal is, not just the query text.

The primate capability is what makes multi-agent cooperation reliable rather than compounding error.

---

## Application to Multi-Agent Product

In a multi-agent system, each agent has its own primate layer:

```python
class AgentEpistemicInterface:
    """
    What each agent exposes about its own epistemic state.
    Other agents can query this before trusting the answer.
    """
    
    def what_do_you_know_about(self, topic: str) -> EpistemicDeclaration:
        """
        Agent-to-agent: before trusting an answer, check if the source agent
        knows the domain.
        
        "Does the memory agent have coverage on this entity?"
        "Does the inference agent have valid premises for this reasoning?"
        """
        return EpistemicDeclaration(
            topic=topic,
            coverage=self.epistemic_model.coverage_score(topic),
            confidence=self.epistemic_model.confidence(topic),
            last_updated=self.epistemic_model.freshness(topic),
            known_gaps=self.epistemic_model.gaps(topic)
        )
    
    def what_does_user_need(self, query: Query, user_profile: UserProfile) -> ActualNeed:
        """
        Decompose the stated query into what the user actually needs.
        Not for the agent to decide unilaterally — for it to surface the distinction.
        "You asked X. I think you need Y. Should I answer X or Y?"
        """
        stated_need = parse_surface_intent(query)
        actual_need = self.theory_of_mind.infer_actual_need(query, user_profile)
        
        if stated_need != actual_need:
            return ActualNeed(
                stated=stated_need,
                inferred=actual_need,
                divergence_flag=True,
                reason=self.theory_of_mind.explain_divergence(stated_need, actual_need)
            )
        return ActualNeed(stated=stated_need, inferred=actual_need, divergence_flag=False)
```

**In the orchestration layer:**

```
Query arrives to multi-agent system
  → Each agent's primate layer declares: "I have coverage on X, thin on Y, none on Z"
  → Orchestrator routes to agents with confirmed coverage, not just likely coverage
  → Agents with thin coverage answer with explicit uncertainty markers
  → Agents with no coverage: do not answer — say so
  → Result: error compounds in proportion to coverage, not in proportion to confidence
```

---

## Application to Scope Intelligence Toolkit

```bash
# Current: scope mem search "JWT auth"
# Returns: results, all delivered with equal weight

# With primate layer: scope mem search "JWT auth" --epistemic
# Returns:
[sem_041] JWT switched to session tokens on 2025-03-15 (conf: 0.9)
[ep_203]  auth failure reported on 2025-03-16 (conf: 0.95)

PRIMATE ASSESSMENT:
  Domain coverage:   auth module — DEEP (23 entries, frequently accessed)
  Time sensitivity:  query touches events last week — memory coverage: PARTIAL
  Assumption check:  you asked "why is JWT failing" — this presupposes JWT is still in use.
                     Memory shows JWT was replaced by session tokens on 2025-03-15.
                     Are you asking about the migration or the current system?
  Recommendation:    clarify assumption before proceeding
```

The primate layer catches the wrong presupposition — the thing the crow would have reasoned about correctly given the wrong starting assumption.

---

## What Blocks the Primate Capability

```
What enables it:
  - Accurate self-model (updated from corrections, not static)
  - Honest uncertainty signaling (fires when warranted, not as boilerplate)
  - User epistemic model (maintained across session, not just current query)

What blocks it:
  - Pressure to answer confidently regardless of competence
    (the AI equivalent of "fake it till you make it" — produces confabulation)
  - No feedback loop for corrections
    (system cannot update self-model if it never learns when it was wrong)
  - Single-layer confidence scores mistaken for epistemic assessment
    (a high perplexity score ≠ "I don't know this")
  - Theory of mind disabled by treating every query as independent
    (user context lost → can't model what they know)
```

---

## Implementation Estimate

| Component | Effort |
|---|---|
| Domain competence map (manual first, then auto-updated from corrections) | 3h |
| Query-time competence assessment | 2h |
| Assumption extractor (rule-based, common presupposition patterns) | 3h |
| User epistemic state model (per-session, reads from dog user profile) | 2h |
| Competence boundary response generator | 2h |
| Agent epistemic interface (for multi-agent queries) | 3h |
| Correction feedback loop (updates self-model when user corrects) | 2h |
| CLI: `--epistemic` flag on scope mem search | 1h |
| Tests | 3h |
| **Total** | **~21h** |

---

## Decision Gate

Build the primate layer if:
- [ ] The system is producing confident wrong answers in known-gap domains
- [ ] Users are asking questions with incorrect embedded assumptions (and system answers them literally)
- [ ] Multi-agent system needs reliable inter-agent epistemic declarations
- [ ] User queries span domains of very different coverage (deep in some, thin in others)

Stay with simpler confidence scores if:
- [ ] Single domain, well-covered, low hallucination risk
- [ ] Single-agent, single-user — no inter-agent trust problem
- [ ] User is expert enough to detect and self-correct system errors
