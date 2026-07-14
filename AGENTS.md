# AGENTS.md

## Goal
Build an evidence-based LoL analysis platform for individual users.

## Read only what is needed
1. Read `docs/ai/IMPLEMENTATION_STATUS.md`.
2. Read the active phase in `docs/ai/EXECUTION_PLAN.md`.
3. Read only the documents listed for that phase.
4. Inspect the repository before proposing changes.

Repository code is the source of truth for current architecture, commands, formulas, and behavior. Planning documents describe goals, not existing implementation.

## Core rules
- Focus on individual analysis. Do not add team-fit, roster, synergy, leadership, or mentality scores.
- Team data may be used only as context, a denominator, or a model input for individual analysis.
- Separate observation, hypothesis, limitation, and replay question.
- Do not convert temporal sequence or correlation into causation.
- Preserve existing metric formulas unless the active task explicitly changes them.
- A single match is not permanent skill.
- Factual analysis claims require evidence IDs or source records.
- Low-confidence output must allow `unknown`, `insufficient_data`, or `needs_replay_review`.
- Use `advantage`, not `win probability`, until the model is calibrated and validated.
- Do not present risk or style as a positive ability score.

## Workflow
Before editing:
- run `git status`;
- protect existing user changes;
- inspect relevant code, tests, commands, and contracts;
- record the work package in `docs/ai/IMPLEMENTATION_STATUS.md`.

During editing:
- complete only the active phase;
- extend existing architecture instead of creating a parallel system;
- make the smallest coherent change;
- add tests for changed behavior;
- keep thresholds and derived logic centralized and versioned.

After editing:
- run relevant tests, lint, type checks, and build;
- review the diff for regression and scope creep;
- update `docs/ai/IMPLEMENTATION_STATUS.md`;
- report changes, checks, risks, and the next action;
- stop before the next phase.

## Safety
- Never discard uncommitted user changes.
- Do not silently change public API meanings.
- Destructive schema changes require migration and recovery notes.
- Do not expose or commit secrets or personal data.
- Do not broadly format unrelated files.
- Do not push, open a PR, or merge unless explicitly requested.

## Completion
A task is complete only when acceptance criteria and relevant checks pass, existing behavior is preserved, domain language is evidence-safe, and the status document is updated.

Do not ask questions that repository inspection can answer. Record the safest reasonable assumption unless credentials, policy, conflicting requirements, destructive decisions, or user changes block safe progress.
