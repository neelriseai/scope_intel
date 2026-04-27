# Retrieval Layer (RAG)

## API Commands
- `get_feature_scope("checkout")`
- `get_symbol_context("applyDiscount")`
- `find_min_context_for_bug(trace, changed_files)`

## Output Examples
- Feature summary, owned packages, top entry points, top dependencies, top files, top related tests.
- Symbol context: declaring class, callers, callees, configs, impacted tests.

## Subagent Strategy
- **Explore** → locate minimal files/symbols.
- **Plan** → decide patch strategy.
- **Main Agent** → perform edits.
- **Validation Helper** → run tests, update scope.
