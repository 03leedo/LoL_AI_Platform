# CLAUDE.md — LoL Player Insight Platform

## Mission
Build a professional, evidence-based LoL analysis platform for **individual users**.

The product must:
- collect and normalize match data;
- derive explainable individual-performance signals;
- find repeated patterns and replay-worthy moments;
- connect conclusions to evidence;
- optionally explain results with AI;
- never pretend incomplete data reveals player intent.

## Read First
At the start of a task:

1. Read `docs/IMPLEMENTATION_STATUS.md` (live progress, single source of truth).
2. Read the relevant phase in `docs/FABLE_EXECUTION_PLAN.md`.
3. Read only the relevant sections of `docs/PRODUCT_ANALYSIS_SPEC.md`.
4. Inspect the current repository (`docs/REPOSITORY_AUDIT.md` maps it) before proposing file changes.

Document map:
- `docs/IMPLEMENTATION_STATUS.md` — live phase status and decisions.
- `docs/FABLE_EXECUTION_PLAN.md` — forward phase plan (Phases 0–12).
- `docs/PRODUCT_ANALYSIS_SPEC.md` — domain reference v3 (analysis methodology).
- `docs/REPOSITORY_AUDIT.md` — architecture and indicator-to-file map.
- `docs/master-plan.md` — completed milestones M0–M3 history, architecture rationale,
  data-reality notes (Riot API가 주는 것/안 주는 것). Roadmap governance moved to the
  execution plan; this file remains the architectural reference.
- `docs/PRD-expansion.md`, `docs/PRD-expansion-2.md` — historical product specs.

## Repository Facts (verified 2026-07-13)
- Backend: FastAPI + SQLAlchemy(async) + asyncpg, `backend/app/{api,core,models,repositories,schemas,services}`.
- Frontend: Next.js 15 App Router + React 19 + Tailwind, `frontend/src/{app,components,lib}`. Korean UI.
- DB: PostgreSQL 16 (JSONB raw payloads + normalized tables). Redis planned (M5), not yet used.
- Migrations: Alembic (`backend/migrations/`, revisions 0001–0004). Dev also auto-creates tables on startup.
- LLM: provider layer `backend/app/services/llm_provider.py` — any OpenAI-compatible endpoint or Anthropic.
  Currently configured for Gemini via its OpenAI-compat API. The LLM writes prose only;
  all numbers/patterns are rule-computed (`patterns.py`, `reports.py`).
- Dev environment: repo lives in WSL (`ubuntu-24.04`); Windows-side sessions run WSL commands via
  `wsl.exe -d ubuntu-24.04 --cd /home/doheon/projects/LoL_AI_Platform -- bash tmp/<script>.sh`
  (write scripts to gitignored `tmp/` to avoid quoting issues).
- Commands:
  - test: `backend/.venv/bin/python -m pytest` (config in `pytest.ini`, pythonpath=backend; tests in `tests/`)
  - typecheck (frontend): `cd frontend && node node_modules/typescript/bin/tsc -p tsconfig.json --noEmit`
  - run stack: `docker compose up --build` (postgres + backend :8000 + frontend :3000)
  - migrations: `cd backend && alembic upgrade head` (offline check: `--sql`)
- Conventions: evidence/metric internals in English, user-facing UI text in Korean;
  metric scores follow `{value, confidence, direction}` + evidence; long-format storage in
  `metric_scores` with `metric_version` (bump on formula change; raw JSONB allows recompute).

## Product Scope
### In scope
- individual match performance;
- role-, patch-, tier-, champion-, and matchup-aware comparison;
- early-game expected performance;
- individual resource share and conversion;
- fight outcome contribution;
- risk exposure;
- objective readiness;
- consistency and improvement tracking;
- representative, best, and profile-deviation matches;
- replay checkpoints;
- optional AI explanation and coach review;
- pro-match data as a benchmark or research dataset.

### Out of scope
- team-fit scores;
- roster recommendations;
- player-synergy scores;
- jungle-support or ADC-support proximity as an ability score;
- leadership, mentality, shot-calling, or communication scores;
- definitive "good death / bad death" labels without reviewed evidence;
- vision analysis before the final roadmap phase;
- real-time in-game advice (collection may be live; analysis is post-game only).

Team gold, team damage, objectives, and match outcome may be used only as context, denominators, or model inputs for individual analysis.

## Domain Invariants
1. Separate:
   - observation;
   - hypothesis;
   - limitation;
   - replay question or practice suggestion.

