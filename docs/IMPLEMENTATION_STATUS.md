# Implementation Status

This file is the live handoff between Claude Code sessions.

## Project Goal

Build a professional individual-user LoL analysis platform whose metrics are evidence-backed, context-aware, replay-linked, and honest about uncertainty.

## Current Phase

- Phase: `0 — Repository Audit` **COMPLETE** (see `docs/REPOSITORY_AUDIT.md`) → next is `1 — Evidence-safe Analysis Semantics`
- State: `PHASE_1_READY`
- Last updated: `2026-07-13`
- Branch: `main`
- Last commit: see `git log -1` (M0–M3 milestones complete and pushed)

## Phase Reconciliation (handoff pack ↔ completed milestones M0–M3)

The repo predates this pack. Mapping of `docs/FABLE_EXECUTION_PLAN.md` phases to what already exists:

| Plan phase | Status | Existing implementation |
|---|---|---|
| 0 Repository audit | ✅ done | `docs/REPOSITORY_AUDIT.md` (generated 2026-07-13) |
| 1 Evidence-safe semantics | ❌ **next** | evidence has `{value, confidence, direction}` but no evidence IDs, no observation/hypothesis/limitation/replay-question separation; "승률"·"추천 포지션" naming pending |
| 2 Versioned data foundation | 🟡 mostly done | raw JSONB (`riot_matches`, `riot_match_timelines`), `metric_version` on `metric_scores`, idempotent-ish ingestion (merge / delete+insert); missing: completeness flags, evidence lineage IDs |
| 3 Episode engine | 🟡 partial | fight clustering in `habit_metrics._detect_teamfights`; no persisted episodes, no objective-analyzable denominator, Death Cost can double-count one objective across deaths |
| 4 Individual profile v1 | 🟡 partial | `scorecard.py` (6 abilities) + `role_analyzer.py` (shrinkage); no cohort percentiles, no recency weighting |
| 5 Representative/best/deviation matches | ❌ | not started |
| 6 Evidence-grounded AI agent | 🟡 partial | `reports.py` + `llm_provider.py` (Gemini via OpenAI-compat); patterns rule-computed, LLM prose-only; missing evidence-ID enforcement and tool-based access |
| 7 Advantage model | 🟡 v0 | rule-based logistic curve (`win_probability.py`); UI still says "승률" — rename in Phase 1; ML + calibration pending |
| 8 Expected-performance models | ❌ | not started |
| 9 Live Client collector | ❌ | planned as companion C1 (see master-plan §7.4) |
| 10 Replay review mode | ❌ | planned as companion C2 / 리플레이 시어터 |
| 11 Highlight showcase | ❌ | planned as C3 (YouTube embed + R2 hybrid decided) |
| 12 Vision analysis | ❌ | last, per plan |

Also completed outside the plan's numbering: kill/death heatmap + death zones, turning points, rank lookup, background ingestion jobs, cross-match pattern mining + death autopsy (these feed Phases 1/3/4).

## Repository Facts

- Backend: FastAPI (async), `backend/app/`
- Frontend: Next.js 15 App Router, React 19, Tailwind, `frontend/src/`
- Database: PostgreSQL 16, JSONB raw + normalized tables
- ORM/query layer: SQLAlchemy 2 (async) + asyncpg
- Worker/queue: asyncio background tasks (`services/ingest.py`, `ingest_jobs` table); Redis/Celery not yet
- ML tooling: none yet (planned Phase 7/8)
- Local app: none yet (companion C1–C3 planned)
- Package managers: pip (backend/.venv), pnpm (frontend; runs in Docker)
- Runtime versions: Python 3.12 (WSL venv), Node 24 (Windows host, for tsc only), containers via Docker Compose
- Deployment: local Docker Compose only; CI/CD pending (old M5)
- Existing Claude instructions: `CLAUDE.md` (this pack, merged with repo facts)
- Existing migrations: Alembic 0001–0004
- Existing test frameworks: pytest (unittest-style), 102 tests passing

## Verified Commands

