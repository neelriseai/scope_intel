---
name: enhance-feature
description: Guided enhancement workflow. Use when a user asks to add/extend behaviour in a named feature. Checks cross-feature side effects before editing.
---

## enhance-feature workflow

**Goal:** Implement the enhancement in the smallest possible change set with verified side-effect awareness.

### Step 1 — Identify feature boundary
```bash
scope feature <feature-id> --repo .
```
- Note owned_packages, depends_on_features, entry_points.

### Step 2 — Check cross-feature side effects
```bash
scope impacted --feature <feature-id> --repo .
```
- List any features that import from this one — they may be affected.
- For each dependent feature: `scope feature <dep-id>` to understand the coupling.

### Step 3 — Retrieve touchpoints
```bash
scope touchpoints --feature <feature-id> --repo .
```
- Identify routes, configs, DB models that the enhancement will touch.

### Step 4 — Plan the edit set
- List the files you intend to modify (from key_files + entry_points).
- Confirm no unrelated files are in the list.

### Step 5 — Implement (targeted classes only)
- Edit only the files identified in step 4.
- Add new symbols; do not rename existing public entry points without checking callers:
  ```bash
  scope callers <entry-point-symbol> --repo .
  ```

### Step 6 — Run impacted tests
```bash
scope tests --feature <feature-id> --repo .
```

### Step 7 — Update scope + summaries
```bash
scope update --files <all-changed-files> --repo .
```

---
**Token discipline:** Do not read the entire feature directory. Use `key_files` from step 1 as the reading list.
