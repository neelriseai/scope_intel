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

## Phase 4: Long-Term Memory
- MemPalace-style memory integration.
- Store failures, ownership, historical changes.
- Cross-repo learning.

## Guiding Principles
- Deterministic updates > AI-only summaries.
- Compact slices > full repo scans.
- Hooks enforce discipline.
- Skills handle reusable playbooks.