2. Never convert correlation into causation.
   - Avoid: "This death caused dragon loss."
   - Prefer: "Dragon loss was observed 47 seconds after this death."

3. Preserve existing metric formulas unless the active task explicitly changes them.
   Existing metrics should first be moved into evidence/submetric roles, not deleted or reimplemented.

4. A single match score is not permanent skill.
   Long-term profiles require role filtering, sample-size handling, recency weighting, and uncertainty.

5. Do not mix pro and solo-queue records in one model without an explicit domain-separation design.

6. Every generated analysis sentence containing a factual claim must be traceable to evidence IDs or source records.

7. Low-confidence analysis must allow `unknown` or `needs_replay_review`.

8. Before a win-probability model is calibrated and validated, label the result `advantage` (우세도) rather than `win probability` (승률).

## Agent Workflow
Use an outcome-oriented approach inside one bounded phase.

Before editing:
- run `git status`;
- identify existing user changes;
- inspect build, test, lint, migrations, and architecture;
- write or update the file-level plan in `docs/IMPLEMENTATION_STATUS.md`;
- avoid broad rewrites when existing modules can be extended.

During implementation:
- complete only the active phase;
- make the smallest coherent architectural change;
- reuse current conventions and libraries;
- add tests with each behavior change;
- keep database and API changes backward-compatible when practical;
- record assumptions and decisions.

After implementation:
- run the relevant tests, lint, type checks, and build;
- review the diff for scope creep;
- run the domain reviewer (`.claude/agents/domain-reviewer.md`) after analysis-semantics changes;
- update `docs/IMPLEMENTATION_STATUS.md`;
- summarize changed files, tests, remaining risks, and next phase;
- do not begin the next phase automatically.

## Repository Safety
- Never overwrite or discard pre-existing uncommitted user changes.
- Never edit generated, vendor, lock, or migration-history files without a clear reason.
- Do not replace the current stack merely because another stack is listed in the product plan.
- Do not create a parallel architecture when equivalent services already exist.
- Do not silently change public API response meanings.
- Destructive schema changes require a migration and rollback path.
- If credentials, API keys, or personal data are found, do not print or commit them.

## Data and Feature Rules
Maintain these logical layers even if names differ:

1. raw source data (`riot_matches.raw_json`, `riot_match_timelines.raw_json`);
2. normalized match/participant/event records;
3. derived episodes and features;
4. versioned profile/model output (`metric_scores`, `analysis_reports`);
5. evidence and explanation (`moments`, evidence payloads).

Derived values must record:
- feature or rule version;
- source IDs;
- confidence/completeness;
- calculation time.

Feature generation must be deterministic and rerunnable from stored source data.

## ML Rules
Do not replace a clear rule with ML without a measurable reason.

For every model:
- define the prediction target;
- define one row of training data;
- list features available at inference time;
- prevent match-level leakage;
- split by time and match ID;
- compare with a simple baseline;
- evaluate calibration for probabilities;
- report performance by role, patch, and relevant cohort;
- version artifacts and feature definitions;
- keep pro and solo-queue models separate.

Do not claim model accuracy means player-skill accuracy.

## LLM Rules
The LLM must not calculate authoritative metrics from raw timelines.

It receives structured, already-computed evidence and may:
- summarize;
- compare representative and deviation matches;
- organize hypotheses;
- create replay questions;
- suggest a limited practice experiment.

It must not invent numeric values or hidden game state.

Preferred structured output:
- `observations`
- `hypotheses`
- `limitations`
- `replay_checkpoints`
- `practice_suggestions`

## Quality Gates
A task is complete only when:
- acceptance criteria pass;
- relevant tests pass;
- behavior is documented;
- no existing feature is unintentionally removed;
- evidence language follows domain invariants;
- implementation status is updated.

If a relevant test suite does not exist, add the smallest useful test harness instead of claiming verification.

## Git
- Prefer 1–4 coherent commits per phase, on `main` per current solo workflow.
- Commit messages should explain intent, not only file names.
- Push only when the user asks (established rhythm: user approves push per milestone).

## Blockers
Do not ask questions that repository inspection can answer.

Pause and report a blocker only when:
- required credentials or external access are missing;
- two product rules materially conflict;
- a destructive migration requires a product decision;
- a legal/API-policy constraint prevents the requested behavior;
- user-owned uncommitted changes make safe progress impossible.

Otherwise, make the safest reasonable assumption, record it, and proceed within the active phase.
