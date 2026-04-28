# MCP Query Contract (Extended)

This contract defines deterministic methods for assistants to query `.ai-context/` files.

## Core Methods

### list_context_files()
Enumerate all available context files with metadata.  
**Returns:** manifest from `index.json`.

---

### get_context_file(file_id)
Retrieve full content of a specific `.md` file by ID.  
**Input:** `file_id` (string, e.g., `"002"`)  
**Returns:** file content.

---

### get_context_slice(query)
Retrieve compact slice relevant to a query.  
**Input:** `query` (string, e.g., `"debug flow"`)  
**Returns:** matching sections.

---

### get_phase_status()
Return current implementation phase + deliverables.  
**Source:** `curated/current-phase.md`.

---

### get_constraints()
Return token-efficiency constraints.  
**Source:** `curated/constraints.md`.

---

### get_module_map()
Return toolkit + repo-local module map.  
**Source:** `curated/module-map.md`.

---

## Extended Methods (Generated Files)

### get_skill_playbook(skill_id)
Retrieve content from `007-skill-playbooks.md`.  
**Input:** `skill_id` (e.g., `"debug-feature"`, `"enhance-feature"`)  
**Returns:** skill workflow steps.

---

### get_subagent_strategy()
Retrieve subagent roles from `008-subagent-strategy.md`.  
**Returns:** Explore, Plan, Main Agent, Validation Helper strategy.

---

### get_schema_design()
Retrieve schema examples from `009-schema-design.md`.  
**Returns:** feature-map schema + symbol schema JSON.

---

### get_claude_integration()
Retrieve detailed integration guide from `claude-code-integration.md`.  
**Returns:** CLAUDE.md rules, hook configs, sample skill, verification steps.

---

### get_roadmap()
Retrieve phased roadmap from `roadmap.md`.  
**Returns:** Phase 1–4 deliverables + guiding principles.

---

## Usage Flow
1. Assistant starts → `list_context_files()`.  
2. Narrow query → `get_context_slice(query)`.  
3. Deep dive → `get_context_file(file_id)`.  
4. Workflow guidance → `get_skill_playbook()`, `get_subagent_strategy()`.  
5. Integration rules → `get_claude_integration()`.  
6. Project status → `get_phase_status()`, `get_roadmap()`.  
7. Constraints + module map → `get_constraints()`, `get_module_map()`.  

---

## Example Queries

```json
get_skill_playbook("debug-feature")
**Returns:**  /debug-feature workflow steps.
```

```json
get_claude_integration()
**Returns:**  CLAUDE.md template, hook configs, sample skill.
```

```json
get_claude_integration()
**Returns:**  CLAUDE.md template, hook configs, sample skill.
```
```json
get_roadmap()
**Returns:**  roadmap phases + deliverables.
```

