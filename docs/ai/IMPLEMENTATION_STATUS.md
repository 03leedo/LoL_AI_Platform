# Implementation Status

This file is the live handoff between Claude Code sessions.

## Project Goal

Build a professional individual-user LoL analysis platform whose metrics are evidence-backed, context-aware, replay-linked, and honest about uncertainty.

## Current Phase

- Phase: `6 — Evidence-grounded AI agent` **COMPLETE** (domain-reviewed) → next is `7 — Advantage model` (per-minute snapshot dataset, logistic baseline → boosting, temporal/match-grouped splits, calibration report)
- State: `PHASE_7_READY`
- Last updated: `2026-07-14`
- Branch: `main`
- Last commit: see `git log -1`

## Phase Reconciliation (handoff pack ↔ completed milestones M0–M3)

The repo predates this pack. Mapping of `docs/ai/EXECUTION_PLAN.md` phases to what already exists:

| Plan phase | Status | Existing implementation |
|---|---|---|
| 0 Repository audit | ✅ done | `docs/ai/REPOSITORY_AUDIT.md` (generated 2026-07-13) |
| 1 Evidence-safe semantics | ✅ done (2026-07-14) | `services/analysis_semantics.py`: deterministic evidence IDs, observation/limitation/replay_question statements, performance vs risk_style grouping; 우세도 rename + "최근 강세" copy; causal-wording pass enforced by `tests/test_wording_lint.py`; domain reviewer findings applied |
| 2 Versioned data foundation | 🟡 mostly done | + queue_id filter on aggregation reads (2026-07-14, default ranked solo 420); still missing: completeness flags |
| 3 Episode engine | ✅ core done (2026-07-14) | `services/episodes.py` (EPISODE_VERSION 1): time+distance fight clustering, elite availability windows, one-objective↔one-death attribution (METRIC_VERSION 3), objective-analyzable denominator in patterns/autopsy; deferred: episode persistence, consolidated death-context builder, HORDE/Atakhan windows |
| 4 Individual profile v1 | ✅ done (2026-07-14) | `services/profiles.py` (PROFILE_VERSION 1): 5 role-filtered dimensions, recency weighting exp(-days/14), shrinkage n_eff/(n_eff+8) toward cohort mean, local-sample cohort percentiles (explicitly labeled non-tier), submetrics + evidence match ids; `GET /summoner/../profile`; remake filter on aggregation reads |
| 5 Representative/best/deviation matches | ✅ done (2026-07-14) | `services/representative_matches.py` (SELECTION_VERSION 1, rms_distance_0_100_v1): reuses profile per-match formulas, unified deterministic tie-breaks, coverage-first best selection, selections persisted (report_type=selections); UI panel with review links |
| 6 Evidence-grounded AI agent | ✅ done (2026-07-14) | LLM contract v2 (REPORT_VERSION 4): observations require refs from payload ids, numeric-hallucination guard, hypotheses capped, insufficient path, rule-owned strengths/weaknesses, usage logging; tool-calling loop deferred (payload already deterministic) |
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
- Existing test frameworks: pytest (unittest-style), 115 tests passing

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

Phase 6 — Evidence-grounded AI agent hardening: **COMPLETE** (2026-07-14, domain-reviewed).

Delivered (REPORT_VERSION 4, REPORT_PROMPT_VERSION 2):
- LLM contract v2 in `services/reports.py`: output restricted to
  {insufficient?, summary, observations[≤4, refs required], hypotheses[≤3], practice_suggestions[≤3]};
  payload exposes referencable ids (`pat:{key}` + ≤3 match ids per pattern); sanitizer drops unknown
  refs, ref-less observations, and any statement whose numbers (>10) are absent from the payload
  (ratio→percent conversion allowed); a summary failing the guard rejects the whole output → rules
  fallback. Insufficient path surfaces a guarded reason and keeps the deterministic report intact.
- strengths / weaknesses / limitations / replay_questions are rule-owned — LLM output for those
  keys is never read (tested).
- Cost/version observability: both providers log model + token usage; prompt version recorded on
  all LLM-touched content including the insufficient path (review M1/L1 applied).
- Payload privacy: no puuid/riot-id sent; rule draft trimmed to summary only.
- UI: 관측(근거 ref 칩)/가설(확정 아님 라벨) 섹션, AI 서술 생략 사유 표시.

Deferred (recorded): Flash/Thinking model tiering; true tool-calling loop (payload assembly is
already deterministic — the LLM never parses raw timelines).

Phase 6 residual limitations (domain review): numeric guard covers Arabic digits only (한글 숫자
표기는 통과); number existence ≠ semantic binding (진짜 숫자를 엉뚱한 주장에 붙일 수 있음 — 관측은
refs로 완화, 요약/가설 산문은 미바인딩); experiment framing of suggestions is prompt-level only;
hypotheses may carry zero refs (UI 라벨로 완화).

---

Previous package — Phase 5 — Representative / Best / Deviation matches: **COMPLETE** (2026-07-14, domain-reviewed).

