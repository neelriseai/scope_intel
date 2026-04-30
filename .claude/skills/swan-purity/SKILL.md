---
name: swan-purity
description: >
  The Swan Layer — purity, discernment, and refinement of AI memory and retrieval.
  Operates after retrieval, before delivery. Deduplicates, removes stale entries,
  separates fact from opinion, ranks by source authority, and reduces noise.
  Philosophy: Hamsa Viveka — the ability to separate milk from water even when mixed.
  Most data problems are purity problems, not missing-data problems.
status: candidate
relates_to: nature-memory-framework, elephant-memory, eagle-retrieval, crow-inference, scope-intelligence-toolkit
---

## The Philosophy — Hamsa Viveka (The Discernment of the Swan)

In Hindu philosophy (Advaita Vedanta), the swan (Hamsa) possesses **Neeraksheeraviveka** —
the mythological ability to separate milk from water even when the two are perfectly mixed.
No other creature can do this. The swan drinks only the milk and leaves the water behind.

The Hamsa is the vehicle of Brahma (creation) and Saraswati (knowledge/wisdom).
Its power is not strength or speed — it is **viveka: pure discrimination and discernment.**
The ability to extract essence from mixture. To see clearly what is true when truth is diluted by noise.

In Western mythology, the swan is associated with grace, purity (white), and transformation.
The "swan song" — the most beautiful song sung just before death — represents final clarity,
the purest expression of a thing before it passes.

**For AI memory systems:**
The swan does not gather information. It does not search, infer, or route.
It takes what has been gathered and makes it **pure before it is used.**

Most AI memory problems are not "the data doesn't exist."
They are "the right data is buried in a mixture of duplicates, stale entries,
opinions stated as facts, and low-authority noise."

**The swan separates the milk from the water.**

---

## The Key Insight — Most Warehouse Problems Are Purity Problems

The user identified something data engineers spend years learning:

```
❌ What engineers assume: "We have bad data because data is missing."
✅ What's actually true:  "We have bad answers because right data
                           is mixed with wrong/stale/duplicate/opinion data."
```

Common purity failures in AI memory:
- **Duplicate entries**: "auth uses JWT" stored 7 times with slightly different wording → 7 results returned, all saying the same thing
- **Stale facts not removed**: old fact "auth uses sessions" still in memory after switch to JWT → retrieval returns conflicting answers
- **Opinion as fact**: "auth *should probably* use OAuth" captured as a fact, not as a suggestion
- **Authority confusion**: a casual Slack message carries same weight as the formal spec document → unranked noise
- **Superseded entries not archived**: old version of a constraint coexists with new version
- **Inference presented as certainty**: crow built an answer with 0.7 confidence, stored as 1.0 fact

The swan's job: clean all of this before the answer leaves the system.

---

## Where Swan Sits in the Pipeline

```
Query → Eagle (filter) → Ant (trail?) → Bee (search) → Crow (infer if needed)
                                                               │
                                                    ┌──────────▼──────────┐
                                                    │    🦢 SWAN LAYER     │
                                                    │  Purify before return│
                                                    └──────────┬──────────┘
                                                               │
                                                         Final answer
```

Eagle filters BEFORE retrieval (attention gating — what not to look at).
Swan filters AFTER retrieval (purity pass — what not to return).

These are categorically different operations on opposite ends of the pipeline.

---

## Swan Operates in Two Modes

### Mode 1 — Write-Time Purity (at ingest/capture)
Run swan checks when new information enters any memory layer:
```
New fact arrives → Swan checks:
  Is this a duplicate?
  Is this opinion or fact?
  What authority level is the source?
  Does this contradict something with higher authority?
→ Store clean, or reject with reason, or store with authority tag
```

### Mode 2 — Read-Time Purity (before returning results)
Run swan pass on retrieved results before they reach the user/agent:
```
Retrieval returns 20 candidates → Swan refines:
  Remove duplicates (keep highest authority version)
  Remove stale entries (superseded, decayed below threshold)
  Separate facts from opinions (tag clearly)
  Rank by authority (spec > doc > code > commit > inference)
  Remove self-contradictions (flag or arbitrate)
→ Return 5 clean, ranked, labelled results
```

---

## The Five Purity Operations

### 1. Deduplication — One Truth, Not Seven Echoes

```python
def deduplicate(entries: list[MemoryEntry]) -> list[MemoryEntry]:
    """Collapse near-identical entries. Keep the most authoritative version."""
    clusters = cluster_by_semantic_similarity(entries, threshold=0.85)
    result = []
    for cluster in clusters:
        # Among near-duplicates, keep the highest authority version
        canonical = max(cluster, key=lambda e: AUTHORITY_RANK[e.source_type])
        canonical.reinforcement_count = sum(e.reinforcement_count for e in cluster)
        result.append(canonical)
    return result
```

