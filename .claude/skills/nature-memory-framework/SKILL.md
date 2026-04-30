---
name: nature-memory-framework
description: >
  Master framework for nature-inspired AI memory architecture.
  Nature solved memory through specialised RETRIEVAL strategies, not just
  specialised storage. A multi-agent memory system should mirror this —
  each memory type is a query strategy, not a separate database.
status: candidate         # not implemented — under evaluation
relates_to: elephant-memory, episodic-memory, scope-intelligence-toolkit
---

## The Philosophy of Each Animal — Start Here

Before mapping animals to software, understand what each animal is *famous for* and *why*.
The philosophy is the lesson. The biology is the proof.

### 🐕 Dog — The Human-Aligned Companion
Famous for: loyalty, reading human emotion, role memory, never forgetting its handler.
The dog is the ONLY animal in this framework that co-evolved specifically with humans —
changing its own physiology (the eyebrow muscle for "puppy eyes," gaze-following, face-processing cortex)
to become better at understanding us. Not trained to comply — built to align.
The dog reads gesture, tone, mood, and urgency before the question is even finished.
It guards its territory and role faithfully without being reminded.
**Philosophy: alignment is not instruction-following. It is understanding what the human needs, not just what they said.**
The dog layer wraps AROUND the entire pipeline — it doesn't process data, it processes the human.
Every other animal is about what the system knows. The dog is about who it serves.

### 🐘 Elephant — The Living World Map
Famous for: "An elephant never forgets."
But the depth goes further. The elephant matriarch IS the herd's collective memory.
She carries route maps spanning hundreds of kilometres — water sources, safe paths, danger zones —
that she may have visited only once, decades ago, passed down from generations before her.
When the matriarch dies, the herd loses its map. Young herds with no matriarch get lost.
**Philosophy: memory as collective survival asset, not individual resource. Depth + durability + transgenerational.**
The elephant doesn't remember everything — it remembers what *the herd needs to survive.*

### 🦅 Eagle — Locks On to the Visible Target
Famous for: seeing a rabbit from 3km and locking focus precisely on a visible target.
The eagle's target is already visible — in the open field, already moving. Its job: choose which visible signal to commit to, lock the forward fovea on it, suppress everything else, dive.
Intelligence is not seeing more — it is **suppressing more of what's visible** to lock on the one thing that matters.
**Philosophy: from what is already visible, select the one thing worth all attention. Commit before certainty. The target is in view — the eagle's choice is what to focus on.**
Contrast with heron: eagle acts on visible signals. Heron waits for hidden signals to surface.

### 🐝 Honeybee — Networked Collective Intelligence Under a Queen
Famous for: building perfect hives and producing honey through collective work.
No single bee designed the hive. No single bee knows the full blueprint.
The queen sets purpose and cohesion through pheromones — she is the orchestrator of direction.
Workers self-organise into specialised roles (nurse, builder, guard, forager) and execute in parallel.
The waggle dance = distributed consensus: competing scouts dance, the best source wins by attracting followers.
**Philosophy: specialised parallel workers + orchestrated purpose + consensus aggregation = collective output greater than any individual.**
The honey is the product of the whole network working in sync.

### 🦢 Heron/Egret — Stillness IS the Strategy
Famous for: standing motionless for hours, then striking in 60ms with lethal accuracy.
The heron has completely separated observation from action. It is always watching. It is almost never acting.
Its S-curved neck is a loaded spring — the longer it waits, the more potential energy accumulated, released completely in one burst.
**Philosophy: inaction is the default. Action is the exception. The threshold separates noise from signal. When threshold is crossed — total commitment, not tentative response.**
The heron corrects for refraction (the fish is not where it appears) — it accounts for systematic distortion before striking.

### 🕊️ Pigeon — Don't Retrieve Data, Navigate to It
Famous for: homing across hundreds of km from unknown locations, reliable message delivery.
The pigeon uses FIVE independent navigation systems simultaneously — magnetic, sun compass, visual landmarks, olfactory maps, infrasound. Remove any one — it still navigates. This redundancy is the design.
Home is not an address. It is a multi-sensory composite signature. The pigeon navigates toward the convergence of all signals pointing home.
**Philosophy: don't route by address — route by context-match. Multi-signal sensor fusion beats single-point routing. If one signal fails, others carry it. The message always arrives.**
The pigeon is the nervous system connecting all other animals in the framework.

