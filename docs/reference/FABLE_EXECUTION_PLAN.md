# Fable Execution Plan
## Individual-focused LoL professional analysis platform

This is the **implementation control document**.  
`docs/reference/PRODUCT_ANALYSIS_SPEC.md` is the detailed domain reference.  
`docs/ai/IMPLEMENTATION_STATUS.md` is the live source of truth for progress.

---

# 1. How Fable Should Use This Plan

Fable should receive a meaningful phase outcome rather than a list of tiny code edits.

For each phase:

1. investigate the repository;
2. map the requested outcome onto the existing architecture;
3. write a file-level implementation plan;
4. implement only that phase;
5. verify behavior;
6. update status and stop.

Do not redesign the entire repository before the current phase requires it.

## Context-efficiency rule

Use this reading order:

```text
CLAUDE.md
→ IMPLEMENTATION_STATUS.md
→ active phase in this file
→ relevant PRODUCT_ANALYSIS_SPEC sections
→ relevant source files
```

Do not repeatedly reread the full 2,000+ line specification.

---

# 2. Target Outcome

The eventual product should support:

```text
Riot match/timeline ingestion
→ normalized individual match data
→ event and episode analysis
→ versioned evidence
→ individual match features
→ long-term role-specific profile
→ representative / best / deviation matches
→ replay checkpoints
→ optional Gemini explanation
→ later ML, Live Client, replay automation, highlights
→ vision analysis last
```

The immediate development path is deliberately narrower.

---

# 3. Phase Order

| Phase | Outcome | Dependency |
|---|---|---|
| 0 | Repository audit and implementation map | none |
| 1 | Evidence-safe analysis semantics | 0 |
| 2 | Versioned data and feature foundation | 1 |
| 3 | Fight, death, and objective episode engine | 2 |
| 4 | Individual profile v1 | 3 |
| 5 | Representative, best, and deviation matches | 4 |
| 6 | Evidence-grounded Gemini analysis | 1, 4, 5 |
| 7 | Advantage model | 2, 3 |
| 8 | Expected-performance models | 4, data volume |
| 9 | Live Client local collector | 2 |
| 10 | Replay review mode | 3, 5 |
| 11 | Highlight showcase | 9 or 10 |
| 12 | Vision analysis | all relevant foundations |

Do not start Phase 12 early.

---

# Phase 0 — Repository Audit

## Outcome

Produce a reliable map of the current system so later work extends existing behavior rather than replacing it.

## Required investigation

- repository tree and monorepo boundaries;
- backend, frontend, worker, ML, and local-app components;
- package managers and runtime versions;
- build, lint, type-check, test, and migration commands;
- current database schema;
- current Riot API ingestion;
- current match/timeline domain types;
- current indicators and exact formulas;
- current AI/Gemini integration;
- current UI routes and response contracts;
- duplicate or dead implementations;
- current failing tests and known issues;
- git status and uncommitted user work.

## Deliverables

Create:

### `docs/ai/REPOSITORY_AUDIT.md`

Must include:

1. architecture summary;
2. runtime and commands;
3. data-flow diagram;
4. current feature inventory;
5. indicator-to-file map;
6. API and DB contracts;
7. test coverage map;
8. risks and technical debt;
9. recommended file-level Phase 1 plan;
10. explicit list of files that should not be touched yet.

### Update `docs/ai/IMPLEMENTATION_STATUS.md`

Set:
- current phase;
- repository facts;
- verified commands;
- blockers;
- next action.

## Acceptance criteria

- No product code changed.
- Existing formulas are documented from code, not inferred from product docs.
- Every proposed Phase 1 edit points to an existing file or clearly justified new module.
- Unknowns are marked unknown.

---

# Phase 1 — Evidence-safe Analysis Semantics

## Outcome

Existing analysis continues to work, but facts, interpretations, limitations, and replay questions become structurally separate and testable.

## Required behavior

Introduce or adapt a response/domain structure equivalent to:

```text
AnalysisEvidence
- id
- source match/event IDs
- time range
- observation type
- payload
- confidence
- limitations
- rule version

AnalysisStatement
- kind: observation | hypothesis | limitation | replay_question
- text
- evidence IDs
- confidence
```

The exact classes and locations must follow the existing stack.

## Scope

- preserve current metric calculations;
- replace causal wording at the presentation/analysis boundary;
- attach evidence IDs to major analysis claims;
- allow `unknown` and `needs_replay_review`;
- rename unvalidated probability output to `advantage`;
- separate positive performance metrics from risk/style indicators in response metadata where feasible;
- fix only clear related contradictions or duplicate output discovered in the audit.

