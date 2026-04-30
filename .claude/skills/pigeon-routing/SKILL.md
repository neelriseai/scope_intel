---
name: pigeon-routing
description: >
  The Pigeon Layer — multi-modal navigation, resilient message routing, and
  home-state anchoring for multi-agent AI systems. Don't retrieve data.
  Navigate to it. Each agent has a home context. Messages carry path metadata.
  Multiple independent signals fuse into a routing decision. If one signal fails,
  others carry it home.
  Philosophy: redundant multi-signal sensor fusion for reliable navigation
  under uncertainty and disruption.
status: candidate
relates_to: nature-memory-framework, octopus-memory, bee-memory, ant-trails, scope-intelligence-toolkit
---

## The Philosophy — A Messenger Who Never Forgets the Route

The pigeon's role is simple and ancient: **carry the message, remember the route, always deliver.**

What makes the pigeon unique among all animals in this framework is not just that it navigates — it's that **it never forgets**. A pigeon that has flown London → Paris once will remember that exact route for the rest of its life — 10 to 15 years. The route does not decay. It does not need reinforcement. It does not evaporate if unused for a year.

This is the critical distinction from the ant:
```
Ant trail:       pheromone evaporates if unused → route forgotten
Pigeon route:    remembered permanently after first successful flight → never forgotten
```

Ants optimise routes through forgetting. Pigeons preserve routes through permanent memory.

Both are right for different things:
- Use ant trails for **retrieval paths** (what was useful recently — volatile, should decay)
- Use pigeon routes for **communication routes** (how agents reach each other — structural, should persist)

**The pigeon is a reliable long-memory message carrier.**
Once it knows a route, the message always gets through.
The route knowledge outlives any individual session, any system restart, any gap in usage.

This changes how you design agent-to-agent communication:
- Not "send to this address" (fragile — address can change)
- Not "find dynamically every time" (expensive — re-navigates from scratch each time)
- But: **remember this route permanently, use it reliably every time**

---

## What Pigeons Actually Do — Five Independent Navigation Systems

This is the most important fact: pigeons don't rely on one signal. They combine **five independent systems** through sensor fusion. Remove any one — they still navigate. This redundancy is the design, not the accident.

### System 1 — Magnetic Field Sensing
Magnetite crystals in the beak + magnetically-sensitive hair cells in the inner ear.
The pigeon has a literal geomagnetic map of the earth encoded in its body.
It knows its magnetic latitude/longitude relative to home at all times.
Accuracy: ~tens of km. Reliable in all weather, day or night.

### System 2 — Sun Compass (Time-Compensated)
The sun moves 15° per hour. The pigeon's internal clock compensates automatically.
At 2pm, the sun is not south — the pigeon knows exactly where south is anyway.
Accuracy: ~high directional precision. Fails: at night, in overcast.

### System 3 — Visual Landmarks
Rivers, coastlines, highways, mountain ranges, urban silhouettes.
Learned over repeated trips. Each pigeon develops its own landmark set —
personal, not species-wide. Two pigeons from the same loft may navigate by
different landmarks on the same route.
Accuracy: very high near home. Fails: released far from familiar territory.

### System 4 — Olfactory Map (Smell Gradients)
Controversial but well-supported: pigeons detect smell gradients carried on wind
from distant geographic features. Mountains, coastlines, cities, forests —
all have characteristic chemical signatures. The pigeon builds an olfactory
position map over time.
Accuracy: coarse global positioning. Fails: still air, heavy rain.

### System 5 — Infrasound (Acoustic Landscape)
Pigeons detect infrasound (0.1–10Hz) from mountains, oceans, cities —
features that produce distinctive low-frequency acoustic signatures.
Detectable from hundreds of km away. Used for global coarse positioning.
Accuracy: coarse. Fails: acoustically flat environments.

