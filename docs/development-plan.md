# LoL AI Platform Development Plan

> **Superseded (2026-07-07):** the current roadmap lives in
> [master-plan.md](./master-plan.md), which integrates the expansion PRD
> ([PRD-expansion.md](./PRD-expansion.md)), new custom-metric ideas, and the
> replay/vision extension strategy. This file is kept for sprint history.

This plan turns the PDF sprint roadmap into implementation checkpoints that
match the current repository.

## Current Baseline

Sprint 1 is mostly in place:

- Next.js frontend dashboard shell.
- FastAPI backend with health and Riot lookup routes.
- Riot Account-V1, Summoner-V4, and Match-V5 client boundaries.
- PostgreSQL models for summoners, matches, and summoner match summaries.
- Docker Compose stack for PostgreSQL, backend, and frontend.

## Sprint 1: Foundation

Goal: keep the local stack stable enough for Riot API driven development.

Acceptance criteria:

- `docker compose up --build` starts PostgreSQL, FastAPI, and Next.js.
- `/api/v1/health` reports API, database, and Riot key state.
- Riot ID lookup persists summoner profile data.
- Frontend lookup handles loading, success, and error states.

Status: implemented. Keep changes limited to bug fixes unless Sprint 2 exposes
missing foundation work.

## Sprint 2: Timeline Analytics

Goal: ingest Match-V5 timeline data and expose first analysis features.

Implementation checkpoints:

- Add Riot timeline API client method.
- Build a timeline analyzer for per-minute team gold, XP, CS, and objective
  counts.
- Persist timeline feature rows by match and minute.
- Expose a backend endpoint for match timeline analysis.
- Add frontend match selection and a first gold/objective analysis view.

Acceptance criteria:

- Given a match ID, backend returns timeline frames with team totals and
  blue-minus-red diffs.
- Repeated timeline requests refresh stored feature rows without duplicates.
- Frontend can fetch recent match IDs for a summoner and render the selected
  match analysis.

## Sprint 3: Win Probability

Goal: convert timeline features into custom coaching metrics, then layer an
explainable rule-based win probability on top.

Implementation checkpoints:

- Normalize match participants and timeline events.
- Add player skill score storage for match-level analysis outputs.
- Implement Death Cost Index, Throw Index, Objective Setup Score, Lead
  Conversion Score, and Stability Score.
- Return evidence for each high-impact death, objective setup, and lead
  conversion event.
- Add a rule-based win probability predictor after these coaching metrics are
  stable.

Acceptance criteria:

- Backend returns player, scores, and evidence for a selected match and PUUID.
- Risk metrics are clearly marked as worse when higher, while setup/conversion
  metrics are better when higher.
- Evidence copy avoids intent claims and includes confidence.
- Frontend shows risk cards, operating conversion cards, and evidence without
  requiring Vision data.

## Sprint 4: Rank Role Analyzer

Goal: analyze ranked match history by role and recommend the player's strongest
positions.

Implementation checkpoints:

- Classify stored matches by top, jungle, mid, bottom, and support.
- Aggregate common skill scores and role-specific indicators.
- Calculate role fit with sample-size confidence.
- Add rank analysis tabs and recommendation cards to the frontend.

Acceptance criteria:

- Backend returns role fit scores, recent form, and confidence by position.
- Frontend can compare all positions and highlight recommended/caution roles.
- Low-sample roles are not over-ranked without confidence warnings.

## Sprint 5: AI Agent

Goal: generate player-readable match review reports from recent match patterns.

Implementation checkpoints:

- Aggregate recent matches by player, champion, role, and loss patterns.
- Define report sections: summary, recurring risks, improvement focus, and next
  practice goals.
- Add an LLM provider boundary with tool-call friendly structured inputs.
- Keep report generation optional when no AI provider key is configured.

Acceptance criteria:

- Backend can produce a deterministic non-AI report fallback.
- AI report calls are isolated behind one service interface.
- Frontend displays report state, errors, and generated recommendations.

## Sprint 6: Machine Learning

Goal: replace the rule-based predictor with trained model inference.

Implementation checkpoints:

- Build a training dataset from stored timeline features and match outcomes.
- Train and compare Logistic Regression, Random Forest, and XGBoost.
- Export model artifacts and metadata.
- Add SHAP or equivalent feature attribution.

Acceptance criteria:

- Model evaluation is reproducible from committed scripts.
- Backend can serve the selected model behind the same prediction API.
- Rule-based predictor remains available as a fallback.

## Sprint 7: Production

Goal: harden data access, deployment, and operations.

Implementation checkpoints:

- Add Redis caching for Riot API responses.
- Add PostgreSQL indexes for lookup-heavy tables.
- Add scheduled ingestion jobs.
- Add k6 load tests.
- Optimize Docker images and add Nginx reverse proxy.
- Add GitHub Actions CI/CD.

Acceptance criteria:

- CI runs backend and frontend checks.
- Load test thresholds are documented.
- Deployment configuration is environment-driven and secret-safe.

## Expansion: Highlight And Vision Analysis

Goal: add post-game replay assistance after the Riot API based MVP is useful on
its own.

Implementation checkpoints:

- Detect highlight candidates from timeline events and score them.
- Accept uploaded video clips and extract event windows with FFmpeg.
- Sample frames and send them to a Vision provider for minimap, positioning,
  wave, and kiting support signals.
- Keep all Vision claims phrased as evidence-backed possibilities with
  confidence, not certainty.
- Defer local recording agents until upload-based highlights are proven.

Out of scope for MVP:

- Real-time in-game advice.
- Automatic local screen recording.
- Vision-only scoring without Riot API evidence.
