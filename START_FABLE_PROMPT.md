# First Fable Prompt

Paste the following into Claude Code from the repository root after placing this handoff pack in the project.

---

Use Fable for this task.

Read `CLAUDE.md`, `docs/IMPLEMENTATION_STATUS.md`, and `docs/FABLE_EXECUTION_PLAN.md`.  
Use `docs/PRODUCT_ANALYSIS_SPEC.md` only as a domain reference; do not treat its suggested stack or table names as proof of the repository’s current architecture.

Your outcome is to complete **Phase 0 and Phase 1 only**:

1. Inspect the entire repository and create `docs/REPOSITORY_AUDIT.md`.
2. Map every currently implemented indicator to its actual files, inputs, formulas, API outputs, UI consumers, and tests.
3. Protect all pre-existing uncommitted user changes.
4. Before editing product code, update `docs/IMPLEMENTATION_STATUS.md` with a file-level Phase 1 work package.
5. Implement an evidence-safe analysis boundary that separates:
   - observation;
   - hypothesis;
   - limitation;
   - replay question.
6. Preserve existing metric calculations unless you find and document a clear bug.
7. Remove or migrate causal wording such as “this death caused the objective loss” into evidence-grounded wording.
8. Add the smallest useful tests for the new semantics and backward compatibility.
9. Run all relevant tests, lint, type checks, and builds that the repository supports.
10. Review the final diff for scope creep.
11. Update `docs/IMPLEMENTATION_STATUS.md` with decisions, changed files, test results, risks, and the exact recommended Phase 2 outcome.
12. Stop. Do not start Phase 2.

Use read-only exploration or subagents for broad codebase investigation when useful, but keep the final architectural conclusions in the main session.

Do not ask me questions that can be answered by inspecting the repository. When a safe assumption is necessary, record it in the status file. Report a blocker only under the blocker conditions in `CLAUDE.md`.

At the end, provide:
- architecture summary;
- files changed;
- preserved behavior;
- tests run and results;
- unresolved risks;
- suggested commit breakdown.

Do not push or open a PR.
