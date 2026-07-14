# Token-optimized Agent Context Pack

## Purpose
Keep always-loaded instructions small and load detailed knowledge only for the active work.

## Structure
```text
AGENTS.md                       Codex always-loaded rules
CLAUDE.md                       Claude Code always-loaded rules
docs/ai/IMPLEMENTATION_STATUS.md  current state only
docs/ai/EXECUTION_PLAN.md         phase index and reading map
docs/product/PRODUCT_OVERVIEW.md  compact product definition
docs/domain/                     domain rules, loaded when relevant
docs/ml/                         ML rules, loaded only for ML
docs/phases/                     one document per work phase
docs/reference/FULL_PRODUCT_PLAN.md  long reference, last resort
prompts/                        first and next-phase prompts
.claude/agents/                 optional Claude reviewer
```

## Context strategy
Always loaded:
- `AGENTS.md` or `CLAUDE.md`.

Read at task start:
- current status;
- active phase row and phase file.

Read only when listed:
- domain, data, ML, or product documents.

Read only as a last resort:
- full historical product plan.

## Install
Copy the contents into the existing project root. Merge rather than overwrite an existing root instruction file.

## First run
Use `prompts/FIRST_RUN.md`.

## Maintenance
- Keep root instructions under roughly 1,000 tokens when possible.
- Keep status focused on the current phase.
- Archive completed work instead of appending indefinitely.
- Do not use automatic full-file imports for the long reference plan.
- Start a fresh agent context when changing phases after status is updated.