### 🐭 Mouse — Probe Before You Commit
Famous for: maze learning, rapid adaptation, surviving in narrow unknown spaces.
The mouse is the only animal in this framework that generates knowledge through **direct experiment** rather than storage or reasoning.
It never random-walks — it hugs walls first (thigmotaxis), systematically maps boundaries, then works inward.
Its whisker array probes N dimensions simultaneously at 25Hz — not one thing at a time, but a fan of simultaneous micro-sensors.
**Philosophy: the system should learn from probing reality, not just from documents. Every experiment is tiny and reversible. The freeze response (anomaly detection) is the most valuable output.**
The mouse creates paths that ants later reinforce and crows later reason about.

### 🦢 Swan — Separate the Milk from the Water (Hamsa Viveka)
Famous for: grace, purity, and in Hindu philosophy — the ability to separate milk from water even when perfectly mixed.
The Hamsa (swan) in Vedanta is the vehicle of Saraswati (knowledge) and represents viveka — pure discernment.
The swan does not search, does not infer. It takes what has been found and makes it pure before delivery.
**Philosophy: most data problems are purity problems. The answer exists — it's just buried in duplicates, stale entries, opinions stated as facts, and low-authority noise.**
The swan sings its most beautiful song just before it dies — superseded facts are archived in their final form before removal.

### 🐦‍⬛ Crow — The Answer Doesn't Exist Yet, So Build It
Famous for: tool use, problem solving, intelligence rivalling primates.
Betty the crow bent a straight wire into a hook — a tool shape she had never seen — to solve a problem in real time.
The crow does not accept the problem as stated. When the answer isn't there, it invents the path to get it.
Crucially: the crow reasons **sequentially with observation** — step 1, observe result, then decide step 2.
Not parallel like bees. Not trail-following like ants. Exploratory, adaptive, step-by-step.
**Philosophy: when the direct answer doesn't exist, construct it from what does — by reasoning across sources in sequence, with course-correction at each step.**
The crow also models other agents' knowledge — it knows what you don't know and bridges exactly that gap.

### 🐜 Ant — The Trail IS the Knowledge (Stigmergy)
Famous for: finding the shortest path without any individual knowing the map.
The individual ant is unintelligent. The pheromone trail in the environment IS the intelligence.
When the trail evaporates, the knowledge is gone. When it's used, it strengthens.
This is stigmergy — coordination through modification of a shared environment.
**Philosophy: the environment stores the knowledge, not the agent. The system learns by being used.**
Over time, retrieval routes that work get reinforced. Routes that don't get used vanish.
No programming, no curation — pure emergent optimisation.

### 🕷️ Spider — Structure IS Knowledge
Famous for: web-spinning, precision, patience.
The spider's web is not just a trap — it is a live sensor network.
Each thread transmits vibration differently by position. The spider navigates the web by *structure*, not by memory of events.
The web IS the knowledge. Topology encodes relationship.
**Philosophy: knowledge of how things connect is as valuable as knowledge of what things are.**

### 🐙 Octopus — Radical Distributed Autonomy
Famous for: intelligence with no central brain — problem-solving, camouflage, tool use.
90% of neurons are in the arms. Each arm acts, senses, and decides independently.
The central brain sets high-level intent ("explore that crevice"). The arm executes without asking.
**Philosophy: real intelligence is local. Central control is a bottleneck. Autonomy at the edge is strength.**
A severed octopus arm still reacts for an hour — the local mind persists without the centre.

---

## The Core Insight

**Nature's lesson: each animal solved a different problem. Together they form a complete system.**

- Dog      → *who is asking and in what state* (human alignment — wraps everything)
- Elephant → *what to remember for the long term* (depth + durability)
- Eagle    → *what to look at right now* (selective attention on visible signals)
- Heron    → *when to act at all* (threshold gate on hidden signals)
- Bee      → *how to search in parallel with consensus* (distributed retrieval)
- Ant      → *which paths have worked before* (reinforced retrieval + pipeline workers)
- Crow     → *how to construct what isn't there* (sequential inference)
- Swan     → *how to make results pure* (discernment before delivery)
- Spider   → *how things connect* (relational structure)
- Mouse    → *what nobody knew to look for* (experimental discovery)
- Pigeon   → *how messages reliably reach the right place* (permanent routing)
- Octopus  → *how to distribute without a centre* (autonomous agents)

