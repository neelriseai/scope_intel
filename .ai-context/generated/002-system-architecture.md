# System Architecture

## Layers
1. **Project Instructions Layer**
   - CLAUDE.md with concise rules.
   - Optional `.claude/rules/` for language/test-specific rules.

2. **Scope Index Layer**
   - Persistent knowledge base: features, symbols, dependencies, aliases, impacted tests.

3. **Update Engine**
   - Incremental updates on file edits.
   - Deep refresh for nightly rebuilds.

4. **Retrieval Interface**
   - Compact query commands: `get_feature_scope`, `get_symbol_context`, `find_related_tests`.

5. **Claude-Facing Execution Layer**
   - Skills (`/debug-feature`, `/enhance-feature`).
   - Subagents (Explore, Plan, Validation).

## Repo Example