### The Fusion Mechanism
The pigeon doesn't pick one signal. It runs all five and weights them by current reliability:
```
position_estimate = weighted_sum([
    magnetic_signal    × reliability(magnetic),
    sun_signal         × reliability(sun, time_of_day, cloud_cover),
    visual_landmarks   × reliability(visual, familiarity_with_area),
    olfactory_gradient × reliability(olfactory, wind_conditions),
    infrasound_map     × reliability(infrasound, terrain_type)
])
```
Cloudy day: sun_weight drops, magnetic_weight rises.
Unfamiliar territory: visual_weight drops, magnetic_weight rises.
The system is self-compensating. Signal degradation is handled automatically.

---

## Home-State Anchoring — Home Is Not an Address

The pigeon's "home" is not a GPS coordinate. It is a **multi-sensory composite signature**:
- The magnetic field strength and direction at the loft location
- The smell profile of the local environment
- The visual panorama (what the loft looks like from the air)
- The infrasound pattern of the home region
- The sun angle at home at various times of day

The pigeon navigates toward the convergence of all these signals.
When they all point the same direction — that is home.

**For AI agents, home is not a server address or an API endpoint.**
Home is the agent's **context state**:
- Its current task definition
- Its active memory state (which facts it holds)
- Its available tools
- Its permission scope
- Its identity

A message routes to an agent not by address, but by finding the agent
whose home state matches the message's destination context signature.

---

## AI Translation — The Pigeon Routing Engine

### Core Architecture

```
Message origin (Agent A)
    │
    ├── builds message:
    │     {payload, destination_context, path_metadata, fallback_signals}
    │
    └── releases message into routing layer
              │
    ┌─────────▼──────────────────────────────────────────────┐
    │           PIGEON ROUTING ENGINE                         │
    │                                                         │
    │  Signal 1: content type match                           │
    │  Signal 2: entity match (who is this about?)           │
    │  Signal 3: structural position (overview vs detail)     │
    │  Signal 4: authority source match                       │
    │  Signal 5: cross-reference pattern                      │
    │                                                         │
    │  → weighted sensor fusion → destination agent/zone      │
    │  → if primary route fails → fallback route              │
    │  → delivery confirmed → path reinforced (ant trail)     │
    └────────────────────────────────────────────────────────┘
              │
    ┌─────────▼──────────┐
    │  Destination Agent B│
    │  (home context      │
    │   matched)          │
    └────────────────────┘
```

### Message Structure — Carries Its Own Path Metadata

```json
{
  "id": "msg_041",
  "payload": "auth module now uses OAuth 2.0",
  "origin": {
    "agent_id": "doc-ingest-agent",
    "session": "ep_023",
    "timestamp": "2025-04-30T09:15:00Z"
  },
  "destination_context": {
    "target_memory_zone": "semantic/auth",
    "entity_tags": ["auth", "OAuth", "security"],
    "authority_level": 8,
    "content_type": "fact"
  },
  "path_metadata": {
    "checkpoints_passed": ["doc-reader", "chunker", "classifier"],
    "routing_signals": {
      "heading_match": 0.9,
      "entity_match": 0.85,
      "structural_position": 0.7,
      "authority_match": 1.0,
      "cross_reference": 0.3
    },
    "current_confidence": 0.87
  },
  "fallback_routes": [
    "semantic/security",
    "episodic/recent"
  ],
  "delivery_required": true
}
```

The message carries exactly how it was routed and how confident each signal was.
If it arrives at the wrong destination, the path_metadata reveals where the routing went wrong.

---

## Multi-Modal Routing for Doc Ingest

This directly upgrades the current keyword-pattern routing in doc_ingestor.py.

**Current (single-signal):**
```python
if "auth" in title.lower():
    route_to = "003-auth-module.md"
```