Delivered:
- `services/profiles.py`: per-match dimension formulas extracted to module functions
  (`per_match_dimension_values`) — verified behavior-identical; selections reuse them (no parallel math).
- `services/representative_matches.py` (SELECTION_VERSION 1, method rms_distance_0_100_v1):
  eligible = role records with ≥3 computable dimensions (excluded counted); profile vector =
  recency-weighted mean over eligible matches (`profile_vector_basis` recorded — differs from the
  Phase 4 profile which includes low-coverage matches); representative = min RMS distance,
  deviation = max (reason wording: "가장 달랐던", never "최악"), best = coverage-first then highest
  mean (partial-data matches cannot win on fewer dimensions; `dimensions_used` exposed);
  unified deterministic tie-breaks (newer game, then ascending match_id).
- Route `GET /summoner/{name}/{tag}/representative-matches`; selections persisted to
  `analysis_reports` (report_type=selections) with reasons + versions.
- Frontend RepresentativeMatchesPanel: three cards with kind badges, driver rows, review links;
  deviation subtitle states it is not a "worst game" label.
- Domain review findings applied: coverage-first best, tie-break unification + exact-tie test,
  partial-dimension eligible test, method recorded on degenerate path, wording lint now covers
  profiles + representative_matches sources, +.1f diff formatting.

Preserved: profile outputs unchanged; all metric formulas untouched.

---

Previous package — Phase 4 — Individual Profile v1: **COMPLETE** (2026-07-14, domain-reviewed).

Delivered:
- `services/profiles.py` (PROFILE_VERSION 1, constants centralized): dimensions early_growth /
  resource_conversion / **risk_management** (renamed from risk_exposure per review — inverted risk
  composite, `inverted_from` recorded in persisted evidence) / objective_readiness / fight_contribution.
  Recency weighting exp(-days/14); shrinkage reliability = n_eff/(n_eff+8) with n_eff=(Σw)²/Σw² so
  stale games don't inflate confidence; baseline = cohort mean only when cohort ≥30 valid values.
- Local-sample cohort from stored `match_participants` (`fetch_cohort_participant_stats`) —
  labeled "티어 미구분 임시 기준"; dimension-level percentile only where the identical formula runs
  on cohort rows (early_growth, resource_conversion); mean-vs-single-game caveat disclosed in
  comparison_group. Remake filter (≥300s) on both player-record and cohort reads.
- Review H1 fixed: player records now carry damage/gold/duration so resource_conversion works on
  real data (fixture aligned with the repository contract).
- Route `GET /summoner/{name}/{tag}/profile?window&queue&role` (queue_label derived from queue);
  aggregates persisted as `profile.*` rows with computed_at_ms for regenerability.
- Frontend PlayerProfilePanel: role chips, percentile bars, shrinkage note (표본 보정 전 N점),
  submetric drill-down, "고정 실력이 아님/로컬 표본" disclaimers.

Preserved: all existing metric formulas; scorecard/role-fit endpoints unchanged.

---

Previous package — Phase 2 gap + Phase 3 episode engine: **COMPLETE** (2026-07-14, domain-reviewed twice).

Delivered:
- `services/episodes.py` (EPISODE_VERSION 1, thresholds centralized): fight clustering by ≤20s AND
  ≤3500u (missing positions merge by time with `confidence: medium`), elite availability windows
  (dragon 5:00/+5:00, baron 20:00/+6:00, herald 8:00–~19:55 — patch-approximate, disclosed),
  objective→death attribution (nearest preceding death within 90s, one objective charged once).
- Death Cost / Throw Index consume deduplicated attribution; teamfight detection uses the shared
  builder → METRIC_VERSION 3. Regression test: 4 deaths + 1 dragon = 48pts (was 96).
- patterns/autopsy: objective-linked share now uses the analyzable-death denominator with
  elite-set-consistent numerator; stat shows 분석 가능/전체 both. Legacy contexts fall back to
  all-analyzable explicitly.
- Aggregation queue filter (default 420; `queue=0` disables) on rank-analysis/report; report cache
  key gains `q{queue}`; REPORT_VERSION 3. UI copy says "최근 솔로랭크 N경기 기준".
- Frontend: autopsy chip shows "(분석 가능 N회 기준)" and renders "분석 가능 데스 없음" instead of 0%.
- Second domain review findings applied (elite-set numerator filter, empty-denominator display,
  unconditional approximation disclosure, meaningful symmetry test).

Previous phase (1 — evidence-safe semantics) record retained below in git history (commit 40cc3f1).

Delivered:
- `services/analysis_semantics.py` — deterministic evidence IDs (`ev:{match}:{type}:{minute}:{n}`),
  statement layer (observation / limitation / replay_question), performance|risk_style grouping with
  direction-based fallback for unregistered metrics; applied in review/analysis routes and ingest.
- Causal/judgmental wording removed from `habit_metrics`, `patterns`, `custom_metrics` (titles only —
  formulas untouched, METRIC_VERSION unchanged); enforced by `tests/test_wording_lint.py`
  (fixture-level + source-level lint).
