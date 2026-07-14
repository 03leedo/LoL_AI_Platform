# Execution Plan

Read only the active phase document and its listed references.

| Phase | Outcome | Phase document | Extra references |
|---|---|---|---|
| 0 | Map the real repository | `docs/phases/PHASE_00_AUDIT.md` | none |
| 1 | Evidence-safe analysis boundary | `docs/phases/PHASE_01_EVIDENCE.md` | `docs/domain/ANALYSIS_RULES.md` |
| 2 | Versioned, rerunnable data/features | `docs/phases/PHASE_02_DATA.md` | `docs/domain/DATA_AND_METRICS.md` |
| 3 | Fight/death/objective episodes | `docs/phases/PHASE_03_EPISODES.md` | `docs/domain/ANALYSIS_RULES.md` |
| 4 | Individual profile v1 | `docs/phases/PHASE_04_PROFILE.md` | `docs/domain/DATA_AND_METRICS.md` |
| 5 | Representative/best/deviation matches | `docs/phases/PHASE_05_MATCH_SELECTION.md` | `docs/domain/ANALYSIS_RULES.md` |
| 6 | Evidence-grounded Gemini output | `docs/phases/PHASE_06_GEMINI.md` | `docs/domain/ANALYSIS_RULES.md` |
| 7–8 | Advantage and expected-value ML | `docs/phases/PHASE_07_08_ML.md` | `docs/ml/MODEL_RULES.md` |
| 9–12 | Live collection, replay, highlights, vision | `docs/phases/PHASE_09_12_LATER.md` | relevant reference only |

## Shared phase procedure
1. Verify current status and `git status`.
2. Inspect the relevant implementation.
3. Write a file-level work package in the status file.
4. Implement only the active phase.
5. Run relevant checks.
6. Review the diff and domain language.
7. Update status and stop.

## Product order
```text
repository audit
→ evidence semantics
→ data/feature foundation
→ episode engine
→ individual profile
→ match selection and replay evidence
→ Gemini explanation
→ validated ML
→ local collection and replay
→ highlights
→ vision last
```

The full historical product plan is retained at `docs/reference/FULL_PRODUCT_PLAN.md`. Read it only when focused documents do not contain needed information.
