Here’s the **updated README.md** with a full **Quickstart section** so new contributors can onboard quickly and run your MCP service locally:

---

## 📂 `.ai-context/README.md`

```markdown
# AI Context Project

This project defines a deterministic context system to guide AI assistants (Claude, Cursor, Codex) in consuming fewer tokens during debugging, input reading, and output generation.

---

## 📌 Purpose
- Prevent repo-wide scanning by assistants.
- Provide compact, queryable slices of context.
- Separate **global reusable heuristics** from **repo-specific truth**.
- Wire deterministic workflows into Claude Code via hooks, skills, and MCP.

---

## 📂 Structure

```
.ai-context/
├─ generated/        # Systematic, reusable knowledge
│  ├─ 001-project-overview.md
│  ├─ 002-system-architecture.md
│  ├─ 003-deterministic-engine.md
│  ├─ 004-rag-layer.md
│  ├─ 005-memory-layer.md
│  ├─ 006-validation-engine.md
│  ├─ 007-skill-playbooks.md
│  ├─ 008-subagent-strategy.md
│  ├─ 009-schema-design.md
│  ├─ claude-code-integration.md
│  ├─ roadmap.md
│  ├─ symbol-schema.md
│  ├─ index.json
│  └─ mcp-contract.md
├─ curated/          # Current evolving truths
│  ├─ current-phase.md
│  ├─ constraints.md
│  └─ module-map.md
└─ README.md         # Orientation and usage
```

---

## 🔧 MCP Contract

The MCP contract defines deterministic endpoints for assistants:

- `list_context_files()` → Manifest of all files.  
- `get_context_file(file_id)` → Full file content.  
- `get_context_slice(query)` → Compact slice matching query.  
- `get_phase_status()` → Current phase + deliverables.  
- `get_constraints()` → Token-efficiency rules.  
- `get_module_map()` → Toolkit + repo-local scope files.  
- `get_skill_playbook(skill_id)` → Skill workflows.  
- `get_subagent_strategy()` → Subagent roles.  
- `get_schema_design()` → Feature-map + symbol schema.  
- `get_claude_integration()` → Detailed Claude Code wiring guide.  
- `get_roadmap()` → Phased implementation plan.  

See `mcp-contract.md` and `mcp-contract-schema.json` for details.

---

## 🚀 Quickstart

### 1. Install Dependencies
```bash
pip install fastapi uvicorn
```

### 2. Run the MCP Server
```bash
uvicorn server:app --reload --port 8000
```

### 3. Test Endpoints
```bash
# List all context files
curl http://localhost:8000/list_context_files

# Retrieve full file content
curl http://localhost:8000/get_context_file/002

# Search for a slice
curl "http://localhost:8000/get_context_slice?query=debug flow"

# Get Claude integration guide
curl http://localhost:8000/get_claude_integration

# Get roadmap
curl http://localhost:8000/get_roadmap
```

### 4. Integrate with Claude Code
- Place `claude-code-integration.md` in `.ai-context/generated/`.  
- Use `.claude/settings.json` hooks to auto-refresh scope after edits.  
- Add skills (`/debug-feature`, `/impact-analysis`) under `.claude/skills/`.  
- Verify with `claude /hooks`.

---

## 📌 Key Files

- **claude-code-integration.md** → Detailed wiring guide (CLAUDE.md, hooks, sample skill).  
- **roadmap.md** → Phased plan (Phase 1–4, MVP → long-term memory).  
- **symbol-schema.md** → Dedicated symbol schema reference.  
- **007-skill-playbooks.md** → Reusable skills (/debug-feature, /enhance-feature, /impact-analysis, /update-scope).  
- **008-subagent-strategy.md** → Explore, Plan, Main Agent, Validation Helper.  
- **009-schema-design.md** → Feature-map + symbol schema examples.  

---

## ✅ Usage Flow

1. Assistant starts → `list_context_files()`.  
2. Narrow query → `get_context_slice(query)`.  
3. Deep dive → `get_context_file(file_id)`.  
4. Workflow guidance → `get_skill_playbook()`, `get_subagent_strategy()`.  
5. Integration rules → `get_claude_integration()`.  
6. Project status → `get_phase_status()`, `get_roadmap()`.  
7. Constraints + module map → `get_constraints()`, `get_module_map()`.  

---

## 📌 Guiding Principles
- **Always-loaded context must stay tiny** → CLAUDE.md only holds rules.  
- **Heavy reference material is lazy-loaded** → via skills, MCP queries.  
- **Deterministic updates > AI-only summaries** → hooks enforce discipline.  
- **Compact slices > full repo scans** → assistants query only what they need.  
```

---