- Reports: `limitations` + `replay_questions` (rule-generated; LLM cannot overwrite them);
  REPORT_VERSION 1→2 invalidates stale caches.
- Frontend: 우세도 rename (승률 없음, API 필드는 유지), score cards split into
  퍼포먼스 지표 / 위험·스타일 신호 sections, "최근 강세" badge + footnote, 복기 질문/데이터 한계 sections.
- Domain review: NEEDS_CHANGES → all findings applied (false shrinkage claim fixed, direction-based
  group fallback, lint gaps closed, death-zone hypothesis softened, unknown-score limitations,
  neutral-placeholder leak fixed).

### Preserved behavior

- All 9 metric formulas byte-identical (string literals only changed).
- API responses additive-only (`group`, `id`, `statements`, `limitations`, `replay_questions`).

### Acceptance checks

- [x] observation cannot reference nonexistent evidence (test)
- [x] causal wording lint (fixtures + module sources)
- [x] unknown/low-confidence produces limitation statements (test)
- [x] advantage naming (우세도) in all user-facing copy
- [x] 115 pytest + frontend tsc pass
- [x] domain reviewer run and findings applied

### Deferred

- Full 한글화 of evidence titles/descriptions (currently English; statements mix languages).
- Hypothesis-kind statements (only observation/limitation/replay_question emitted so far).

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
| 2026-07-14 | `pytest` | 115 passed | + analysis semantics, wording lint (fixture+source) |
| 2026-07-14 | frontend tsc --noEmit | pass | Phase 1 UI regroup/rename |
| 2026-07-14 | `pytest` | 129 passed | + episodes (clustering/availability/attribution/dedup regression) |
| 2026-07-14 | frontend tsc --noEmit | pass | autopsy chip + queue copy |
| 2026-07-14 | `pytest` | 138 passed | + profiles (role filter, shrinkage, recency, cohort fallbacks) |
| 2026-07-14 | frontend tsc --noEmit | pass | PlayerProfilePanel |
| 2026-07-14 | `pytest` | 147 passed | + selections (determinism, ties, coverage, positive deviation) |
| 2026-07-14 | frontend tsc --noEmit | pass | RepresentativeMatchesPanel |
| 2026-07-14 | `pytest` | 153 passed | + LLM contract v2 sanitizer (refs, numeric guard, caps, fallback) |
| 2026-07-14 | frontend tsc --noEmit | pass | report 관측/가설 sections |

## Changed Files in Current Phase

Phase 1: `backend/app/services/analysis_semantics.py` (new), wording edits in `custom_metrics.py` /
`habit_metrics.py` / `patterns.py`, `reports.py` (limitations/replay_questions, REPORT_VERSION 2),
`schemas/riot.py` (additive), routes/ingest wiring; frontend regroup/rename files;
`tests/test_analysis_semantics.py`, `tests/test_wording_lint.py` (new).

## Remaining Risks

- Elite spawn rules are patch-approximate: herald timing matches pre-14.x (recent patches shift with
  void grubs), HORDE/Atakhan windows unmodeled, elder respawn approximated by the dragon chain —
  analyzable classification drifts on current-patch matches (disclosed in user-facing copy).
- Availability windows end open (`+inf`) for never-taken objectives → late deaths stay "analyzable".
- Legacy stored histories without `elite_objectives` use the all-deaths fallback denominator until
  matches are re-ingested (mixed denominator semantics across data ages).
- Objective→death attribution is time-only (no spatial link to the pit).
- Episode `confidence` (medium on missing positions) computed but not yet surfaced in UI.
- Profile cohort = whoever appears in locally ingested matches (biased toward requesting users'
  MMR neighborhoods, tier unknown — labeled); percentile compares a multi-game mean against a
  single-game distribution (disclosed); risk/objective/fight dimensions have submetric percentiles
  only; challenges keys can be absent on older matches → per-dimension insufficient_data.
- **Shrinkage inconsistency**: profiles use n_eff/(n_eff+8); legacy scorecard/pattern averages
  remain plain means (their limitation copy says so) — full unification deferred.
- Statement layer language mix (English evidence + Korean limitations) — cosmetic, deferred.
- Gemini thinking models may consume output budget on reasoning; MAX_OUTPUT_TOKENS raised to 4000, sanitizer falls back to rules on truncation.

## Next Action

Phase 7 — Advantage model: reproducible per-minute snapshot dataset builder from stored
`match_timeline_features`, logistic-regression baseline, temporal + match-grouped splits,
calibration report (Brier/ECE/reliability curve); gradient boosting only if it beats the baseline.
Keep the 우세도 label and the heuristic curve until validation passes documented thresholds.
Note: local match volume is small — the deliverable is the validated pipeline + honest report;
model replacement happens only if metrics justify it.

Earlier phase limitations remain recorded above (Phase 5 best/risk_management mean, selection
profile-vector basis; Phase 6 numeric-guard scope).