Seven entries saying "auth uses JWT" become one entry with `reinforcement_count=7`.
The others are absorbed — their reinforcement is credited to the canonical entry.
Not deleted — *merged*. The information is preserved, the noise is removed.

### 2. Staleness Removal — The Past Should Not Speak as the Present

```python
def remove_stale(entries: list[MemoryEntry], now: datetime) -> list[MemoryEntry]:
    """Remove superseded facts and entries below confidence floor."""
    clean = []
    for entry in entries:
        if entry.status == "superseded":
            # Don't return. It lived — now it's the swan song.
            # Archive to episodic (its final form preserved) but don't surface it.
            archive_as_swan_song(entry)
            continue
        age_days = (now - entry.last_reinforced).days
        effective_confidence = entry.confidence * math.exp(-age_days / entry.decay_rate)
        if effective_confidence < 0.2:
            continue  # too stale to trust
        entry.effective_confidence = effective_confidence
        clean.append(entry)
    return clean
```

**The swan song:** when a fact is superseded or decayed below threshold, before removal
it is archived to the episodic layer with a `swan_song: true` flag — its final recorded form.
History is never destroyed. It is simply moved from the present to the past.

### 3. Fact vs Opinion Separation — Milk from Water

```python
OPINION_SIGNALS = [
    r"\bshould\b", r"\bprobably\b", r"\bmight\b", r"\bconsider\b",
    r"\bideally\b", r"\bthink\b", r"\bmaybe\b", r"\bwould be better\b",
    r"\bprefer\b", r"\bseem[s]?\b", r"\bappear[s]?\b"
]
FACT_PREDICATES = ["uses", "is", "must", "must-not", "contains", "returns", "requires"]

def classify_entry(entry: MemoryEntry) -> str:
    text = f"{entry.predicate} {entry.object}"
    if any(re.search(sig, text, re.I) for sig in OPINION_SIGNALS):
        return "opinion"
    if entry.predicate in FACT_PREDICATES:
        return "fact"
    return "uncertain"
```

Facts and opinions are returned with different labels:
```
[FACT]    auth-module uses JWT            (conf: 0.95, source: spec-doc)
[OPINION] auth should probably use OAuth  (conf: 0.6,  source: chat-capture)
[FACT]    JWT tokens must include expiry  (conf: 1.0,  source: constraints-doc)
```

The user/agent can decide how to weight them. The swan doesn't suppress opinions —
it **labels them clearly** so they're not mistaken for facts.

### 4. Authority Ranking — Not All Sources Are Equal

```python
AUTHORITY_RANK = {
    "formal-spec":       10,  # API contracts, formal requirements
    "constraints-doc":   10,  # curated/constraints.md
    "design-doc":         8,  # .ai-context/generated/*.md from doc ingest
    "code":               7,  # extracted from actual source code
    "git-commit":         5,  # commit messages (explicit)
    "auto-capture":       4,  # auto-captured from git (inferred)
    "session-capture":    3,  # captured from chat/session
    "crow-inference":     2,  # constructed by inference, not stated explicitly
    "speculation":        1,  # low-confidence inference or casual mention
}

def rank_by_authority(entries: list[MemoryEntry]) -> list[MemoryEntry]:
    return sorted(entries,
                  key=lambda e: (AUTHORITY_RANK.get(e.source_type, 0),
                                 e.effective_confidence),
                  reverse=True)
```

A constraint from `constraints-doc` (authority=10) outranks an inferred fact
from the crow agent (authority=2) even if the crow's confidence is higher.
**Source authority is orthogonal to confidence.**

### 5. Contradiction Arbitration — When Two Facts Conflict

```python
def arbitrate_contradictions(entries: list[MemoryEntry]) -> list[MemoryEntry]:
    """When two entries have same subject+predicate but different object, arbitrate."""
    seen = {}
    arbitrated = []
    for entry in entries:  # already sorted by authority
        key = f"{entry.subject}:{entry.predicate}"
        if key in seen:
            existing = seen[key]
            # Flag the contradiction — don't silently drop either
            entry.note = f"CONTRADICTS: {existing.id} (lower authority — may be outdated)"
            existing.note = f"SUPERSEDES: {entry.id} (higher authority)"
            arbitrated.append(entry)  # include both, labelled
        else:
            seen[key] = entry
            arbitrated.append(entry)
    return arbitrated
```

The swan does not silently discard contradictions — it labels them.
The user/agent sees both sides and can make an informed decision.
Unlabelled contradictions are the most dangerous form of data corruption.

---

## The Swan Song — Preserving What Is Superseded

When the swan removes a fact from the active present, it preserves its last form:

```python
def archive_as_swan_song(entry: MemoryEntry):
    """The fact's final, most beautiful form — preserved before it fades."""
    swan_song = {
        "original_id":     entry.id,
        "subject":         entry.subject,
        "predicate":       entry.predicate,
        "object":          entry.object,
        "final_confidence":entry.confidence,
        "reason_archived": entry.supersession_reason or "confidence_decay",
        "archived_at":     now(),
        "swan_song":       True,
        "note": "This fact was once true. It is preserved here as historical record."
    }
    append_to_episodic(swan_song)
```

