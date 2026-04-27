# Roadmap

## Phase 1: MVP
- Build CLI + per-repo `.scope-intelligence`.
- Deliverables:
  - CLAUDE.md
  - 3 feature maps
  - Retrieval + updater scripts
  - Debug + impact-analysis skills
  - Post-edit hook

## Phase 2: Enhanced Scope
- Add symbol index.
- Add impacted tests + dependency graphs.
- Async hook refresh.
- Expand skills (`/impact-analysis`).

## Phase 3: Subagents + MCP
- Introduce custom subagent for scope analysis.
- Add MCP service wrapper.
- Runtime traces + stack-trace narrowing.
- PR-aware scope deltas.

## Phase 4: Long-Term Memory ✓
- MemPalace with four memory types: semantic, procedure, episodic, structural.
- Semantic: timeless facts with confidence scores — never aged by recency.
- Procedure: ordered step-by-step workflows per repo.
- Episodic: bugs, decisions, failures, fixes — newest first.
- Structural: live slice from Phase 1-3 index injected on every fetch.
- Layered fetch: structural → semantic → procedural → episodic.
- Git churn analysis cross-referenced with feature map.
- MCP tools: mem_add, mem_fetch, mem_list, mem_churn.

## Phase 5: Cross-Repo Intelligence + Auto-Learning
- Cross-repo memory: share semantic facts and procedures across multiple repos.
- Auto-episodic capture: hook into git commits/PR merges to auto-file memories
  (e.g. "file X was in 3 bug-fix commits this sprint → high-risk, record it").
- Confidence decay: semantic facts auto-downgrade confidence when the scoped
  file changes (detected via scope update), prompting human confirmation.
- Memory search: `scope mem search "jwt"` — full-text search across all memory
  types, ranked by type priority (semantic > procedural > episodic).
- Conflict detection: warn when a new semantic fact contradicts an existing one
  for the same scope (e.g. "auth uses HS256" vs "auth uses RS256").
- Memory export/import: `scope mem export --format markdown` for team wikis;
  `scope mem import wiki.md` to seed MemPalace from existing docs.
- Agent-driven memory: Claude Code skill that auto-runs mem_fetch before any
  task and auto-runs mem_add after completing a task (captures what it learned).

## Guiding Principles
- Deterministic updates > AI-only summaries.
- Compact slices > full repo scans.
- Hooks enforce discipline.
- Skills handle reusable playbooks.
