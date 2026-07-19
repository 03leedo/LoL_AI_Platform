# Implementation Status

This file is the live handoff between Claude Code sessions.

## Project Goal

Build a professional individual-user LoL analysis platform whose metrics are evidence-backed, context-aware, replay-linked, and honest about uncertainty.

## Current Phase

- Phase: `9 — Live Client collector (C1)` **CORE DONE** (2026-07-19) — companion script + upload/reconcile API verified end-to-end; awaiting first real-game collection on the user's PC
- State: `PHASE_9_CORE_DONE`
- Last updated: `2026-07-18`
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
| 6 Evidence-grounded AI agent | ✅ done (2026-07-14, +hardening 2026-07-18) | LLM contract v2 (REPORT_VERSION 5): observations require refs from payload ids, numeric-hallucination guard incl. Korean numeral notation, hypotheses capped, insufficient path, rule-owned strengths/weaknesses, usage logging; tool-calling loop deferred (payload already deterministic) |
| 7 Advantage model | ✅ pipeline done (2026-07-18) | `app/ml/` (DATASET_VERSION 1, MODEL_VERSION 1): snapshot dataset from raw timelines, temporal match-grouped split, pure-Python logistic + calibration report, adoption gate → verdict keep_heuristic on 40 local matches; serving stays `win_probability.py` heuristic until gate passes |
| 8 Expected-performance models | ✅ pipeline done (2026-07-18) | `app/ml/expected_performance.py` (EXPECTED_VERSION 1): GD/CSD/XPD@10 lane differentials, grouped-average baselines (zero/role/role_side, train-only fit, small-group fallback), residual = actual − expected; verdict report_only on 40 local matches — nothing user-facing |
| 9 Live Client collector | 🟢 core done (2026-07-19) | `companion/live_collector.py` + `/api/v1/live/*` (idempotent upload, final-match reconciliation); LCU pick/ban + metric merge deferred; awaiting first real-game run |
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

## ML Improvement Backlog (recorded 2026-07-18, after Phase 7)

Ordered by expected impact; each is an explicit versioned change, never a silent edit.

1. **Data volume** — the binding constraint (40 usable matches). Grow ingestion before model work:
   every gate threshold assumes ≥300 matches. Re-run `train_advantage` periodically; keep every
   report in `docs/ml/reports/` so progress is comparable across volumes.
2. **DATASET_VERSION 2** — exclude each match's terminal frame (or last N seconds) from training/
   eval, or add per-time-bucket criteria to the adoption gate: terminal frames nearly encode the
   label, so aggregate metrics are optimistic and a bad-mid-game model could pass the gate.
3. **Per-bucket adoption gate** — coaching value lives in mid-game (10–29분) calibration; require
   bucket-level ECE/Brier thresholds, not only aggregate.
4. **Recalibration layer** — if the raw model stays miscalibrated at volume (ECE > threshold but
   AUC clearly better), add Platt/isotonic recalibration fitted on a held-out calibration slice
   before rejecting it outright.
5. **Feature extensions (needs volume)** — elite sub-types (elder/soul point), inhibitors,
   baron-buff-active window, side, patch; champion composition much later. Each = FEATURE bump +
   dataset version bump.
6. **Boosting** — only after logistic is beaten on held-out data (MODEL_RULES); revisit the
   no-numpy decision at that point. **Binding tuning rule (2026-07-19 review):** all future
   hyperparameter/model selection uses a temporal validation slice carved from train — never
   the gate's test split (the current test window is not selection-clean after the convergence
   probe); an `adopt` verdict must additionally be confirmed on matches ingested after the
   last tuning date.
7. **Patch calibration is currently trivial** — all local matches share one patch; becomes
   meaningful (and a required check) once data spans patches.
8. **Phase 6 guard leftovers** (low priority, fail-safe directions recorded): 할푼 fraction,
   한자 numerals, idiom availability cost (백배/백 번), summary/hypothesis prose number binding.

## Active Work Package

### Outcome

Phase 9 — Live Client collector (C1, master-plan §7.4 + docs/phases/PHASE_09_12_LATER.md):
opt-in, collection-only companion for the user's own games; local queue; idempotent sync;
final-match reconciliation. No in-game exposure ever (PRD §19.3).