The episodic layer becomes the archive of swan songs — facts that were once
authoritative but are now past. The crow can query them when reasoning about
"what was once believed" vs "what is now true."

---

## Application to Scope Intelligence Toolkit

### During Doc Ingest — Write-Time Swan Pass

Before writing any extracted fact to semantic memory:

```
Doc section extracted → LLM classifies → Swan checks:
  Is "auth should use JWT" → opinion (should) → tag as opinion, lower authority
  Is "auth MUST use JWT" → fact (must) → tag as fact, constraints authority
  Is this already in semantic? → if yes, merge/reinforce don't duplicate
  Is source a spec doc? → authority=10. Is source auto-captured? → authority=4
```

This prevents the most common doc ingest failure: capturing opinion sentences
("we might consider using Redis") as facts ("memory-layer uses Redis").

### During Memory Search — Read-Time Swan Pass

```bash
scope mem search "what does the auth module use?" --pure
```

```
Raw retrieval (Bee returns):
  "auth uses JWT"              (conf: 0.9,  source: design-doc)
  "auth uses JWT"              (conf: 0.8,  source: git-commit)      ← duplicate
  "auth uses JWT"              (conf: 0.7,  source: session-capture) ← duplicate
  "auth should use OAuth"      (conf: 0.5,  source: chat-capture)    ← opinion
  "auth used sessions"         (conf: 0.3,  source: superseded-fact) ← stale

Swan pass:
  Dedup:     3 JWT entries → 1 entry (reinforcement_count=3, keep design-doc version)
  Authority: design-doc (8) > chat-capture (3) → JWT ranked above OAuth suggestion
  Staleness: sessions entry at 0.3 effective confidence → swan song → removed
  Labels:    "auth should use OAuth" tagged as [OPINION]

Clean output:
  [FACT]    auth-module uses JWT           (conf: 0.9, reinforced: 3×, source: design-doc)
  [OPINION] auth should use OAuth          (conf: 0.5, source: chat-capture)
```

2 results instead of 5. Clean. Labelled. Ranked by authority.

---

## The Authority Chain for Scope Intelligence

For scope-intel specifically, the authority chain is:

```
10  curated/constraints.md          — absolute rules, never overridden
10  .scope-intelligence/features.json  — formal feature registry
 8  .ai-context/generated/*.md      — doc ingest output (from formal docs)
 7  curated/module-map.md           — structural ground truth
 6  source code (imports, types)    — what the system actually does
 5  git commits (explicit messages) — intentional decisions recorded
 4  auto-capture (git keywords)     — inferred from commit patterns
 3  session-capture (mempalace)     — captured from Claude sessions
 2  crow-inference                  — constructed answer
 1  casual mentions, comments       — speculative/informal
```

Facts from higher in the chain always surface first.
Facts from lower in the chain are not discarded — they are demoted and labelled.

---

## Swan vs Eagle — The Distinction

Both filter. Neither searches. But they are opposite ends of the pipeline:

| | Eagle | Swan |
|---|---|---|
| **When** | Before retrieval starts | After retrieval completes |
| **What** | Decides what zones to search | Cleans what was found |
| **Method** | Intent classification, zone selection, suppression | Dedup, staleness, fact/opinion, authority ranking |
| **Removes** | Irrelevant search zones | Impure results within found zones |
| **Analogy** | "Don't look in those rooms" | "Of what you found, show only the clean items" |

A system needs both. Eagle prevents wasted search. Swan prevents dirty answers.

---

## Implementation Estimate

| Component | Effort |
|---|---|
| Deduplication (semantic similarity clustering) | 3h |
| Staleness removal + confidence decay calculation | 1h |
| Fact vs opinion classifier (regex + predicate rules) | 2h |
| Authority ranking schema + source tagging | 2h |
| Contradiction arbitration + labelling | 2h |
| Swan song archival to episodic | 1h |
| Write-time swan (doc ingest integration) | 2h |
| Read-time swan (search result refinement) | 2h |
| CLI: `scope mem search --pure` flag | 1h |
| Tests | 3h |
| **Total** | **~19h** |

---

## Decision Gate

Build the swan layer if:
- [ ] Memory has grown large enough that duplicates accumulate (>500 entries)
- [ ] Doc ingest is capturing opinions as facts (common problem)
- [ ] Multiple source types exist with different reliability (spec vs chat vs commits)
- [ ] Search results feel noisy even after eagle filtering
- [ ] "Why does it return conflicting answers?" is a recurring complaint
- [ ] A data warehouse/knowledge base is being built (purity problems dominate at scale)

Swan is always worth building early:
- [ ] Write-time purity is cheapest — clean at entry, not at query
- [ ] Authority tagging requires no LLM — pure code-side logic
- [ ] Deduplication pays for itself on the first large doc ingest
