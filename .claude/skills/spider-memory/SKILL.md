---
name: spider-memory
description: >
  The Spider Layer — relational/graph memory for AI systems.
  Knows how entities connect, what depends on what, and which components
  form clusters. The spider doesn't remember events — it knows the web's
  current structure.
status: candidate
relates_to: nature-memory-framework, elephant-memory, scope-intelligence-toolkit
---

## What the Spider Actually Does

A spider web is not a static structure — it is a live sensor network:
- Each thread transmits vibration with different frequency depending on position
- Spider knows exactly which location in the web was hit (directional memory)
- Web encodes topology — the spider navigates by structure, not by landmarks
- Spider repairs damaged sections while preserving overall topology
- Different web architectures for different prey/environments — the structure is a strategy

**The key insight:** The spider's "memory" is the web itself.
Structure IS knowledge. Relationships ARE the data.

---

## What Relational Memory Is (and Is Not)

### IS:
- "auth-module depends on user-module" (dependency edge)
- "Sprint 3 owns features: F1, F2, F7" (ownership cluster)
- "File A is referenced by files B, C, D" (reference graph)
- "Concept X is similar to concept Y" (semantic proximity edge)
- "Component Z is downstream of engine" (data flow edge)

### IS NOT:
- "auth-module uses JWT" (→ semantic / elephant layer)
- "On 2025-01-10, auth was refactored" (→ episodic layer)
- "When auth fails, do X" (→ procedural / bee layer)

The relational layer stores **topology**, not content.

---

## Storage Design

### Graph as adjacency list (simple, zero deps)
```json
{
  "nodes": {
    "auth-module":    {"type": "module", "phase": 2, "owner": "backend-team"},
    "user-module":    {"type": "module", "phase": 1, "owner": "backend-team"},
    "engine":         {"type": "module", "phase": 3, "owner": "core-team"},
    "jwt-library":    {"type": "library", "external": true},
    "feature/login":  {"type": "feature", "status": "stable"}
  },
  "edges": [
    {"from": "auth-module",   "to": "user-module",  "type": "depends-on",   "weight": 0.9},
    {"from": "auth-module",   "to": "jwt-library",  "type": "uses",          "weight": 1.0},
    {"from": "engine",        "to": "auth-module",  "type": "calls",         "weight": 0.7},
    {"from": "feature/login", "to": "auth-module",  "type": "implemented-by","weight": 1.0}
  ]
}
```

Edge types:
- `depends-on` — runtime dependency
- `calls` — direct function/API call
- `uses` — uses a library or external service
- `implemented-by` — feature → module mapping
- `similar-to` — semantic proximity (auto-detected)
- `conflicts-with` — detected incompatibility

---

## Query Interface

```python
# What does auth-module depend on?
spider.outgoing("auth-module", type="depends-on")
# → [user-module, jwt-library]

# What depends on auth-module? (blast radius)
spider.incoming("auth-module")
# → [engine, feature/login, feature/registration]

# Full blast radius (transitive)
spider.blast_radius("user-module", depth=3)
# → auth-module (d=1) → engine (d=2), feature/login (d=2) → api-gateway (d=3)

# Find clusters (what components form a subsystem?)
spider.cluster("auth-module", max_distance=2)

# Orphaned nodes (nothing connects to them)
spider.orphans()

# Critical nodes (many things depend on them — high risk to change)
spider.critical_nodes(min_incoming=3)
```

---

## How the Spider Layer Updates

Unlike semantic memory (slow, deliberate), the relational layer is **structural**.
It updates when code structure changes, not when facts are confirmed.

Update triggers:
- `doc ingest` → extract component relationships from architecture section
- `git auto-capture` → detect new imports, new file dependencies
- Manual: `scope rel add auth-module depends-on redis`
- Code scan: parse import statements → build edges automatically

Repair (like a spider repairs its web):
- If a node is removed → remove all its edges
- If an edge source/target is renamed → migrate edge to new name
- If two nodes are merged → merge their edge sets

---

## Application to Scope Intelligence Toolkit

Currently `curated/module-map.md` is prose — a spider layer would replace it:

```
# module-map.md (current — hard to query)
The auth module uses JWT library and depends on the user module.
The engine calls auth for every request.
```

```json
// relations.json (spider layer — queryable)
edges: [
  {from: "auth", to: "user-module", type: "depends-on"},
  {from: "auth", to: "jwt",        type: "uses"},
  {from: "engine", to: "auth",      type: "calls"}
]
```

This enables impact analysis:
```
> scope rel blast-radius user-module
→ auth depends on it
→ engine calls auth (indirect)
→ feature/login uses engine (indirect, 2 hops)
→ 3 components at risk if user-module changes
```

Which is exactly what the `impact-analysis` skill does — but currently it reads prose markdown.
The spider layer makes that query instant and computable.

---

## Application to Multi-Agent Product

In a multi-agent system, the spider layer answers:
- "Which agents are responsible for components that touch X?" → routing
- "If agent A changes module M, which other agents' domains are affected?" → broadcast
- "Which agent owns this component?" → ownership graph

The coordinator agent uses the spider layer to route questions:
```
User asks: "What will break if I change the payment module?"
Coordinator → spider.blast_radius("payment-module")
→ identifies: checkout-agent, notification-agent are affected
→ routes query to those agents for their perspective
```

---

## Implementation Estimate

| Component | Effort |
|---|---|
| Graph data model (nodes + edges JSON) | 1h |
| CRUD operations + edge traversal | 3h |
| Blast radius + cluster algorithms | 2h |
| Auto-build from doc ingest / git scan | 3h |
| CLI: `scope rel add/query/blast-radius` | 2h |
| Replace module-map.md with queryable graph | 2h |
| Tests | 2h |
| **Total** | **~15h** |
