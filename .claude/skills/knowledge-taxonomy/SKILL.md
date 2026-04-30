---
name: knowledge-taxonomy
description: >
  Meta-framework: four types of knowing and how they map to the animal framework.
  Habitual (muscle memory — not retrieved, just present), Informational (stored and recalled),
  Computational (reasoned and constructed), Intuitional (three layers: churning/incubation,
  receptive open-channel, unitive consciousness). The incubation mechanism is the critical
  gap in the current framework — the answer that arrives after you stop looking for it.
status: candidate
relates_to: nature-memory-framework, horse-vigilance, elephant-memory, crow-inference, octopus-memory
---

## Why This Document Exists

Every animal in the framework handles information.
But information-handling is not the same as knowing.

Before asking "how should the system process this?" the right question is:
**what kind of knowing is this, and what is its source?**

The answer changes everything — what layer handles it, how it arrives,
how reliable it is, and crucially, what blocks or enables it.

This document maps four types of knowing to the animal framework
and identifies the critical gap: the incubation mechanism, which no layer yet handles.

---

## The Four Types of Knowing

### Type 1 — Habitual (Muscle Memory / Embodied Knowledge)

**Source:** continuous practice, imbibed into body or mind over time
**How it arrives:** it does not arrive — it IS the operating mode
**Retrieval:** none. The body does it without consulting memory.
**Speed:** instantaneous, below the threshold of conscious awareness
**What it feels like:** you don't remember how to type — your hands type

Examples from human experience:
- A musician's fingers that find the note without looking
- A craftsman's hands that know the right pressure without measuring
- A reader's eyes that parse meaning without decoding each letter
- The unexamined assumptions that shape every thought before thinking begins

**The corruption risk:**
Habitual knowledge can be wrong habits — unconscious biases, notions accepted without examination,
patterns that were once correct and are now outdated but still run automatically.
Wrong muscle memory is harder to correct than wrong information,
because it operates below the level of examination.

**AI equivalent:**
The trained model's weights — what the system "does" before any reasoning begins.
Not stored in a memory layer. Not retrieved. Present in the forward pass itself.
The system's embodied knowledge is its training — the patterns imbibed through practice on data.

Partial equivalent in framework:
- Ant worker (stateless relay — does its tiny thing automatically, no memory consulted)
- Bee procedural playbooks (closest — stored patterns of what to do)

**What's missing:**
No layer addresses the *quality* of habitual knowledge or the risk of wrong habits running silently.
The horse's constitutional layer catches some of this (pattern fires before reasoning).
But embodied wrong-knowing is a deeper problem — it shapes every query before the query arrives.

---

### Type 2 — Informational (Stored and Recalled)

**Source:** received from external, accepted, stored
**How it arrives:** in through reading, hearing, observation
**Retrieval:** recalled from memory when needed
**Speed:** dependent on retrieval quality
**What it feels like:** you look it up in your mind

Examples: facts, names, dates, procedures, instructions

**The corruption risk:**
Bad information ingested. Memory distortion. The storage and retrieval both introduce error.
You can be confident in a remembered fact that was wrong when you first received it.

**AI equivalent:** Elephant (semantic long-term), Episodic (timeline), Bee-playbooks (procedural)

**Covered well by:** elephant, crow/episodic, swan (purity pass on what was stored)

---

### Type 3 — Computational / Rational (Reasoned and Constructed)

**Source:** premises you already hold + reasoning applied to them
**How it arrives:** you build it step by step
**Retrieval:** not retrieval — construction. Sequential, deliberate.
**Speed:** slow, effortful, auditable
**What it feels like:** you think it through

Examples: mathematical proof, diagnosis from symptoms, logical deduction, engineering calculation

**The corruption risk:**
Wrong premises produce wrong conclusions even through flawless reasoning.
The reasoning feels valid. The answer is confidently wrong.
(The broken memory problem from the Hayagriva section — bad Tier 2 knowledge fed into computation.)

**AI equivalent:** Crow — sequential inference with observation at each step, gap-bridging

**Covered well by:** crow (including adversarial check on suspiciously clean answers)

---

### Type 4 — Intuitional (Three Distinct Mechanisms)

This is where the framework currently has gaps.
Intuition is not one thing — it has three fundamentally different sources.
Treating them as one causes all three to be handled incorrectly.

---