**Pigeon (multi-signal fusion):**
```python
def pigeon_route(section: DocSection) -> RouteDecision:
    signals = {
        # Signal 1: heading keyword match
        "heading_match": keyword_score(section.title, ROUTE_PATTERNS),

        # Signal 2: entity presence in body text
        "entity_match": entity_overlap(section.body, known_entities),

        # Signal 3: structural position in document
        "structural": position_score(section.index, section.total_sections),

        # Signal 4: writing style (imperative=constraint, descriptive=architecture)
        "style": classify_writing_style(section.body),

        # Signal 5: cross-references to other sections
        "cross_ref": cross_reference_signal(section.body, all_sections)
    }

    # Dynamic weighting based on signal reliability
    weights = {
        "heading_match":  0.4 if signals["heading_match"] > 0.5 else 0.1,
        "entity_match":   0.3,
        "structural":     0.1,
        "style":          0.1,
        "cross_ref":      0.1 if signals["cross_ref"] > 0 else 0.0
    }

    composite_score = {
        target: sum(signals[sig] * weights[sig] * ROUTE_SIGNALS[target][sig]
                    for sig in signals)
        for target in ROUTE_TARGETS
    }

    primary = max(composite_score, key=composite_score.get)
    confidence = composite_score[primary]

    if confidence < 0.5:
        # Ambiguous — use fallback route or flag for review
        return RouteDecision(primary, confidence, fallback=FALLBACK_ROUTES[primary])

    return RouteDecision(primary, confidence)
```

If the heading says "Memory" but the body only mentions "Redis" and "cache" (entities suggesting infrastructure), and the structural position is late in the document (suggesting implementation detail), and the writing style is descriptive — all five signals together give a much more accurate routing decision than the heading alone.

---

## Agent-to-Agent Communication (Multi-Agent Product)

**Problem today:**
```
Agent A → sends message → Agent B (hardcoded address)
Agent B is offline → message lost
Agent B moved to new instance → message lost
No delivery confirmation → unknown state
```

**Pigeon solution:**
```
Agent A → releases message with destination_context (not address)
        → routing engine uses multi-signal fusion to find Agent B's home state
        → if Agent B is offline: message queued, navigation resumes when B returns
        → if Agent B moved: routing re-navigates to new home location
        → delivery confirmed → receipt sent back → path reinforced
        → if all routes fail: message held at last checkpoint, retry on schedule
```

This is guaranteed delivery without hardcoded addresses.
The message finds the agent. The agent doesn't need to expose a fixed address.

---

## Permanent Route Memory — The Route Registry

Unlike ant trails (which decay), pigeon routes are stored permanently:

```jsonl
// pigeon_routes.jsonl — permanent route registry, never decays
{"id": "route_001", "from": "doc-ingest-agent", "to": "semantic/auth", "first_flown": "2025-01-10", "times_used": 47, "last_used": "2025-04-28", "reliability": 0.98, "signals": {"heading_match": 0.9, "entity_match": 0.85}}
{"id": "route_002", "from": "agent-A", "to": "agent-B/memory-zone", "first_flown": "2025-02-01", "times_used": 12, "last_used": "2025-03-15", "reliability": 0.92}
{"id": "route_003", "from": "qa-agent", "to": "constraints/security", "first_flown": "2025-01-20", "times_used": 3, "last_used": "2025-01-25", "reliability": 1.0}
```

Note: `last_used` 3 months ago on route_003 — but the route is still valid. Still in the registry. The pigeon remembers.

**The route registry is the system's permanent institutional memory of how to reach things.**
It grows over time. It never shrinks. It is the most stable layer in the entire framework.

When a new agent starts: it inherits the full route registry immediately.
It doesn't need to rediscover routes that prior agents already flew.
The institutional route knowledge transfers automatically.

---

## Ant Trail vs Pigeon Route — When to Use Each

| | Ant Trail | Pigeon Route |
|---|---|---|
| **What it stores** | Which documents to retrieve for a query type | How to route messages between agents/zones |
| **Decay** | Yes — evaporates if unused | No — permanent after first successful flight |
| **Purpose** | Optimise RETRIEVAL (what to read) | Optimise ROUTING (where to send) |
| **Volatile?** | Yes — retrieval relevance changes as code changes | No — structural routes are stable |
| **Example** | "For auth bugs, check logs → config → constraints" | "Messages about auth always route to semantic/auth zone" |
| **Scope** | Within one query session | Across all sessions, all agents, forever |

Both exist in the system. They serve complementary roles. Neither replaces the other.

---

## The Vector Map vs Route Map — Maturity Progression

**Early system (route map — young pigeon):**
Follows specific learned paths. "To reach semantic/auth: go through doc-reader → classifier → auth-router."
Works well for known routes. Fails on novel paths.

