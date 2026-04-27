---
name: debug-feature
description: Guided debug workflow using the scope index. Use when a user reports a bug, paste of a stack trace, or "it's broken" for a named feature. Queries scope before reading any source.
---

## debug-feature workflow

**Goal:** Identify and patch the root cause using the minimum set of files.

### Step 1 — Classify the feature
- Read the bug description / stack trace.
- Identify the probable feature name (1–3 words).
- Run: `scope features --repo .` — confirm the feature id exists.

### Step 2 — Retrieve compact scope
```bash
scope feature <feature-id> --repo .
```
- Note: entry points, key files, depends_on_features, related tests.
- Do NOT open any source files yet.

### Step 3 — Narrow to impacted symbols
```bash
scope symbol <suspect-symbol> --repo .
```
- Check reads / writes / callers / callees.
- If stack trace has a file: `scope impacted --file <path> --repo .`

### Step 4 — Open minimal source (max 3–5 files)
- Use the `key_files` and `entry_points` from step 2.
- Read the smallest slice that covers the error.

### Step 5 — Run related tests
```bash
scope tests --feature <feature-id> --repo .
```
- Run those tests locally to reproduce.

### Step 6 — Patch
- Apply the minimal fix.
- Do not touch files outside the scope slice unless the impact graph demands it.

### Step 7 — Validate + refresh scope
```bash
scope update --files <changed-file> --repo .
```
- Re-run related tests.

---
**Token discipline:** Never run `Glob **/*` or `Grep` across the whole repo before steps 1–3 complete.