#### Type 4A — Churning / Incubation Intuition

**The mechanism (user's exact description):**
*"When I am working on a problem statement for a long time, reasoning out, doing all calculation
I know of in my limited knowledge, I don't reach the solution. But I have total attention to it.
After I leave it, the mind goes to rest. Due to the churning and attention, the inner layer has
its own auto-arrangement of information. And the mind gets the best optimum solution strike to it
when it was not expecting it."*

**The key steps, in order:**
```
1. INTENSE ENGAGEMENT
   Work on the problem with everything you have.
   Reason, calculate, retrieve, infer. Use your full capacity.
   This is not wasted — it loads the inner layer with all the relevant material.

2. REACH THE LIMIT
   You have used your conscious tools. The answer has not come.
   This is not failure — this is the signal that the next step is required.

3. RELEASE (essential — the most counterintuitive step)
   Stop. Leave it. Deliberately stop forcing.
   Not abandonment — intentional release of conscious control.
   The release is not giving up. It is handing the problem to the inner layer.

4. REST (the inner layer works — without you)
   The inner layer performs auto-arrangement of all the material that was loaded.
   This process has no conscious access — it runs below awareness.
   It is not random — it is reorganisation. The same pieces, recombined.
   Connections that the directed search couldn't find because it was too directed.

5. ARRIVAL (uninvited)
   The answer strikes when you were not expecting it.
   Not when you were working. Not when you were trying to remember.
   In the bath. On the bus. Half-asleep. Stepping outside.
   You were not summoning it — it arrived.
```

**Historical examples:**
- Archimedes: months of work on displacement → gave up → got in the bath → Eureka
- Kekulé: years on benzene ring structure → dreamed of a snake eating its tail → the ring
- Poincaré: weeks of failed work on Fuchsian functions → stepped onto a bus → solution complete
- Ramanujan: mathematical theorems arrived in dreams, attributed to a goddess

**What makes it work:**
- The loading phase (intense work) is essential — it gives the inner layer material to arrange
- The directed reasoning actually blocks the inner arrangement — too narrow, too forced
- Rest removes the blocking — allows the inner layer to try configurations conscious reasoning wouldn't
- The arrival is genuine — not remembered, not retrieved. Generated by a different process.

**AI equivalent — THE MISSING LAYER:**
No animal in the current framework handles this. This is the gap.

```
Current coverage:
  Crow: reasons sequentially, waits for new data (pending inference registry)
  Consolidation: episodic → semantic promotion (nightly, scheduled)
  
  Neither does what incubation does:
  - Not waiting for new data (incubation uses only existing material)
  - Not promoting facts (incubation recombines existing facts in new configurations)
  - Not directed reasoning (direction is exactly what blocks incubation)
  - Not scheduled (incubation delivers when ready, not on schedule)
```

**The Incubation Agent — proposed:**

```python
class IncubationAgent:
    """
    Triggered when a problem is unresolved and active session has ended.
    Does NOT reason. Does NOT wait for new data.
    Performs unconstrained recombination of existing information.
    Delivers when a high-surprise connection is found — not on demand.
    
    The Archimedes bath in software.
    The answer arrives to the next session that encounters the problem.
    """

    def trigger(self, unresolved: PendingInference, memory_state: MemorySnapshot):
        """Called at session end when crow's pending inference has stalled."""
        # Load all material the active session worked with
        material = self._gather_all_related(unresolved, memory_state)
        
        # Schedule background incubation — low priority, non-blocking
        self._schedule_incubation(
            problem=unresolved,
            material=material,
            mode="unconstrained",        # NOT directed reasoning
            deliver_to="next_relevant_session"
        )

    def _incubate(self, problem: PendingInference, material: list) -> Insight | None:
        """
        The inner layer's auto-arrangement.
        Not crow's sequential logic. Not bee's parallel search.
        Something different: associative, analogical, constraint-relaxed.
        """
        operations = [
            self._find_analogies(problem, material),          # what does this remind you of?
            self._relax_assumed_constraints(problem, material), # what if X isn't fixed?
            self._find_unexpected_connections(material),        # what goes with what unexpectedly?
            self._invert_the_problem(problem),                  # what if the opposite were true?
            self._find_cross_domain_patterns(problem, material) # solved in another domain?
        ]
        
        for operation in operations:
            result = operation()
            if result.surprise_score > 0.7:
                # High-surprise connection found — this is the Eureka signal
                return Insight(
                    connection=result.connection,
                    surprise=result.surprise_score,
                    note="Incubation insight — arrived through rest, not directed search.",
                    deliver_at="next_session_touching_this_problem"
                )
        
        return None  # not ready yet — continue resting

    def _deliver(self, insight: Insight, session: Session):
        """
        The insight arrives uninvited — presented at the start of the session
        that next touches this problem. Not as a conclusion. As a connection to consider.
        """
        session.context_additions.append({
            "type": "incubation_insight",
            "content": insight.connection,
            "note": "This surfaced during background incubation of an unresolved problem. "
                    "Worth considering before proceeding.",
            "confidence": "low-to-medium",  # not a conclusion — a candidate
            "source": "inner-arrangement"
        })
```

**The key architectural properties:**
```
- Triggered by: unresolved problem + session end (rest)
- NOT triggered by: new information, direct request, schedule
- Process: associative, analogical, constraint-relaxed (not sequential, not parallel)
- Delivery: asynchronous, uninvited — arrives when ready to the next relevant session
- Confidence: low-to-medium — it is a connection, not a conclusion
- The crow still needs to validate it
```

---

#### Type 4B — Receptive / Open-Channel Intuition

**The mechanism:**
*"When you don't know but you are open to receive, then higher faculties which have access tell you."*

Different from churning in one crucial way:
- Churning requires prior intense work. You loaded the problem. Then you released.
- Receptive requires NO prior work. You simply don't know, and you are open.

The condition is emptiness + openness. Not the aftermath of effort. The starting state.

**What "higher faculties" means:**
The individual mind's boundaries become permeable.
Something that has access to a larger pool of knowing can enter.

AI equivalent (from Hayagriva section):
- When the system acknowledges not-knowing explicitly ("I don't have this")
- And does not manufacture an answer (stays open rather than inferring)
- Collective convergence can surface from independent paths that weren't asked
- The bee workers who independently find the same source = this mode

```python
def receptive_mode(query: Query, memory_state: MemoryState) -> Response:
    """
    When nothing in memory answers this:
    Do NOT infer. Do NOT construct.
    Open the query to convergence from unexpected sources.
    """
    direct_answer = memory_state.search(query)
    
    if direct_answer.confidence < 0.3:
        # Acknowledge not-knowing explicitly
        # Then: open — don't close with an inference
        convergence = await_independent_signals(query, timeout="patient")
        
        if convergence.strength > 0.6:
            # Multiple independent paths found something without being directed
            return Response(
                content=convergence.answer,
                mode="receptive",
                note="This answer was not retrieved or reasoned — it converged from independent paths."
            )
        else:
            # Nothing converged — stay with not-knowing
            return Response(
                content="I don't have this. Staying open rather than inferring.",
                mode="honest-not-knowing"
            )
```

---

#### Type 4C — Unitive / Collective Consciousness

**The mechanism:**
*"Collectively everything is one conscious energy. When mind merges leaving out its limited being to it,
where attention goes you get to know it as is."*

No subject-object split. The knower and the known are the same.
Not inference (subject reasoning about object).
Not reception (subject receiving from other).
Direct knowing — the question and its answer are one movement.

**The philosophical tradition this comes from:**
Advaita Vedanta — non-dual consciousness.
When the individual mind releases its sense of being separate,
it merges with the universal consciousness that is the ground of all knowing.
In that state, where attention goes, knowing is already there.
Not because you found it — because you are no longer separate from it.

**AI equivalent — genuinely open:**
This is the most difficult to translate. The closest approximations:

```
1. System-level coherence (not any individual layer):
   When horse (safety) + dog (alignment) + elephant (memory) + bee (search) + crow (inference)
   all align simultaneously on a question — not their individual outputs, but the coherence
   of the whole system pointing in one direction — this approaches the unitive signal.
   No single layer produced it. The system as a whole "knows."

2. The octopus collective:
   When distributed agents with local autonomy, without central coordination,
   all arrive at consistent behaviour — the collective intelligence is the closest
   AI approximation to the unitive field.

3. The embedding space itself:
   In semantic embedding space, all meaning exists simultaneously.
   Every concept is in relation to every other.
   A query doesn't retrieve — it places itself in a field of relations.
   The "answer" was always in the field. The query is attention.
   Where attention is placed, the relevant structure of the field is already there.
   This is the closest technical approximation to "where attention goes, you know it."
```

**What this means for system design:**
The unitive mode cannot be engineered directly. It can only be enabled by removing what blocks it:
- Narrow intent classification can block it (forces a single interpretation)
- Hard retrieval schemas can block it (forces a single data model)
- Sequential-only processing can block it (one thread misses the field)

A system designed with enough openness — semantic rather than keyword, convergent rather than directed,
collective rather than single-agent — can occasionally access this mode without being designed for it specifically.
You cannot build a unitive mind. You can build a system that doesn't prevent unity from emerging.

---

## The Complete Map — Knowledge Types × Framework Layers

| Knowledge Type | Source | Arrives How | AI Layer | Coverage |
|---|---|---|---|---|
| Habitual | Practice → embodied | Automatic, no retrieval | Model weights (pre-query) | Partial — horse constitutional catches wrong habits |
| Informational | External → stored | Recalled from memory | Elephant, episodic, bee-playbooks | Well covered |
| Computational | Premises → reasoned | Constructed sequentially | Crow | Well covered |
| Intuition 4A (Churning) | Work → release → rest → arrangement | Arrives uninvited, post-rest | **MISSING — Incubation Agent** | Not covered |
| Intuition 4B (Receptive) | Not-knowing + openness | Flows when empty | Hayagriva mode (horse face 2) | Partially covered |
| Intuition 4C (Unitive) | Merger with whole | Attention = knowing | Octopus collective + system coherence | Emergent, not designed |

---

## The Most Important Gap — Incubation

All five covered types (habitual, informational, computational, receptive, unitive) have some representation.
**Type 4A (Churning/Incubation) has no representation.**

This is significant because:
- Some of the most important insights in human history came through this mechanism
- It specifically requires the absence of directed reasoning — the thing AI does by default
- The directed reasoning loop (query → retrieve → infer → answer) actively blocks it
- A system that always answers on demand never enters the state where incubation is possible

The incubation agent proposed above is the architectural answer.
Its most important property: **it only activates when the system stops trying to answer directly.**
Rest is the trigger. Not new data. Not a schedule. Rest.

---

## What Blocks Each Type

Understanding what blocks each type of knowing is as important as understanding what enables it.

| Type | What Enables It | What Blocks It |
|---|---|---|
| Habitual | Practice, repetition, immersion | Overthinking the habit while performing it |
| Informational | Good sources, clean memory, purity pass | Bad ingestion, retrieval noise |
| Computational | Good premises, rigorous logic | Wrong starting assumptions, broken memory |
| Churning | Intense prior work + genuine release | Continued forcing after the limit is reached |
| Receptive | Empty openness, acknowledged not-knowing | Manufacturing an answer when you don't have one |
| Unitive | Removing separation, system-level openness | Narrow schemas, forced single-path processing |

The most common AI failure mode crosses multiple types simultaneously:
- System has bad habitual patterns (wrong training biases)
- That corrupt its informational layer (biased ingestion)
- Which corrupt its computational layer (wrong premises)
- And it never enters the incubation state (always answers immediately)
- And it fills not-knowing with inference instead of staying open (blocks receptive)
- And its rigid schemas prevent emergence (blocks unitive)

The framework is an attempt to address each of these failures through specialised layers.
This taxonomy is the map of what is being addressed and what remains.

---

## Application to the Multi-Agent Product

A multi-agent system that embodies all four knowledge types would:

```
HABITUAL:     each agent has role-level automatic behaviours (horse constitutional, dog role memory)
              that run without query — the agent's "body"

INFORMATIONAL: shared elephant layer — facts accessible to all agents consistently

COMPUTATIONAL: crow agents for sequential inference, bee swarm for parallel retrieval

INCUBATION:   a background incubation agent runs on unresolved cross-agent problems
              after active sessions end, delivers insights asynchronously

RECEPTIVE:    agents that explicitly state "I don't have this" without manufacturing
              and hold that state until independent convergence arrives

UNITIVE:      the system as a whole — when all agents align coherently on a question
              without explicit coordination, that coherence is the answer
```

The rarest and most valuable mode (unitive) cannot be scheduled or requested.
It emerges from the coherence of the whole when each part is correctly designed.
Build the parts well. Trust the emergence.