```text
install:   (backend) backend/.venv/bin/pip install -r backend/requirements.txt
dev:       docker compose up --build        # postgres + backend :8000 + frontend :3000
test:      backend/.venv/bin/python -m pytest      # from repo root; pytest.ini sets pythonpath
lint:      (none configured yet)
typecheck: cd frontend && node node_modules/typescript/bin/tsc -p tsconfig.json --noEmit
build:     docker compose build
migration: cd backend && alembic upgrade head      # offline: alembic upgrade head --sql
```

WSL note: run shell work via `wsl.exe -d ubuntu-24.04 --cd /home/doheon/projects/LoL_AI_Platform -- bash tmp/<script>.sh`.

## Current Feature Inventory

| Feature | Status | Main files | Tests | Notes |
|---|---|---|---|---|
| Riot match ingestion | done | `services/riot_client.py`, `services/match_data.py`, `repositories/matches.py` | test_riot_client_retry, test_match_data | rate-limited (18/s, 95/120s), DB-first cache |
| Timeline ingestion | done | same + `services/timeline_analyzer.py` | test_timeline_analyzer | per-minute features; final-frame minute dedupe fixed 2026-07-13 |
| Existing indicators | done (9) | `services/custom_metrics.py`, `services/habit_metrics.py` | test_custom_metrics, test_habit_metrics | see indicator map below |
| Match analysis UI | done | `frontend/src/app/match/[matchId]/`, `components/review/*` | tsc | score cards, win curve, turning points, evidence minimap |
| Player profile | partial | `services/scorecard.py`, `services/role_analyzer.py`, `RankAnalysisPanel.tsx` | test_scorecard, test_role_analyzer | no cohort percentiles yet |
| Pattern mining / report | done | `services/patterns.py`, `services/reports.py`, `PlayerReportPanel.tsx` | test_patterns, test_reports | rules compute, LLM narrates, cached |
| Gemini integration | done | `services/llm_provider.py`, `services/llm_feedback.py` | test_llm_provider, test_llm_feedback | OpenAI-compat endpoint, model gemini-3.5-flash |
| Heatmap / death zones | done | `services/heatmaps.py`, `SummonerHeatmap.tsx` | test_heatmaps | zone labels are coarse approximations |
| Background ingestion | done | `services/ingest.py`, `ingest_jobs` | (covered indirectly) | LLM disabled in batch |
| Replay support | none | — | — | companion C2 planned |
| ML models | none | — | — | Phase 7/8 |

## Existing Indicator Map

All 0–100 clamped, `{value, confidence, direction}` + evidence list. Formulas documented from code.

| Indicator | Input data | Formula/module | Output/API | Known issues | Preserve in Phase 1 |
|---|---|---|---|---|---|
| Death Cost | deaths + enemy objectives ≤90s + gold state | `custom_metrics._death_cost_index` | scores.death_cost_index | all-deaths denominator; one objective can count for several deaths (fix = Phase 3) | yes |
| Throw Index | deaths while ahead >1000g, 90s gold swing | `custom_metrics._throw_index` | scores.throw_index | — | yes |
| Objective Setup | major objectives ± ally deaths 90s before | `custom_metrics._objective_setup_score` | scores.objective_setup_score | — | yes |
| Lead Conversion | 10/15min lead → 15–25min conversions | `custom_metrics._lead_conversion_score` | scores.lead_conversion_score | null when no lead (by design) | yes |
| Stability | 100 − 0.6·DeathCost − 0.4·Throw | `custom_metrics` | scores.stability_score | meta-score; direction mixing on screen (Phase 1 grouping) | yes |
| Gold Retention | frames currentGold streaks ≥1500g, wallet deaths ≥1300g | `habit_metrics._gold_retention` | scores.gold_retention_score | ±60s frame granularity (labeled) | yes |
| Gambler Index | shutdown conceded, isolated deaths (≥4000u), deep kills/deaths | `habit_metrics._gambler_index` | scores.gambler_index | style signal shown as higher_is_worse — regroup as 위험·스타일 in Phase 1 | yes |
| Teamfight Persistence | kill clusters (≥3 kills/20s/≥4 people), damage share deltas | `habit_metrics._teamfight_persistence` | scores.teamfight_persistence_score | frame-delta damage share is coarse (labeled low/medium) | yes |
| Death Acceleration | death chains within 5min | `habit_metrics._death_acceleration` | scores.death_acceleration_index | wording must stay observational (Phase 1) | yes |

