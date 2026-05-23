"""Curated agent-governance context scaffolding.

This module turns product-improvement strategy into reusable .ai-context files.
The goal is not to make Scope Intel a project manager; it gives coding agents a
small, explicit control surface before they start changing a repo.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GovernanceTemplate:
    filename: str
    title: str
    tags: tuple[str, ...]
    body: str


GOVERNANCE_TEMPLATES: tuple[GovernanceTemplate, ...] = (
    GovernanceTemplate(
        filename="001-product-philosophy.md",
        title="Product Philosophy",
        tags=("philosophy", "constitution", "governance"),
        body="""# Product Philosophy

Define the non-negotiable product principles before asking an agent to improve
the system.

## Constitution

- Accuracy first, cheap path preferred.
- Prefer deterministic logic, retrieval, caching, compact context, and small
  model routes before strong model calls.
- Keep latency low on user-facing paths.
- Preserve memory discipline: relevance, TTL, compression, and privacy.
- Bound agent loops with step, time, cost, and confidence limits.
- Require evidence, consent, verification, and audit for real-world actions.
- Avoid broad rewrites unless the metric gain and regression risk justify them.

## Product-Specific Additions

- Add the domain philosophy here.
- Add any named skill or tool philosophy here.
- Add user-trust promises here.
""",
    ),
    GovernanceTemplate(
        filename="004-skill-contracts.md",
        title="Skill Contracts",
        tags=("skills", "contracts", "bounded-execution"),
        body="""# Skill Contracts

Every reusable agent skill, worker, tool, or route should have an explicit
contract.

## Contract Template

### Skill Name

- Purpose:
- Inputs:
- Outputs:
- Allowed actions:
- Blocked actions:
- Failure modes:
- Fallback route:
- Cost estimate:
- Latency expectation:
- Required evidence:
- Tests protecting it:

## Guardrails

- Do not bypass skill input validation.
- Do not let an agent perform arbitrary work outside a registered skill/tool.
- Preserve deterministic workers when they solve the task reliably.
""",
    ),
    GovernanceTemplate(
        filename="005-quality-gates.md",
        title="Quality Gates",
        tags=("quality", "metrics", "approval-gate"),
        body="""# Quality Gates

No non-trivial change is accepted unless it passes these gates.

## Change Approval Gate

1. Aligns with product philosophy.
2. Protects important invariants.
3. Improves a measurable metric or reduces a real risk.
4. Preserves privacy, consent, and user trust.
5. Chooses the best route for accuracy, cost, latency, and risk.
6. Has bounded failure behavior.
7. Includes tests or a validation plan.
8. Updates the right docs, TODO, or decision log.

## Metrics

- Cost: model calls per task, token use, cache hit rate.
- Latency: p50/p95 response time, timeout rate, fallback delay.
- Reliability: success rate, retry success rate, unhandled exceptions.
- Memory: compression ratio, stale memory use, sensitive-fact blocking.
- Quality: invariant tests, live validation pass rate, source freshness.
""",
    ),
    GovernanceTemplate(
        filename="007-review-loop-instructions.md",
        title="Review Loop Instructions",
        tags=("review-loop", "challenge", "decision"),
        body="""# Review Loop Instructions

Use this loop for substantial work:

```text
Scope context
-> Current state map
-> Design challenge
-> Code challenge
-> Philosophy/skill challenge
-> Defense of existing design
-> Measured decision
-> Small implementation slice
-> Tests and evidence
-> Documentation and decision memory
```

## Required Output For Each Improvement

1. Current problem.
2. Challenge.
3. Defense of the current implementation, if valid.
4. Final decision: keep, modify, refactor, rewrite, postpone, or reject.
5. Reason and trade-off.
6. Files affected.
7. Tests or validation evidence.
8. Metric improved.
9. Risk and rollback plan.
""",
    ),
    GovernanceTemplate(
        filename="008-product-invariants.md",
        title="Product Invariants",
        tags=("invariants", "protected-features", "do-not-break"),
        body="""# Product Invariants