## Non-goals

- no large schema redesign;
- no new ML model;
- no Live Client;
- no replay control;
- no new top-level scoring formula;
- no deletion of current indicators.

## Tests

At minimum:

- an observation cannot reference nonexistent evidence;
- a factual numeric statement is evidence-linked;
- death followed by objective loss is not rendered as confirmed causation;
- low-confidence data can produce a limitation or review-needed result;
- old response consumers remain compatible or receive a documented migration path.

## Acceptance criteria

- current analysis endpoint/page still works;
- metric numeric outputs are unchanged unless a verified bug is fixed;
- output language follows the domain invariants;
- tests pass;
- status and decision log updated.

---

# Phase 2 — Versioned Data and Feature Foundation

## Outcome

Source data, normalized records, derived features, and analysis evidence can be independently versioned and regenerated.

## Required logical layers

Adapt existing storage rather than blindly creating all-new tables.

```text
raw source
normalized match / participant / snapshot / event
derived episode / feature
profile or model output
analysis evidence
```

## Required properties

- idempotent ingestion;
- source and schema version;
- feature/rule version;
- source lineage;
- completeness/confidence flags;
- deterministic feature regeneration;
- backward-compatible migration where practical.

## Minimum entities

Use existing equivalents when present:

- match;
- participant;
- timeline snapshot/frame;
- event;
- player-game feature;
- analysis evidence.

Episode tables may be introduced in Phase 3.

## Acceptance criteria

- importing the same match twice does not duplicate normalized records;
- a selected match can have features regenerated from stored source data;
- derived records show version and lineage;
- migrations have rollback or recovery notes;
- fixtures cover one representative match and one incomplete match.

---

# Phase 3 — Episode Engine

## Outcome

Related kills, deaths, and objective consequences are grouped into reviewable episodes so one team event is not counted repeatedly.

## Modules

### Fight episode builder

Initial configurable heuristics may include:
- kill time gap;
- map distance;
- pre-window;
- post-windows.

Do not hard-code thresholds throughout the codebase. Centralize and version them.

### Death context builder

Attach:
- timestamp;
- game-state context;
- lead state;
- shutdown state;
- nearest ally information when available;
- map-depth estimate;
- upcoming objective context;
- exchange outcome;
- 30/60/90-second follow-up;
- limitations.

### Objective window builder

Determine:
- whether a death is objectively analyzable;
- objective spawn/alive status;
- participant availability;
- event linkage;
- opposite-side trade;
- data confidence.

## Key correction

Do not use all deaths as the denominator for objective-related death rates.

Use only deaths that satisfy the explicit `objective-analyzable` predicate.

## Tests

- one dragon loss linked to one fight episode is not multiplied by four deaths;
- spatially distant kills are not merged solely by time;
- incomplete position data lowers confidence rather than inventing proximity;
- objective-analyzable denominator is reproducible;
- red/blue side handling is symmetric.

## Acceptance criteria

- episode output is deterministic;
- evidence cards can point to episode time ranges;
- existing Death Cost and related metrics consume episode evidence or are ready to;
- no unverified intent is inferred.

---

# Phase 4 — Individual Profile v1

## Outcome

Provide four explainable, role-filtered individual profile dimensions using rules and cohort normalization before complex ML.

## Required dimensions

1. early growth stability;
2. resource conversion efficiency;
3. risk exposure management;
4. objective readiness.

Optional fifth dimension only if current data supports it reliably:
- fight outcome contribution.

## Rules

- calculate per-match features first;
- aggregate only comparable role records;
- record sample size;
- apply recency weighting;
- apply sample-size shrinkage toward cohort baseline;
- expose uncertainty or confidence;
- do not call the output permanent skill.

## Cohort

Use the best available combination of:
- queue;
- role;
- tier range;
- patch range;
- champion role group.

Fallbacks must be explicit.

## Output example

```json
{
  "metric": "risk_exposure_management",
  "score": 42,
  "sample_size": 20,
  "confidence": "medium",
  "comparison_group": "KR ranked ADC, current patch range",
  "submetrics": [],
  "evidence_match_ids": []
}
```

## Acceptance criteria

- different roles are not silently averaged;
- three matches do not produce falsely precise high-confidence profiles;
- each profile dimension exposes submetrics and evidence;
- risk/style direction is clearly distinguished from positive performance direction;
- profile values can be regenerated from match features.

