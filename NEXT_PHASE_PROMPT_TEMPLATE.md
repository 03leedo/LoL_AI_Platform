# Subsequent Phase Prompt Template

Replace `<PHASE>` and `<OUTCOME>` before use.

---

Use Fable for this task.

Read:
- `CLAUDE.md`;
- `docs/IMPLEMENTATION_STATUS.md`;
- the `<PHASE>` section of `docs/FABLE_EXECUTION_PLAN.md`;
- only the relevant sections of `docs/PRODUCT_ANALYSIS_SPEC.md`;
- the source files identified by the current status and audit.

Complete **only <PHASE>**.

Desired outcome:

> <OUTCOME>

Before editing:
1. verify `git status`;
2. confirm previous-phase acceptance criteria and existing test state;
3. update the Active Work Package with the file-level plan;
4. record any assumption.

Then implement the outcome using the current architecture, preserving existing behavior outside this phase.

Verification:
- run relevant unit/integration tests;
- run lint, type checks, and build where available;
- verify domain invariants;
- review for scope creep;
- update implementation status.

Stop after this phase. Do not start the next phase. Do not push or open a PR.
