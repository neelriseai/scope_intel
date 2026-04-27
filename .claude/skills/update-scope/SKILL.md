---
name: update-scope
description: Rebuild or refresh the scope index for a repo (or a subset of files). Use after bulk edits, a merge, or when the index feels stale. Also detects stale feature ownership.
---

## update-scope workflow

### When to use
- After editing multiple files in one session (hooks handle single-file edits automatically).
- After pulling/merging a branch.
- When `scope summary` shows unexpected feature counts or missing symbols.
- To do a full deep refresh (nightly or pre-release).

### Fast incremental refresh (default — skip unchanged files)
```bash
scope index --incremental --repo .
```
- Parses only files whose content hash differs from last index.
- Cross-file edges and aggregates are still recomputed.

### Targeted refresh (specific files)
```bash
scope update --files src/auth/login.py src/auth/session.py --repo .
```

### Full rebuild (nuclear option)
```bash
scope index --repo .
```

### Detect stale ownership
After indexing, run:
```bash
scope features --repo .
```
- Any feature with `files=0` or unexpected `depends_on_features` indicates stale ownership.
- Fix by editing `.scope-intelligence/config.json` → `feature_overrides`.

### Git-diff aware update (after merge)
```bash
scope diff main --repo .
```
- Shows which features and tests are affected by commits not yet on `main`.
- Use this to decide whether a targeted `scope update` or full `scope index` is needed.

---
**When in doubt:** `scope index --incremental` is always safe and cheap. Full `scope index` is the fallback.
