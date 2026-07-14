# Phase 6 — Evidence-grounded Gemini

## Read
- `docs/domain/ANALYSIS_RULES.md`
- current evidence/profile APIs

## Outcome
Gemini explains structured computed evidence without becoming the metric source.

## Input tools/data
Prefer deterministic functions for profile, match overview, metric evidence, repeated patterns, turning points, checkpoints, selections, and limitations.

## Output
- observations;
- hypotheses;
- limitations;
- replay checkpoints;
- practice suggestions.

## Guardrails
- observation requires evidence IDs;
- reject unsupported numbers;
- cap hypotheses;
- require limitations for incomplete data;
- AI failure does not block deterministic analysis;
- log prompt/model/schema version.

Stop after this phase.