---

# Phase 5 — Representative, Best, and Deviation Matches

## Outcome

Turn abstract profile values into concrete matches and replay checkpoints.

## Required outputs

### Representative match
The comparable match whose standardized feature vector is closest to the user’s long-term profile.

### Best-performance match
The match with the strongest context-adjusted positive performance, not simply highest KDA.

### Profile-deviation match
The recent comparable match whose feature vector differs most from the long-term profile.

Do not call this the “worst match.”

## Method

1. select comparable matches;
2. standardize dimensions by cohort;
3. exclude low-quality or abnormal records;
4. calculate vector distance/similarity;
5. store selection reason and version;
6. identify dimensions driving the selection;
7. attach evidence windows.

Start with a clear distance method. Do not introduce clustering unless it materially improves validated behavior.

## Exclusions

- remakes;
- abnormally short matches;
- off-role records unless explicitly requested;
- records with critical missing data;
- incompatible game modes;
- optional: first records after a major patch when the comparison baseline is insufficient.

## Acceptance criteria

- match selections are deterministic for a profile version;
- selection reasons are visible;
- “deviation” may contain positive and negative differences;
- users can open evidence for the dimensions that caused the selection;
- tests cover equal-distance and missing-dimension cases.

---

# Phase 6 — Gemini Evidence Agent

## Outcome

Gemini explains computed results without becoming the source of truth.

## Architecture

Prefer deterministic application tools/functions such as:

```text
get_player_profile
get_match_overview
get_metric_evidence
get_repeated_patterns
get_turning_points
get_replay_checkpoints
get_representative_matches
get_data_limitations
```

Gemini receives structured results. It does not directly parse raw timelines for authoritative metrics.

## Model use

- Flash: default summaries and comparison reports;
- Thinking: explicit detailed analysis or coach-share report only.

## Required schema

```text
observations
hypotheses
limitations
replay_checkpoints
practice_suggestions
```

Each observation must carry evidence IDs.

## Guardrails

- reject unsupported numeric claims;
- cap the number of hypotheses;
- require limitations when source completeness is low;
- suggestions must be framed as experiments, not commands;
- allow no-analysis response when evidence is insufficient;
- log prompt/model/schema version.

## Acceptance criteria

- replayable test fixtures produce schema-valid output;
- unsupported statements are rejected or omitted;
- AI failure does not block deterministic analysis;
- costs and token usage can be observed;
- private data is not unnecessarily included.

---

# Phase 7 — Advantage Model

## Outcome

Replace heuristic advantage flow with a validated, calibrated model.

## Training row

One match at one timestamp.

## Candidate features

Only features available at inference time:
- gold and XP differences;
- kills;
- towers;
- dragons/grubs/herald/baron state;
- alive and respawn-time differences;
- role-level gold differences;
- game time and patch.

## Baseline and model

1. logistic regression;
2. XGBoost or LightGBM only if it improves relevant metrics;
3. probability calibration.

## Split

- group by match ID;
- train on earlier time periods;
- validate later;
- test on the latest held-out period;
- do not random-split timestamp rows.

## Metrics

- ROC-AUC;
- log loss;
- Brier score;
- ECE/calibration plot;
- performance by time bucket, role cohort where relevant, and patch.

## Output rule

Use `advantage` until calibration and held-out validation meet documented thresholds.

## Acceptance criteria

- dataset builder is reproducible;
- baseline report exists;
- leakage checks documented;
- model artifact and feature schema versioned;
- inference path uses the same feature definitions as training.

---

# Phase 8 — Expected-performance Models

## Outcome

Evaluate individual outcomes relative to expected context rather than raw totals.

## Start with

- Expected GD@10;
- Expected CSD@10;
- Expected XPD@10.

## Inputs

Based on actual available data:
- patch;
- role;
- player champion;
- opponent champion;
- side;
- tier or competition level;
- opponent strength proxy;
- early kill/death and jungle-intervention proxies.

## Output

```text
actual - expected
```

This residual feeds early expected-performance reporting.

## Rules

- pro and solo-queue models remain separate;
- explain fallback when matchup samples are sparse;
- evaluate by time period and cohort;
- compare with simple grouped averages;
- use SHAP only after model validity is established.

## Acceptance criteria

- held-out results beat or meaningfully complement grouped baselines;
- sparse-matchup fallback is tested;
- output does not imply intent or permanent skill;
- representative-match selection can optionally use residual features.

---