Delivered (2026-07-19):
- `companion/live_collector.py` (c1-0.1.0, Python stdlib only — no installs beyond Python):
  polls `https://127.0.0.1:2999/liveclientdata/allgamedata` (1s default, configurable), compacts
  to C1 scope (my health/gold/stats + deduped events), buffers in local SQLite, uploads AFTER
  the game in 500-row batches with retry/backoff; unuploaded games re-upload on next start;
  `companion/README.md` = install/run guide (user's PC).
- Backend: `live_sessions`/`live_snapshots` tables (alembic 0005 + dev auto-create),
  `POST /api/v1/live/sessions/{id}/snapshots` (idempotent — (session,seq) conflicts ignored),
  `POST .../complete` (conservative reconciliation: riot id + game_creation window
  [start−45m, start+10m], links only a single unambiguous candidate), `GET .../{id}`.
- Verified end-to-end against the running backend: batch accepted, duplicate retry accepted=0,
  complete → `reconciled` with the real stored match id (synthetic sessions removed after test).
- 10 new tests (riot-id parsing, reconcile 0/1/ambiguous/no-start, snapshot compaction + event
  dedup, game-start estimate); pytest pythonpath now includes repo root for companion imports.
- Deferred (recorded): LCU pick/ban collection (틸트 지표 정밀화), merge of live snapshots into
  analysis metrics (needs schema for health-based gambler refinement), packaged .exe.

Not domain-reviewed: collection infrastructure only; no analysis semantics or metric changes.

---

Previous package — Advantage model iteration v2 (backlog items 2+5): DATASET_VERSION 2 — exclude each match's
terminal frame (removes the near-label-encoding optimism disclosed in Phase 7 review) and add
minute-interaction features (gold/xp diff × game-time weight — the exact axis where the
hand-tuned heuristic wins). Single feature-derivation helper shared by training and any future
serving path (parity). Heuristic stays in production unless the documented gate passes.

Delivered (2026-07-19):
- DATASET_VERSION 2 in `advantage_dataset.py`: `features[:-1]` terminal-frame exclusion;
  `derived_feature_values`/`full_feature_row` compute `gold_diff_x_time`/`xp_diff_x_time`
  (× min(1.5, 0.5+m/30)) at vectorization time — rows never store them, so training and
  inference share one derivation point; old v1 artifacts stay readable.
- Convergence probe: 1500@0.1 was underfit; constants bumped to 5000 epochs, lr 0.3 (plateau;
  train≈test loss → capacity-limited, not overfit). Canonical record:
  `docs/ml/reports/convergence_probe_2026-07-19.json`. Gate caveat: the probed test window is
  no longer selection-clean — binding forward tuning rule recorded (backlog 6 + model doc).
- Retrained at n=526 on dataset v2: model now beats the heuristic on log loss (0.5690 vs
  0.5728) and ECE (0.042 vs 0.046); trails ONLY on Brier (0.1956 vs 0.1943) → verdict
  keep_heuristic with a single remaining criterion. Result-history table added to
  ADVANTAGE_MODEL.md; report `advantage_v2_2026-07-19_n526.json`.
- Remaining ceiling is linear capacity → next candidate is boosting (backlog 6), adopted only
  if it beats BOTH the logistic and the heuristic on the same gate.
- 3 new tests (terminal-frame exclusion, single-frame match, derived interactions); 213 pass.

---

Previous package — Data volume expansion (backlog item 1): backfill derived tables from stored raw timelines
(no API), cohort snowball collector seeded from stored participants (dedupe, cap, rate-limit
respectful, key-expiry abort), lookup ingest cap 30→100. Team/cohort matches are denominators
and model inputs only — no team-fit analysis.

Delivered (2026-07-18):
- `backend/app/services/match_collector.py`: `--backfill` recomputes participants/events/
  timeline features from stored raw payloads (zero API calls); collection mode snowballs from
  registered summoners then recent stored participants, skips already-stored/duplicate matches,
  caps new ingests, tolerates per-match/per-seed failures, and aborts cleanly on 401/403
  (dev-key rotation) instead of hammering the API. Reuses `ingest_single_match` — no parallel
  ingestion path.
- Lookup ingest route cap 30→100 (Riot single-page max; ~200 calls per 100-match job under the
  client limiter).
- **Backfill executed**: 48/48 matches restored into match_timeline_features / match_events;
  match_participants now covers all 55 stored matches (fixes the empty-derived-tables state and
  the legacy mixed-denominator risk for stored matches).
- Collection verified end-to-end against the live API: aborted with
  "riot key rejected (401) — rotate RIOT_API_KEY" (dev key expired; no retries fired).
  Full run pending a fresh key.
- 5 new tests (dedupe vs stored+in-run duplicates, cap stops seed queries, 401/403 abort,
  transient seed failure continues, single-match failure isolation).

Not domain-reviewed: collection infrastructure only — no analysis semantics, metric formulas,
or user-facing copy changed.

Collection executed (2026-07-18, after key rotation + riot-id seed fix):
- Round 1: 100 new matches (5 seeds, 0 failed). Round 2: 200 new (12 seeds, 0 failed).
  Totals: 350 q420 matches / 344 timelines stored (was 47/41). Seed pool barely tapped.
- Retrained at n=333 (advantage) / n=332 (expected); reports preserved as
  `docs/ml/reports/*_n333.json`:
  - **Advantage**: volume gates PASS (333 ≥ 300, 100 test ≥ 60) and model ECE 0.0456 ≤ 0.05,
    but heuristic v0 clearly beats the logistic model (AUC 0.814 vs 0.782, log loss 0.526 vs
    0.548, Brier 0.176 vs 0.189) → keep_heuristic **on model-quality grounds**. The 40-match
    "model edges heuristic" result was noise. Interim n=142 run confirmed the trend.
    Interpretation: the hand-tuned time-weighted gold interaction outperforms linear features —
    exactly the gap backlog items 5 (minute-interaction features) and 6 (boosting) target.
  - **Expected**: grouped baselines still do not beat zero meaningfully (GD@10 zero MAE 616.9 vs
    role_side 620.9 — the small-sample side signal vanished); richer context (matchup/tier)
    needed before expected values become actionable → report_only stands.

---

Previous package — Phase 8 — Expected-performance models: per-participant GD@10 / CSD@10 / XPD@10 dataset from raw
timelines, grouped-average expected values (baselines before any model, per MODEL_RULES),
residual output `actual − expected`, temporal match-grouped held-out report. Report-only:
no serving/profile integration this phase.

Delivered (2026-07-18):
- `backend/app/ml/expected_performance.py` (EXPECTED_VERSION 1): minute-10 lane differentials
  paired by teamPosition (roles not filled exactly once per team are skipped; per-match exclusion
  reasons recorded); grouped-average baselines zero / role_mean / role_side_mean fitted on train
  only with small-group fallback (MIN_GROUP_N 10, role_side→role→zero); held-out MAE/RMSE per
  target; residual = actual − expected with test mean/std; `predict_expected` single entry point.
- Shared fetch extracted (`fetch_match_timeline_records` in advantage_dataset — queue→domain
  guard now guards both builders); `python -m app.ml.train_expected` CLI; model definition doc
  `docs/ml/EXPECTED_PERFORMANCE.md`.
- Real-data run (40 matches / 400 rows, held-out 12/120): role_mean ≡ zero exactly (lane pairs
  are anti-symmetric — per-role means vanish by construction); role_side_mean marginally better
  for GD@10 (MAE 587.5→578.0) and XPD@10, worse for CSD@10 → **verdict report_only**; report at
  `docs/ml/reports/expected_v1_2026-07-18.json`. No serving/profile/UI changes.
- 13 new tests (pairing/anti-symmetry, jungle CS, minute-10 exclusion, duplicate-position skip,
  train-only fitting + fallback, report shape/verdicts, split grouping).

---

Previous package — Phase 7 — Advantage model: reproducible per-minute snapshot dataset + logistic baseline +
calibration report; heuristic curve stays in production unless documented adoption thresholds pass.

Delivered (2026-07-18):
- `backend/app/ml/advantage_dataset.py` (DATASET_VERSION 1): snapshot rows recomputed from raw
  timelines via `analyze_match_timeline`; winner from match teams (ambiguous → excluded, reason
  recorded); remake filter; temporal match-grouped split (oldest→train, newest 30%→test).
- `backend/app/ml/advantage_model.py` (MODEL_VERSION 1): deterministic pure-Python logistic
  regression (zero init, full batch, 1500 epochs, L2), self-contained JSON artifact,
  `predict_from_artifact` as the single train/serve entry point; metrics AUC/log loss/Brier/
  ECE/reliability + time-bucket and patch calibration; baselines = constant train winrate +
  heuristic v0 on identical snapshots; adoption gate (≥300 matches, ≥60 test matches, beats both
  baselines on log loss AND Brier, ECE ≤ 0.05) — verdict is data, never an automatic swap.
- `python -m app.ml.train_advantage` CLI (runs in backend container); model definition doc
  `docs/ml/ADVANTAGE_MODEL.md` (MODEL_RULES required-definition complete).
- Real-data run (40 matches / 1137 snapshots): model AUC 0.785 vs heuristic 0.778, but ECE 0.086
  vs 0.077 and volume ≪ gate → **verdict keep_heuristic**; report preserved at
  `docs/ml/reports/advantage_v1_2026-07-18.json`. Serving path and UI untouched (우세도 유지).
- 26 new tests (winner/patch derivation, split leakage properties, deterministic training,
  artifact round-trip parity, metric edge cases, gate verdicts, queue-domain guard, exclusion
  reasons).

Domain review findings applied (2026-07-18): queue→domain mapping enforced (`QUEUE_DOMAINS`,
unmapped queue → ValueError — soloq/pro can never silently mix); missing `game_creation`
excluded with recorded reason (temporal split stays exact); terminal-frame limitation disclosed
in ADVANTAGE_MODEL.md (final frames nearly encode the label — not strict leakage, both baselines
see identical rows, but aggregate metrics are optimistic; final-frame exclusion or per-bucket
gate planned as explicit DATASET_VERSION 2); doc exclusion fact corrected (remake_or_short).

Phase 7 residual limitations: adoption gate is aggregate-only (per-time-bucket criterion
deferred to DATASET_VERSION 2); patch calibration currently trivial (all local matches share a
patch); local 41-match volume means held-out numbers carry wide uncertainty — the validated
pipeline, not the model, is the deliverable.

### Scope decisions (2026-07-18)

- `match_timeline_features` table is currently empty (schema recreate wiped derived rows), but
  48 raw timelines are preserved — the dataset builder recomputes features deterministically from
  `riot_match_timelines` via the existing `analyze_match_timeline` (single formula source, clear
  lineage). Local volume: 55 matches, 41 ranked-solo (q420) with timelines.
- One row = one (match, minute) snapshot; features = inference-time-available only
  (minute, gold/xp/cs/tower/dragon/herald/baron diffs); label = blue win from match raw teams.
- Split: temporal by game_creation, match-grouped (all snapshots of a match in one split).
- Baselines: constant train blue-winrate + existing heuristic v0 (`win_probability.py`).
- No numpy/sklearn yet: 8 features × ~1k rows — deterministic pure-Python full-batch
  gradient-descent logistic regression; boosting/sklearn only if a later phase justifies it.
- Adoption gate centralized: model replaces heuristic only if held-out log loss AND Brier beat
  both baselines, ECE ≤ threshold, and match count ≥ minimum — with 41 matches the expected
  verdict is keep_heuristic + insufficient_data; the deliverable is the validated pipeline and
  an honest report. UI untouched; `우세도` label unchanged.

---

Previous package — Phase 6 — Evidence-grounded AI agent hardening: **COMPLETE** (2026-07-14, domain-reviewed).

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

Residual hardening 2026-07-18 (REPORT_VERSION 5, REPORT_PROMPT_VERSION 3, domain-reviewed):
- Numeric guard extended to Korean numeral notation: sino-Korean compounds up to 만 scale
  (삼십오, 이천), digit+scale mixes (9만, 2만5천), native numerals incl. tens compounds
  (열다섯, 스물다섯, 서른…), N할→N*10% conversion; a numeral must be bound to a quantity word
  (퍼센트/골드/점/…/개/명/%) and same rule applies (≤10 free, else must exist in payload).
  Lookbehind prevents word-internal matches ("이겼지만 골드" ≠ 만 골드). Prompt now mandates
  Arabic digits; REPORT_VERSION bump invalidates pre-guard caches.
- Closed residual: "numeric guard covers Arabic digits only" — resolved.

Phase 6 residual limitations (current): number existence ≠ semantic binding (진짜 숫자를 엉뚱한
주장에 붙일 수 있음 — 관측은 refs로 완화, 요약/가설 산문은 미바인딩); experiment framing of
suggestions is prompt-level only; hypotheses may carry zero refs (UI 라벨로 완화).
Korean-numeral guard known gaps (fail direction noted): N할 N푼의 푼 무시(5할8푼=58이
50으로 검사되어 정당한 문장이 탈락할 수 있음 — fail-safe), 소수+scale(1.5만) 오파싱 →
탈락(fail-safe), 관용구 백배/백 번/스무 번째는 수량 주장으로 간주되어 문장 탈락(가용성 비용,
오의미 출력은 불가), 한자 숫자(三十五)·수십/몇십 류 모호 수량은 미검사(구체 수치 아님).

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
| 2026-07-18 | `pytest` | 165 passed | + Korean-numeral guard (sino/native/digit+scale/할, false-positive + 일곱/일흔 dispatch regression) |
| 2026-07-18 | `pytest` | 191 passed | + advantage dataset/model (split leakage, determinism, parity, metrics, gate, queue-domain guard) |
| 2026-07-18 | `python -m app.ml.train_advantage` | keep_heuristic | 40 matches/1137 rows; report in docs/ml/reports/ |
| 2026-07-18 | `pytest` | 204 passed | + expected performance (pairing, baselines, fallback, report) |
| 2026-07-18 | `python -m app.ml.train_expected` | report_only | 40 matches/400 rows; report in docs/ml/reports/ |
| 2026-07-18 | `pytest` | 209 passed | + match collector (dedupe, cap, abort, failure isolation) |
| 2026-07-18 | `match_collector --backfill` | 48 backfilled, 0 failed | derived tables restored from stored raw |
| 2026-07-18 | `match_collector --max-new 3` | aborted: key rejected (401) | clean abort verified; full run needs fresh key |
| 2026-07-18 | `pytest` | 210 passed | + riot-id seed resolution (rename fallback) |
| 2026-07-18 | `match_collector` ×2 | 300 new matches, 0 failed | 350 q420 stored (344 timelines) |
| 2026-07-18 | `train_advantage` (n=333) | keep_heuristic (quality) | volume+ECE gates pass; heuristic beats model — report `advantage_v1_2026-07-18_n333.json` |
| 2026-07-18 | `train_expected` (n=332) | report_only | grouped baselines ≈ zero — report `expected_v1_2026-07-18_n333.json` |
| 2026-07-19 | `match_collector` round 3 | 200 new, 0 failed | 550 q420 stored (544 timelines); pool measured EMERALD–DIAMOND (15-player sample: 8 E / 7 D) |
| 2026-07-19 | `train_advantage` (n=526) | keep_heuristic (quality) | gap narrowed: heuristic AUC 0.790 vs model 0.781; model ECE 0.041 now beats heuristic 0.044 — report `advantage_v1_2026-07-19_n526.json` |
| 2026-07-19 | `train_expected` (n=524) | report_only | zero baseline still best — report `expected_v1_2026-07-19_n524.json` |
| 2026-07-19 | `pytest` | 213 passed | + dataset v2 (terminal-frame exclusion, interaction features) |
| 2026-07-19 | `train_advantage` (n=526, dataset v2) | keep_heuristic (Brier only) | model wins LL 0.5690 vs 0.5728 + ECE; trails Brier 0.1956 vs 0.1943 — report `advantage_v2_2026-07-19_n526.json` |
| 2026-07-19 | `pytest` | 223 passed | + live sessions (reconcile paths, idempotency contract, companion compaction) |
| 2026-07-19 | live API e2e (curl) | pass | batch accept → duplicate retry accepted=0 → complete=reconciled w/ real match id |
| 2026-07-19 | `alembic upgrade head --sql` | pass (offline) | 0005 live tables |

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

Volume gates now pass; the constraint moved from data to model quality. Candidates:
1. **Advantage model iteration** (backlog 2/5/6, now unblocked): DATASET_VERSION 2 (terminal-frame
   exclusion), minute-interaction features (the heuristic wins precisely on time-weighted gold),
   then boosting only if it beats both the logistic and the heuristic on held-out data.
2. **Phase 9 — Live Client collector** (companion C1, master-plan §7.4).
3. Optional: further collection rounds (cheap — `match_collector --max-new 100`, seed pool barely
   tapped) to widen patch coverage over time; keys rotate daily.

Adoption rule unchanged: the heuristic stays in production until a candidate beats it on
held-out log loss AND Brier with ECE ≤ 0.05 at ≥300 matches.

Earlier phase limitations remain recorded above (Phase 5 best/risk_management mean, selection
profile-vector basis; Phase 6 numeric-guard scope; Phase 7 terminal-frame optimism, aggregate-only
gate; Phase 8 side-asymmetry signal marginal at current volume).
