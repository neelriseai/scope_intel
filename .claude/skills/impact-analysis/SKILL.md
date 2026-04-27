---
name: impact-analysis
description: Analyse the blast radius of a change before making it. Use when asked "what will break if I change X?" or before a refactor/rename. Works on files, symbols, or features.
---

## impact-analysis workflow

### Input
Provide one of:
- `--file <repo-relative-path>` — a file you plan to change
- `--symbol <name>` — a function/class you plan to rename or remove
- `--feature <name>` — a whole feature being refactored

### Step 1 — Direct impact
```bash
scope impacted --file <path> --repo .
# or
scope impacted --symbol <name> --repo .
# or
scope impacted --feature <name> --repo .
```
- Record: direct (1-hop), transitive (multi-hop), features_touched.

### Step 2 — Symbol-level callers (if renaming/removing a symbol)
```bash
scope callers <symbol-name> --repo .
```
- Every caller must be updated if the symbol signature changes.

### Step 3 — Related tests
```bash
scope tests --file <path> --repo .
# or
scope tests --feature <name> --repo .
```
- These are the tests that must pass after the change.

### Step 4 — Touchpoints (if removing a route or config key)
```bash
scope touchpoints --feature <name> --repo .
```

### Step 5 — Report
Summarise:
- **Direct impact:** N files
- **Transitive impact:** N files
- **Features touched:** list
- **Tests to verify:** list
- **High-risk symbols:** callers of changed symbol
- **Recommendation:** safe / needs coordination / breaking change

---
**Output format:** Prefer the compact human view. Use `--json` only when piping to another tool.