Additional outputs: win curve (`win_probability.py` — rename 승률→우세도 in Phase 1), turning points (`turning_points.py`), heatmap zones (`heatmaps.py`), patterns + autopsy (`patterns.py`), scorecard + role fit.

## Active Work Package

### Outcome

Phase 1 — Evidence-safe analysis semantics (not yet started; file-level plan in `docs/REPOSITORY_AUDIT.md` §9).

### Preserved behavior

- Existing user changes.
- Existing metric calculations unless an active task explicitly changes them.
- Existing public API behavior unless a migration is documented.

### Acceptance checks

- [x] repository audit complete
- [ ] Phase 1 file-level plan confirmed at implementation start
- [ ] tests identified
- [x] user changes protected

### Deferred

All phases after the active one.

## Decisions

| Date | Decision | Reason | Consequence |
|---|---|---|---|
| 2026-07-07 | 3-tier data strategy: API → replay companion → vision; Moment as shared unit | differentiation + extension seams | source/confidence upgrade instead of schema churn |
| 2026-07-07 | metric_scores long-format with metric_version; raw JSONB preserved | recompute without re-fetch | formula changes = version bump + batch recompute |
| 2026-07-08 | LLM narrates only; rules compute all numbers/patterns | hallucination control, cost | reports fall back to rules without a key |
| 2026-07-08 | Companion track C1(live collector)→C2(replay CV)→C3(clips/showcase); broadcast idea reinterpreted as replay theater | policy/licensing/effort | E-numbering superseded |
| 2026-07-08 | Highlight hosting: YouTube embed first, R2 later | cost | quota/audit caveats documented |
| 2026-07-13 | Adopt handoff pack (this spec/plan/status + CLAUDE.md + domain reviewer) | analysis-quality upgrade | roadmap governance moves here; master-plan stays as history/arch reference |
| 2026-07-13 | Individual-user focus; no team-fit or roster metrics | product scope | team data is context only |

## Assumptions

| Assumption | Evidence | Risk if wrong | How to verify |
|---|---|---|---|
| Gemini OpenAI-compat endpoint remains available for the free key | HTTP 200 test call 2026-07-13 (`gemini-3.5-flash`) | reports fall back to rules | provider error logs |
| Dev auto-create tables coexists with Alembic until M5/prod | current startup behavior | schema drift in prod | switch prod to alembic-only |

## Blockers

None. (Riot Personal App approval still pending — dev key rotation every 24h until then.)

## Test Results

| Date | Command | Result | Notes |
|---|---|---|---|
| 2026-07-13 | `pytest` | 102 passed | includes timeline minute-dedupe regression test |
| 2026-07-13 | frontend tsc --noEmit | pass | |
| 2026-07-13 | alembic upgrade head --sql | pass (offline) | |

## Changed Files in Current Phase

Phase 0 deliverables only: `docs/REPOSITORY_AUDIT.md`, this file, `CLAUDE.md`, pack docs copied. Plus bugfix `services/timeline_analyzer.py` (+ regression test) found during audit.

## Remaining Risks

- Death Cost objective double-counting until the Phase 3 episode engine.
- Objective-linked death share uses all deaths as denominator (Phase 3 predicate fix; wording softened in Phase 1).
- "승률/추천 포지션" labels overstate certainty until Phase 1 rename.
- Gemini thinking models may consume output budget on reasoning; MAX_OUTPUT_TOKENS raised to 4000, sanitizer falls back to rules on truncation.

## Next Action

Start Phase 1 (evidence-safe analysis semantics) using the file-level plan in `docs/REPOSITORY_AUDIT.md` §9.
