# Skill Playbooks

## /debug-feature
- Identify feature from bug text/stack trace.
- Retrieve feature scope + impacted symbols.
- Inspect top files.
- Run related tests.
- Propose fix.

## /enhance-feature
- Identify feature boundary.
- Retrieve related modules/configs/tests.
- Check cross-feature side effects.
- Propose minimal edit set.
- Implement + validate.

## /impact-analysis
- Input: changed symbols/files.
- Output: feature impact, related tests, risky downstream methods/classes.

## /update-scope
- Rebuild maps for module/repo.
- Regenerate summaries.
- Detect stale ownership.