In software terms: these are not competing approaches — they are complementary layers
that address different failure modes of a single flat memory store.
The dog is the only layer that operates at the human boundary, not inside the processing core.

---

## The Complete Architecture — All Animals Together

```
                         USER QUERY
                              │
               ┌──────────────▼──────────────┐
               │        🦅 EAGLE LAYER        │
               │   Intent → Entity → Zone     │
               │   Static suppression         │
               │   Narrows what gets searched │
               └──────────────┬──────────────┘
                              │ (selected zones only)
               ┌──────────────▼──────────────┐
               │        🐝 BEE LAYER          │
               │   Queen decomposes query     │
               │   Worker swarm runs in parallel│
               │   Waggle consensus aggregates│
               └──┬──────┬──────┬──────┬─────┘
                  │      │      │      │
           ┌──────▼─┐ ┌──▼───┐ ┌▼────┐ ┌▼──────┐
           │🐘Elephant│ │Crow  │ │🕷️Spider│ │Proced-│
           │Semantic │ │Epis- │ │Relat-│ │ural   │
           │(stable  │ │odic  │ │ional │ │Memory │
           │ truths) │ │(events│ │(graph│ │(how-to│
           └──────┬──┘ └──┬───┘ └──┬──┘ └───┬───┘
                  │       │        │         │
                  └───────┴────────┴─────────┘
                                │
                    ┌───────────▼────────────┐
                    │   SHARED EVENT LOG     │
                    │   (raw facts stream)   │
                    └────────────────────────┘
                                │
           ┌────────────────────▼──────────────────┐
           │           🐙 OCTOPUS LAYER             │
           │  Each agent = local memory + thin sync │
           │  No central coordinator required       │
           │  Agents act autonomously, sync async   │
           └───────────────────────────────────────┘
```

**How to read this:**
- Eagle is the entry point — it filters before any search begins
- Bee orchestrates the parallel search across the narrowed zones
- Elephant / Crow / Spider / Procedural are the storage layers (what gets remembered)
- Octopus is the distribution layer — how storage is spread across agents and machines
- Event log is the single source of truth that all storage layers read from

The event log is the single source of truth.
Each memory layer reads the same log but exposes a different query contract.

---

## The Four Memory Types — Proper Definitions

These are NOT four separate storage systems. They are four retrieval modes.

### 1. Semantic Memory — "What is permanently true?"
- **Nature model**: Elephant (stable world-knowledge, routes, faces, danger patterns)
- **Query**: `what_is("authentication approach")` → stable facts
- **Storage**: key-value or vector embedding
- **Eviction**: facts decay unless reinforced (our confidence decay)
- **Writes**: slow, deliberate (consolidation from episodic events)

### 2. Episodic Memory — "What happened and when?"
- **Nature model**: Crow/Jay (can recall specific past events with time/place context)
- **Query**: `what_happened("engine", since="sprint-2")` → event timeline
- **Storage**: append-only event log with timestamps
- **Eviction**: old events compress into semantic facts (consolidation)
- **Writes**: fast, every event recorded

### 3. Relational Memory — "How do things connect?"
- **Nature model**: Spider (web = graph of nodes + edges, knows the structure not the events)
- **Query**: `what_depends_on("auth-module")` → graph traversal
- **Storage**: adjacency list or property graph
- **Eviction**: edges removed when components deleted
- **Writes**: triggered by structural changes

