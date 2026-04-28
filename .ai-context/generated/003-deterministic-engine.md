# Deterministic Engine

## Modes
- **Fast Incremental Mode**
  - Triggered on file save/edit/commit.
  - Updates ownership, imports, impacted tests.

- **Deep Refresh Mode**
  - Nightly or on demand.
  - Rebuilds call graphs, ownership graphs, dependencies.

## Hook Strategy
- After file edit → update feature map.
- After task complete → refresh impacted tests.
- Before refactor → run impact analyzer.
- After generating code → validate scope ownership.

## Principle
Automation must be deterministic, compact, and non-bloated.
