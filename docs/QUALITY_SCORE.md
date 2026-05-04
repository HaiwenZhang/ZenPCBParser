# Quality Score

## Purpose

Use this rubric when reviewing changes. It keeps agent output aligned with
project expectations without requiring long one-off instructions.

## Score Dimensions

Rate each relevant dimension from 1 to 5:

- Correctness: behavior matches source format and target contracts.
- Boundary fit: changes stay in the owning package or documented layer.
- Versioning: parser, schema, semantic, and project versions follow policy.
- Validation: commands or tests cover the changed behavior and sample scope.
- Diagnostics: failures are visible, actionable, and not misleading.
- Maintainability: future agents can find the rule, test, or doc that explains
  the change.

## Minimum Bar

- No known parser/exporter behavior change should ship without changelog review.
- No schema-affecting change should ship without schema version review.
- No case-driven fix should ship without recording the case scope and key counts.
- No large generated output should be committed as documentation.

## Review Prompt

Before final handoff, answer:

- What user-visible behavior changed?
- Which files own that behavior?
- How was it verified?
- What remains intentionally unsupported?
