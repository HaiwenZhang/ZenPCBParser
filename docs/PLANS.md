# Plans

## Purpose

Plans are versioned work artifacts. They preserve intent, progress, and decisions
so agents can resume work without depending on chat history.

## When To Create A Plan

Create or update an execution plan when work is broad, risky, multi-step, or
likely to span turns.

Examples:

- Adding a new parser or exporter.
- Changing JSON schema or Semantic model contracts.
- Refactoring package boundaries.
- Case-driven fixes that require multiple hypotheses and validation passes.

Small single-file fixes can use a short in-chat checklist instead.

## Locations

- Active plans: `docs/exec-plans/active/`
- Completed plans: `docs/exec-plans/completed/`
- Known debt: `docs/exec-plans/tech-debt-tracker.md`

## Plan Shape

Use concise sections:

- Goal
- Scope
- Non-goals
- Current status
- Steps
- Validation
- Decisions
- Open risks

Move completed plans to `docs/exec-plans/completed/` and leave a short result
summary in the plan.
