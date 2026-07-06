# LoL AI Platform Development Plan

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

Goal: convert timeline features into an explainable rule-based win probability.

Implementation checkpoints:

- Add a rule-based predictor using gold, XP, CS, objectives, game time, and side.
- Store prediction points per match and minute.
- Render win probability over time beside the timeline chart.
- Add test fixtures for deterministic predictor behavior.

Acceptance criteria:

- Backend returns a probability series between 0 and 1 for each analyzed frame.
- The response includes feature contributions or simple explanations.
- Frontend shows probability changes without requiring ML infrastructure.

## Sprint 4: AI Agent

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

## Sprint 5: Machine Learning

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

## Sprint 6: Production

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