### 4. Procedural Memory — "How do I do this type of task?"
- **Nature model**: Honeybee swarm (collective know-how, no single bee holds it all)
- **Query**: `how_to("fix-auth-bug")` → pattern → steps
- **Storage**: pattern-matched playbooks / skill templates
- **Eviction**: never (procedures don't decay, they get superseded)
- **Writes**: learned from successful task resolutions

---

## The Consolidation Process — What GPT Missed Entirely

In mammalian brains, memory consolidation happens during sleep:
- Hippocampus (episodic buffer) → replays events
- Neocortex (semantic store) → extracts stable patterns
- Low-value episodic memories are discarded
- High-value patterns become semantic memory

For AI multi-agent systems, this maps to a **background consolidation agent**:

```
CONSOLIDATION AGENT (runs periodically / on trigger)
  Input:  episodic event log (last N events)
  Output: new semantic facts promoted from episodes
  Also:   decay confidence on unreinforced semantic facts
  Also:   detect new relational edges from co-occurring entities
  Also:   recognise procedural patterns from repeated event sequences
```

This is why our Phase 5 features (`auto_capture` + `decay` + `detect_conflicts`)
were already biologically correct in direction — they just operated on one flat store
instead of the specialised architecture described here.

---

## The Value Signal Problem

How does nature decide what to keep?

The elephant doesn't keep everything — it keeps what *mattered*.
Value signal in nature = emotional intensity × repetition × survival relevance

For AI memory, the equivalent value signal:

```
memory_value = (access_count × 0.4)
             + (recency_score × 0.2)
             + (downstream_dependency_count × 0.3)
             + (explicit_importance_tag × 0.1)
```

High-value memories: rarely decayed, promoted to semantic layer
Low-value memories: decay fast, eventually dropped from episodic buffer

This is a computable metric — no LLM needed to decide what to keep.

---

## The Octopus Model — Multi-Agent Distribution

GPT missed this entirely. The octopus is the right model for multi-agent memory:

- No central brain controls the arms
- Each arm has ~2/3 of the neurons locally (distributed autonomy)
- Arms share a thin "spine" of global context
- Each arm can act independently on local memory
- Global coherence emerges from occasional sync, not central control

**AI translation for multi-agent systems:**

```
Agent A (Feature Dev)         Agent B (QA)          Agent C (Architect)
├── local episodic buffer     ├── local episodic     ├── local episodic
├── reads shared semantic     ├── reads shared sem.  ├── reads shared sem.
├── writes to shared event    ├── writes to event    ├── writes to event
└── no sync needed real-time  └── no sync needed     └── no sync needed
```

Agents do NOT share episodic memory directly.
They share the semantic layer (consolidated truths) + the raw event log.
Consolidation agent periodically reconciles.

This prevents the "too many cooks" problem where multiple agents overwrite each other's episodic context.

---

## Forgetting as a Feature

GPT framed forgetting as a problem to avoid. That's wrong.

Nature forgets deliberately to:
- Reduce interference (old wrong facts shouldn't bias new decisions)
- Enable generalisation (forget specifics, keep patterns)
- Prevent storage bloat

For AI memory systems:
- **Episodic buffer TTL**: events older than X days compress to semantic facts or drop
- **Confidence decay**: unreinforced facts lose authority (our Phase 5 feature)
- **Supersession**: new facts with same subject+predicate replace old ones (not accumulate)
- **Interference prevention**: contradicting facts should not coexist — trigger conflict resolution

**Design rule**: a memory system without forgetting is a search problem, not a memory system.

---

## Application to Multi-Agent Product (New Product Idea)

The user is considering building a separate multi-agent memory product.
The nature-inspired framework suggests this architecture:

```
┌──────────────────────────────────────────────────────────┐
│              NATURE-MEMORY MULTI-AGENT SYSTEM            │
├──────────────────────────────────────────────────────────┤
│  Elephant Layer  │  stable facts, org knowledge, config  │
│  Crow Layer      │  event log, episodic timeline          │
│  Spider Layer    │  dependency graph, entity relations    │
│  Bee Layer       │  playbooks, procedures, how-to cache   │
│  Consolidator    │  episodic → semantic promotion          │
│  Coordinator     │  query routing + value signal calc     │
└──────────────────────────────────────────────────────────┘
```

Each layer is a separate agent with its own storage + query API.
The coordinator routes incoming questions to the right layer(s).
The consolidator runs asynchronously to keep layers coherent.

---

## Application to Scope Intelligence Toolkit (Current Tool)

Current state: one flat `mempalace.jsonl` = all four memory types mixed.

Immediate improvement (no new product needed):

```
.scope-intelligence/
├── semantic.jsonl     ← stable facts ("X uses Y", "Z must never...")
├── events.jsonl       ← episodic log ("on 2025-01-10, ingest ran")
├── relations.json     ← dependency graph (module → module edges)
├── playbooks/         ← procedural memory (how Claude solved things)
└── episodes/          ← restore points (from episodic-memory skill)
```

Query routing in Python (no agent overhead):
```python
def search_memories(query, mode="auto"):
    if mode == "semantic":   return _search_semantic(query)
    if mode == "episodic":   return _search_events(query)
    if mode == "relational": return _traverse_relations(query)
    if mode == "procedural": return _match_playbook(query)
    # auto: score all four, return best match per type
    return _multi_mode_search(query)
```

This is an enhancement to Phase 5's `search_memories` — not a rewrite.

---

## Decision Gate

Build this if:
- [ ] Multiple agents will write to the same memory store
- [ ] Memory queries span different "modes" (what happened vs what is true)
- [ ] The project is long-lived and episodic context matters
- [ ] A multi-agent product is the goal (not just a toolkit)

Stay with flat mempalace if:
- [ ] Single-agent, single-developer, short project
- [ ] Query volume is low (TF-IDF on one file is fast enough)
- [ ] Team is not ready to maintain four storage contracts

---

## Skill Files Per Layer

### Human Interface Layer — Who Is Being Served

| Layer | Skill File | Nature Model | Core Question |
|---|---|---|---|
| Human alignment | `dog-companion/SKILL.md` | Dog 🐕 | Who is asking, in what state, needing what? |

This layer wraps the entire pipeline. It does not process data — it processes the human.

### Storage Layers — What Gets Remembered

| Layer | Skill File | Nature Model | Core Question |
|---|---|---|---|
| Semantic (long-term) | `elephant-memory/SKILL.md` | Elephant 🐘 | What is permanently true? |
| Episodic (timeline) | `episodic-memory/SKILL.md` | Crow/Jay 🐦‍⬛ | What happened and when? |
| Relational (graph) | `spider-memory/SKILL.md` | Spider 🕷️ | How do things connect? |
| Procedural (how-to) | `bee-memory/SKILL.md` | Honeybee 🐝 | How do I do this type of task? |
| Distribution | `octopus-memory/SKILL.md` | Octopus 🐙 | How is memory spread across agents? |
| Consolidation | `memory-consolidator/SKILL.md` | Sleep/Hippocampus | How does episodic become semantic? |

### Retrieval & Routing Layers — How Memory Is Accessed

| Layer | Skill File | Nature Model | Core Question |
|---|---|---|---|
| Threshold gate | `heron-stillness/SKILL.md` | Heron | When is the signal worth acting on? (hidden → revealed) |
| Retrieval governor | `eagle-retrieval/SKILL.md` | Eagle 🦅 | Which visible zones to search? (visible → selected) |
| Path optimisation | `ant-trails/SKILL.md` | Ant 🐜 | Which paths have worked before? |
| Parallel swarm search | `bee-memory/SKILL.md` | Honeybee 🐝 | Run workers in parallel, consensus aggregates |
| Message routing | `pigeon-routing/SKILL.md` | Pigeon 🕊️ | How do messages reach the right agent? |

### Processing Layers — What Happens to Information

| Layer | Skill File | Nature Model | Core Question |
|---|---|---|---|
| Sequential inference | `crow-inference/SKILL.md` | Crow 🐦‍⬛ | When retrieval fails, reason to construct the answer |
| Purity / refinement | `swan-purity/SKILL.md` | Swan 🦢 | Remove noise, duplicates, stale, low-authority entries |
| Experimental probe | `mouse-explorer/SKILL.md` | Mouse 🐭 | Discover new knowledge through direct experiment |

### The Full Pipeline

```
Query arrives
  → Heron gate: is the signal strong enough to act? (WHEN to act)
  → Eagle layer: which memory zones to open? (WHERE to look, from visible context)
  → Ant layer: is there a known path for this query type? (pre-stage results)
  → Bee layer: parallel worker swarm across selected zones (HOW to search)
  → Crow layer: if gaps remain, infer sequentially (WHAT to construct)
  → Swan layer: purify results before delivery (HOW to clean)
  → Answer delivered

Ingest arrives
  → Swan write-time: clean before storing
  → Ant workers: stateless relay pipeline (chunk → classify → route → write)
  → Pigeon routing: multi-signal fusion to find correct destination zone
  → Storage layers: elephant / episodic / spider / bee-playbooks updated
  → Crow pending inferences: trigger any waiting on this new information
  → Mouse probes: validate new content matches expected behavior
```
