# Scope Intelligence rules for Claude Code

This repo has a local scope index at `.scope-intelligence/`. Use it before
scanning the codebase by hand.

Workflow:
1. Before debugging, enhancement, or refactoring, query the scope index first.
2. Use the smallest feature/module scope possible. Do not load unrelated files.
3. After making changes, run `scope update --files <changed>` to refresh.

Useful commands (run from the repo root):

    scope summary                       # repo overview (compact)
    scope feature <name-or-alias>       # files, symbols, tests for a feature
    scope impacted --file <path>        # files transitively affected by a change
    scope impacted --symbol <name>      # blast radius of a symbol change
    scope tests --file <path>           # related tests for a file
    scope tests --feature <name>        # related tests for a feature
    scope symbol <name>                 # callers + callees of a symbol
    scope update --files <a> <b> ...    # incremental re-index after edits

Stored data is JSON only — no source code. Safe to commit if you want to
share the scope map with the team.