**Mature system (vector map — experienced pigeon):**
Develops abstract navigation. "I need to reach any security-related memory zone, and I know the direction from here."
Works for novel routes by extrapolating from principles.

For scope-intel, this maps to the ant trail progression:
- Phase 1: specific trail (always go ticket → log → config → deploy for production issues)
- Phase 2: abstract navigation (for any production issue, navigate toward recent-changes + constraints + logs)

The pigeon routing engine matures from route-following to vector navigation the same way the ant trail system matures from specific paths to generalised patterns.

---

## The Loft — Home Context as the System Anchor

Each agent in a multi-agent system has a **loft** — its stable home context.
Messages always return to their loft on delivery. The loft never moves.

```python
class AgentLoft:
    """The stable home context of an agent. Messages navigate toward this."""
    agent_id: str
    memory_scope: list[str]           # which memory zones this agent owns
    task_definition: str              # what this agent does
    entity_domain: list[str]          # which entities this agent handles
    authority_level: int              # what sources it accepts
    olfactory_signature: dict         # multi-dimensional identity fingerprint

    def matches(self, destination_context: dict) -> float:
        """How well does an incoming message's destination match this loft?"""
        return weighted_signal_match(self.olfactory_signature, destination_context)
```

The "olfactory signature" (borrowing the pigeon's smell map metaphor) is the
agent's multi-dimensional identity — the composite of all the signals that
make this agent the right destination for specific messages.

---

## Resilience Properties

| Failure Mode | Pigeon Response |
|---|---|
| Destination agent offline | Message held at last checkpoint, retry when signal detected |
| Primary route blocked | Fallback routes activated automatically |
| One navigation signal fails | Other signals carry increased weight |
| Message corrupted in transit | Path metadata allows reconstruction from last clean checkpoint |
| Destination agent moved | Re-navigate using home-state signature, not old address |
| Network partition | Messages queue locally, deliver on reconnect |

Compare to standard HTTP request:
- Network error → 500, message lost
- Endpoint moved → 404, message lost
- No delivery confirmation → unknown

The pigeon design is orders of magnitude more resilient for long-running multi-agent systems.

---

## Application to Scope Intelligence Toolkit — Immediate Value

Even in the current single-agent toolkit, pigeon routing improves doc ingest:

**Before (keyword route — single signal):**
A section titled "Caching Strategy" → no keyword match → lands in default bucket

**After (pigeon route — multi-signal):**
"Caching Strategy":
- heading_match: 0.3 (no direct pattern)
- entity_match: 0.8 (Redis, TTL, session — memory-layer entities)
- structural: 0.6 (middle of doc = implementation detail)
- style: 0.7 (descriptive, technical)
- cross_ref: 0.9 (references Memory Layer section explicitly)

→ composite routes to: 005-memory-layer.md with confidence 0.76
→ correct destination despite no heading keyword match

This is why the current doc ingest misses sections — single-signal routing
fails on anything with an ambiguous or indirect title.

---

## How Pigeon Connects to Other Layers

```
Ant trails:     learn which pigeon routes succeed → reinforce them
Eagle:          identifies destination zone → pigeon navigates within zone
Bee workers:    each worker is like a pigeon carrying one type of message
Crow:           when pigeon arrives with incomplete message → crow infers the gaps
Swan:           cleans message content before routing begins (write-time purity)
Octopus:        pigeon is the inter-arm communication protocol for octopus agents
```

The pigeon is the **nervous system** connecting all the other animals.
Without it, layers exist in isolation. With it, they communicate reliably.

---

## Implementation Estimate

| Component | Effort |
|---|---|
| Multi-signal router (5 signals + weights) | 4h |
| Dynamic weight calibration (reliability-based) | 2h |
| Message schema with path metadata | 2h |
| Fallback route definition per destination | 2h |
| Home-state / loft model per agent | 3h |
| Delivery confirmation + path reinforcement (→ ant) | 2h |
| Doc ingest upgrade: keyword → pigeon routing | 3h |
| Agent-to-agent message queue (offline resilience) | 4h |
| CLI: `scope route show` (visualise routing decisions) | 2h |
| Tests | 4h |
| **Total** | **~28h** |