This registry protects unique product behavior from accidental simplification.

## Classification

- Core invariant: must not change without explicit approval.
- Protected feature: can improve, but external behavior must remain.
- Experimental feature: can be modified or replaced if a better path exists.
- Accidental complexity: can be removed when proven unnecessary.
- Dead feature: can be removed after usage check.

## Invariant Template

### Invariant Name

- Protection level:
- Code locations:
- Design principle supported:
- Why it is unique:
- What breaks if changed:
- Allowed changes:
- Approval required:
- Protection tests:
""",
    ),
    GovernanceTemplate(
        filename="009-do-not-simplify.md",
        title="Do Not Simplify",
        tags=("do-not-simplify", "risk", "protected-complexity"),
        body="""# Do Not Simplify Without Approval

Some logic looks complex because it protects reliability, cost, privacy, or
auditability.

## Protected Complexity

- Multi-stage fallback chains.
- Detailed event logging and audit trails.
- Memory scoring, TTL, compression, and conflict handling.
- Skill input/output validation.
- Error categorization and retry budgets.
- Cost guardrails and model-routing thresholds.
- Consent, privacy, and external-action boundaries.

Before simplifying any item, document the invariant affected, risk, safer
alternative, required test, and rollback plan.
""",
    ),
    GovernanceTemplate(
        filename="010-hidden-gems.md",
        title="Hidden Gems",
        tags=("hidden-gems", "discovery", "differentiators"),
        body="""# Hidden Gems

Use this file to promote useful implementation ideas that are easy for future
agents to miss.

## Hidden Gem Template

### Feature Or Pattern

- What it does:
- Why it is valuable:
- Where it exists:
- Product differentiator:
- Should it become an invariant:
- Documentation needed:
- Tests needed:
""",
    ),
    GovernanceTemplate(
        filename="011-architecture-decisions.md",
        title="Architecture Decisions",
        tags=("decisions", "adr", "rollback"),
        body="""# Architecture Decisions

Record accepted, rejected, and postponed design choices.

## Decision Template

Date:
Module:
Decision:
Status: Accepted / Rejected / Postponed
Reason:
Trade-off:
Impact on cost:
Impact on latency:
Impact on reliability:
Impact on memory:
Risk:
Rollback plan:
""",
    ),
)


def scaffold_governance_context(
    repo: Path | str,
    *,
    overwrite: bool = False,
    dry_run: bool = False,
) -> dict[str, object]:
    root = Path(repo).resolve()
    curated = root / ".ai-context" / "curated"
    written: list[str] = []
    skipped: list[str] = []
    planned: list[str] = []

    if not dry_run:
        curated.mkdir(parents=True, exist_ok=True)

    for template in GOVERNANCE_TEMPLATES:
        target = curated / template.filename
        rel = str(target.relative_to(root)).replace("\\", "/")
        planned.append(rel)
        if target.exists() and not overwrite:
            skipped.append(rel)
            continue
        if not dry_run:
            target.write_text(_render_template(template), encoding="utf-8")
        written.append(rel)

    return {
        "ok": True,
        "repo": str(root),
        "target_dir": str(curated.relative_to(root)).replace("\\", "/"),
        "planned": planned,
        "written": written,
        "skipped": skipped,
        "overwrite": overwrite,
        "dry_run": dry_run,
        "next_steps": (
            "review curated governance files",
            "fill product-specific invariants and skill contracts",
            "run scope doc validate",
            "run scope compact build --repo . --target ai-context",
        ),
    }


def _render_template(template: GovernanceTemplate) -> str:
    tags = ", ".join(template.tags)
    return (
        f"---\n"
        f"title: {template.title}\n"
        f"tags: [{tags}]\n"
        f"source: scope_intel_governance_scaffold\n"
        f"---\n\n"
        f"{template.body.rstrip()}\n"
    )