# Phase 9 — Live Client Local Collector

## Outcome

An opt-in local collector reliably records in-game local data and reconciles it with the final Riot match.

## Components

- game process detector;
- endpoint poller;
- event cursor;
- local session store;
- upload/sync worker;
- match reconciler;
- privacy and consent UI.

## Suggested starting cadence

Treat as configurable:
- events and active-player essentials around 1 second;
- broader player/game state around 3–5 seconds.

Do not promise that API values themselves update at exactly one-second resolution.

## Requirements

- local-first failure tolerance;
- SQLite or equivalent queue;
- retry/backoff;
- duplicate protection;
- collector version;
- clear collected-field documentation;
- user deletion control.

## Acceptance criteria

- one full local session can be captured;
- temporary network loss does not lose the session;
- session reconciles to a Riot match or remains explicitly unresolved;
- server ingestion is idempotent;
- no hidden-information claim is made.

---

# Phase 10 — Replay Review Mode

## Outcome

Users can jump from evidence to the relevant replay time and review a match like an analysis broadcast.

## Start small

1. verify replay control integration;
2. seek to a timestamp;
3. synchronize match time;
4. show event and profile overlays;
5. compare representative and deviation checkpoints;
6. add user/coach notes.

## Acceptance criteria

- seek error is measured;
- unavailable replay is handled gracefully;
- evidence survives even when replay is unavailable;
- overlays show observations, not unsupported conclusions.

---

# Phase 11 — Highlight Showcase

## Outcome

Generate data-driven candidate clips and let the user select 2–3 representative highlights.

## Candidate events

- multi-kill;
- solo kill;
- objective steal;
- large advantage swing;
- favorable outnumbered exchange;
- user bookmark.

## MVP storage

Prefer local clips and externally hosted links before building paid video storage.

## Acceptance criteria

- clip windows are configurable;
- users explicitly choose public highlights;
- deletion/privacy controls exist;
- profile does not upload every candidate by default.

---

# Phase 12 — Vision Analysis

## Outcome

Add missing visual context only to already-selected important moments.

## Scope

- HUD parsing;
- minimap icon detection;
- health-bar tracking;
- visible ally/enemy count;
- event context extraction.

## Explicit non-goal

Do not attempt an end-to-end model that judges all LoL decisions from full video.

## Dataset path

```text
recorded video + synchronized game time
→ event-centered clip extraction
→ weak labels from API
→ human correction
→ match-level train/validation/test split
```

## Acceptance criteria

- fixed-environment benchmark first;
- match-level split;
- confidence output;
- safe fallback to API-only analysis;
- no vision-derived intent claim.

---

# 4. Work-package Template

Before implementing a phase, add this to `IMPLEMENTATION_STATUS.md`:

```markdown
## Active Work Package

### Outcome
One externally verifiable result.

### Current implementation
Relevant modules and contracts found in the repository.

### Planned changes
- file/module:
  - responsibility:
  - reason:

### Preserved behavior
Existing features and formulas that must not change.

### Acceptance checks
- [ ] behavior check
- [ ] unit/integration test
- [ ] lint/type/build
- [ ] migration/recovery check
- [ ] domain language review

### Deferred
Items intentionally not implemented.
```

---

# 5. Review Checklist

## Domain review

- Is every conclusion narrower than the available data?
- Is a team-context variable accidentally presented as a team metric?
- Is a style indicator displayed as ability?
- Is “after” incorrectly written as “because of”?
- Is a single match presented as permanent skill?
- Are sample size and confidence visible?
- Can a user reach the supporting match or event?

## Engineering review

- Is this extension consistent with current architecture?
- Is ingestion idempotent?
- Can features be regenerated?
- Are response changes versioned or backward-compatible?
- Are thresholds centralized?
- Are timestamps and sides tested?
- Are model features available at inference time?
- Is the diff limited to the phase?

## Product review

- Does this help an individual user understand and review play?
- Does it avoid team-building and scouting detours?
- Is the result actionable without pretending certainty?
- Does replay evidence add more value than another score?

---

# 6. Recommended First Fable Run

Complete **Phase 0 and Phase 1 only** in one long session.

Why:
- Phase 0 prevents architecture hallucination.
- Phase 1 improves trustworthiness without changing metric formulas.
- Later data and ML work should be based on the real repository audit.

Stop after:
- repository audit;
- evidence-safe response implementation;
- tests;
- status update;
- coherent commits if requested.

Do not begin Phase 2 automatically.
