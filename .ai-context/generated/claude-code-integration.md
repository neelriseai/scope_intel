# Wiring the toolkit into Claude Code

This page shows how to make Claude Code actually *use* the scope index:
- a project `CLAUDE.md` that tells Claude to consult the index first
- a `PostToolUse` hook that auto-refreshes the index after Claude edits files
- (optional) a `UserPromptSubmit` hook that injects a one-line repo summary on
  each new prompt
- (optional) a custom skill so Claude has a named playbook for "use scope first"

Prereqs:
- The toolkit is on `PATH` (the `scope` command resolves), or you call it via
  `python -m scope_intel`.
- The target repo has been initialised with `scope init` and indexed once.

## 1. Project-level `CLAUDE.md`

`scope init --write-claude-md` writes the file below into the repo root if
one doesn't already exist. Trim or extend to taste:

```markdown
# Scope Intelligence rules for Claude Code

This repo has a local scope index at `.scope-intelligence/`.

Workflow:
1. Before debugging, enhancement, or refactoring, query the scope index first.
2. Use the smallest feature/module scope possible. Do not load unrelated files.
3. After making changes, run `scope update --files <changed>` to refresh.

Useful commands:
    scope summary
    scope feature <name>
    scope impacted --file <path>
    scope tests --file <path>
    scope symbol <name>
    scope update --files <a> <b>
```

## 2. Hook config — `.claude/settings.json`

Drop this in the repo's `.claude/settings.json` (create the folder if
missing). It runs `scope update` after every successful `Edit` / `Write` /
`MultiEdit` Claude performs in the repo, scoped to the file Claude just
touched.

Claude Code passes hook payloads to commands as **JSON on stdin**, with a
`tool_input.file_path` field for edit-style tools. `$CLAUDE_PROJECT_DIR` is
the only path-related env var you can rely on. The shim script below reads
stdin and forwards the file path to `scope update`.

`.claude/scope-update-hook.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
file=$(python -c "import json,sys; d=json.load(sys.stdin); ti=d.get('tool_input') or {}; \
print(ti.get('file_path') or ti.get('filePath') or '')")
[ -n "$file" ] || exit 0
# Make path repo-relative
rel=$(python -c "import os,sys; r=os.environ['CLAUDE_PROJECT_DIR']; \
p=sys.argv[1]; print(os.path.relpath(p, r))" "$file")
exec python -m scope_intel update --repo "$CLAUDE_PROJECT_DIR" --files "$rel"
```

`.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/scope-update-hook.sh",
            "timeout": 30,
            "run_in_background": true
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python -m scope_intel summary --repo \"$CLAUDE_PROJECT_DIR\" --json 2>/dev/null | python -c \"import json,sys;\\nd=json.load(sys.stdin); t=d.get('totals',{});\\ntop=','.join(f['id'] for f in d.get('top_features',[])[:5]);\\nprint(f'<scope>files={t.get(\\\"files\\\")} symbols={t.get(\\\"symbols\\\")} features={t.get(\\\"features\\\")} top={top}</scope>')\"",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

Windows users: replace the `bash` shim with a `.cmd` wrapper that does the
same stdin parse with `python -c`.

Key bits:
- `matcher` selects which Claude tools fire the hook. `Edit|Write|MultiEdit`
  covers all the cases where source changes.
- The hook reads `tool_input.file_path` from stdin JSON — that's how Claude
  Code tells the hook which file just changed.
- `run_in_background: true` means Claude doesn't wait for re-indexing to
  finish — important because a large repo refresh could block the
  conversation.
- The `UserPromptSubmit` hook is optional; it injects a single tagged
  `<scope>...</scope>` line into the prompt so Claude always knows the rough
  shape of the repo without reading any JSON.

## 3. Pre-tool guard (optional)

If you want to *force* Claude to query the scope index before reading large
swaths of source, add a `PreToolUse` hook that flags wide `Glob` / `Grep`
calls:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Glob|Grep",
        "hooks": [
          {
            "type": "command",
            "command": "python -m scope_intel summary --repo \"$CLAUDE_PROJECT_DIR\" --json >/dev/null 2>&1 && echo 'scope index available — prefer `scope feature` or `scope impacted` for narrowing' || true",
            "timeout": 3
          }
        ]
      }
    ]
  }
}
```

This prints a soft reminder rather than blocking — Claude still gets to run
the search, but the message nudges it toward the cheaper query path.

## 4. Sample skill (optional)

For repos where you want a named, explicit workflow, drop a skill at
`.claude/skills/use-scope/SKILL.md`:

```markdown
---
name: use-scope
description: Query the local scope index before reading source files. Use when starting any debugging or enhancement task.
---

When the user asks for a debug, enhancement, or impact-analysis task:

1. Run `scope summary` to confirm the index exists and learn the top features.
2. Run `scope feature <best-match>` to retrieve the smallest relevant slice.
3. Run `scope impacted --file <touched-file>` before editing anything that
   has many reverse imports.
4. Open at most the top 3-5 files returned by the queries above.
5. After edits, hooks will refresh the index automatically — no manual call
   needed.
```

## 5. Verifying the wiring

```bash
# Confirm Claude Code sees the hooks (after editing settings.json)
claude /hooks

# Tail what scope writes during a session
tail -f .scope-intelligence/state.json
```

If the hook silently fails, check Claude Code's transcript view (`Ctrl-R`) —
hook stderr is captured there.
