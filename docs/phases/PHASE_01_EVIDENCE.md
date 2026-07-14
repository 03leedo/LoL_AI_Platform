# Phase 1 — Evidence-safe Analysis

## Read
- `docs/domain/ANALYSIS_RULES.md`
- relevant audit sections

## Outcome
Separate facts, interpretations, limitations, and replay questions without changing current metric values.

## Minimum model
Equivalent concepts:
- evidence ID and source;
- time/time range;
- observation payload;
- confidence and limitations;
- rule version;
- statement kind;
- linked evidence IDs.

Use existing architecture and names.

## Required
- preserve current formulas;
- replace causal presentation wording;
- support unknown/replay-review;
- add evidence links to major factual claims;
- maintain API compatibility or document migration.

## Tests
- statement cannot reference nonexistent evidence;
- numeric factual output links to evidence;
- objective loss after death is not rendered as confirmed causation;
- incomplete data can produce a limitation;
- current consumers still work.

Stop after this phase.
