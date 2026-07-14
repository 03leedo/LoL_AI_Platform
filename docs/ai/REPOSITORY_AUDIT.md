# Repository Audit — 2026-07-13

Phase 0 deliverable. Maps the current system so later phases extend existing behavior instead of replacing it. Formulas documented from code, not from product docs.

## 1. Architecture Summary

Monorepo, three runtime components via Docker Compose:

```text
frontend (Next.js 15, React 19, Korean UI)  :3000
  /                      search
  /summoner/[riotId]     profile + rank badge + match cards + heatmap + rank analysis + AI report
  /match/[matchId]       review: score cards, win curve, turning points, key events, evidence minimap

backend (FastAPI async)  :8000  prefix /api/v1
  api/routes/riot.py     all product endpoints (single router file — split candidate later)
  services/              riot_client (rate-limited), match_data (DB-first cache), timeline_analyzer,
                         custom_metrics, habit_metrics, key_events, evidence_contexts, heatmaps,
                         win_probability, turning_points, scorecard, role_analyzer, patterns,
                         reports, llm_provider, llm_feedback, ingest, challenges, rate_limiter,
                         match_summaries
  repositories/          matches, summoners, analysis (persistence; merge / delete+insert patterns)
  models/                summoner, match, analysis (SQLAlchemy, JSONB-heavy)
  migrations/            alembic 0001 baseline, 0002 M0 tables, 0003 rank cols, 0004 analysis_reports

postgres 16              raw JSONB + normalized tables (schema below)
```

Companion app (Tauri/local collector), Redis, ML tooling: planned, not present.

## 2. Runtime and Commands

See `docs/ai/IMPLEMENTATION_STATUS.md` → Verified Commands (single source; not duplicated here).

## 3. Data Flow

```text
Riot ID search → account/summoner/league (Riot API, rate-limited 18/s·95/120s)
match request → match_data.get_match_cached / get_timeline_cached   # DB-first, immutable payloads
  cache miss → RiotClient (retry 429 Retry-After, 5xx backoff) → commit raw JSONB immediately
review/analysis flow:
  timeline_analyzer → per-minute features (dedup by minute, last frame wins)
  custom_metrics.analyze_player_match → 5 scores + evidence
  habit_metrics.merge_habit_metrics   → +4 scores, evidence merged (cap 16)
  evidence_contexts.attach            → ±30s context, minimap snapshots, rule insights
  llm_feedback (optional)             → ≤2 LLM insights per evidence, rules fallback
  key_events / win_probability / turning_points / build_review_assets
  persistence: participants, events, features, player_skill_scores, metric_scores(long), moments
background ingest (POST .../ingest):
  ingest_jobs row → asyncio task (own session) → per match: cached fetch + full metric persistence (no LLM)
aggregation (GET .../rank-analysis): DB-only → scorecard + role fit → scope=aggregate rows
report (GET .../report): records+events → patterns/autopsy (rules) → deterministic report →
  optional LLM rewrite (prose only) → analysis_reports cache keyed v{RPT}:m{METRIC}:{window}:{latest_match}
heatmap (GET .../heatmap): timeline kill events → points + coarse zones → death-zone stats
```

## 4. Current Feature Inventory

See `docs/ai/IMPLEMENTATION_STATUS.md` → Current Feature Inventory (kept there as the live copy).

## 5. Indicator-to-File Map

Live copy in `docs/ai/IMPLEMENTATION_STATUS.md` → Existing Indicator Map. Key constants:

- `custom_metrics`: OBJECTIVE_WINDOW_MS=90s; objective weights baron 25 / dragon 16 / herald 14 / tower 10; METRIC_VERSION=2
- `habit_metrics`: RICH_GOLD 1500 / wallet-death 1300; ISOLATION 4000u; map diagonal 15000(+1000 deep margin); fight = ≥3 kills, ≤20s gaps, ≥4 participants; chain window 5min; evidence cap 16
- `win_probability`: hand-tuned logistic, time-weighted gold; clamp 3–97%
- `turning_points`: |Δ|≥8%p, top 3, high-impact event preference
- `heatmaps.zone_of`: mid band |x−y|<2000, lane edges 3000/12000, jungle side by x+y vs 15000
- `patterns`: first-death window 6min/≥50%/≥3; death zone ≥30%/≥5; objective-linked ≥30%/≥4; shutdown ≥3회 or ≥700g; chronic thresholds per metric
- `scorecard`: 6 abilities from challenges + stored scores; confidence by n (10/5)
- `role_analyzer`: shrinkage n/8 toward 50; recommend fit≥50; caution fit<45

## 6. API and DB Contracts

Endpoints (`/api/v1/riot`): account, summoner (rank fields), matches ids, match-history, heatmap,
ingest POST + ingest-jobs/{id}, rank-analysis, report, matches/{id} (raw), /timeline, /review, /analysis.

Tables: summoners(+solo rank), riot_matches(raw_json), riot_match_timelines(raw_json), summoner_matches(legacy),
match_participants(raw_json incl. challenges), match_events, match_timeline_features, player_skill_scores(wide, legacy-ish),
metric_scores(long: scope, window, metric_key, value, confidence, direction, evidence, source, metric_version),
moments, ingest_jobs, analysis_reports(cache_key).

Response-shape conventions: scores `{value:int|null, confidence:low|medium|high, direction:higher_is_better|higher_is_worse}`;
evidence `{minute,type,title,description,confidence,context?}`; new fields added optional/defaulted for backward compat.

## 7. Test Coverage Map

102 pytest tests (fixture-based, no live DB — stub sessions) across: custom metrics, habit metrics, key events,
evidence contexts, llm feedback/provider, riot client retry, rate limiter, match_data cache, analysis repositories,
scorecard, role analyzer, turning points, win probability, heatmaps, patterns, reports, timeline analyzer, match summaries.
Frontend: tsc only (no component tests). No E2E. No lint config.

## 8. Risks and Technical Debt

1. Death Cost / objective-linked deaths: one objective can be attributed to multiple deaths; denominator is all deaths (Phase 3 episode engine + analyzable-death predicate).
2. Causal-leaning labels: "승률", "추천 포지션", some pattern titles ("데스 직후 오브젝트를 내주는 패턴" is acceptable-observational, but review all) — Phase 1.
3. Direction mixing on screen: risk/style indicators (gambler, death acceleration, gold retention) rendered alongside ability scores — Phase 1 grouping metadata.
4. `api/routes/riot.py` is a single large router; `page`-level frontend components growing — refactor when a phase touches them.
5. `player_skill_scores` (wide) duplicates `metric_scores` (long) — converge on long-format eventually.
6. Evidence has no stable IDs; contexts recomputed per request (not persisted) — Phase 1/2.
7. Dev auto-create tables + Alembic coexistence — fine for dev, must be alembic-only in prod (M5).
8. LLM enum/labels: `llm_feedback` merged insights cap 2 may drop rule insights entirely when LLM returns 2 (by design, revisit).
9. No lint; unittest-style tests (fine, but no async test framework — asyncio.run pattern used).

## 9. Recommended Phase 1 File-level Plan

Outcome: observation/hypothesis/limitation/replay-question separation + evidence IDs + honest naming, with zero metric-formula changes.

- `backend/app/services/analysis_semantics.py` (new): builders for `AnalysisStatement{kind, text, evidence_ids, confidence}` and evidence-ID assignment (deterministic ids like `ev:{match_id}:{type}:{minute}:{n}` over existing evidence items).
- `backend/app/services/custom_metrics.py` / `habit_metrics.py`: no formula change; evidence items gain `id` + `kind:"observation"`; wording pass on titles/descriptions (correlation phrasing).
- `backend/app/services/win_probability.py` + schemas + frontend: rename user-facing 승률 → 우세도(advantage); keep field names backward-compatible (`blue_win_prob` stays; add `label:"advantage"` metadata or rename at UI layer only).
- `backend/app/services/role_analyzer.py` + `RankAnalysisPanel.tsx`: "추천 포지션" → "최근 성과가 가장 좋았던 포지션" (metadata + UI copy).
- `backend/app/schemas/riot.py`: optional `statements` block per analysis (observations/hypotheses/limitations/replay_questions), `direction_group: performance|risk_style` on score metadata.
- `backend/app/services/patterns.py` / `reports.py`: emit limitation + replay-question entries; LLM system prompt gains statement-schema; sanitizer enforces evidence_ids present on factual claims.
- Frontend: score card grouping (퍼포먼스 vs 위험·스타일 섹션), 우세도 label, statements rendering in report panel.
- Tests: evidence-id linkage, no-causal-wording lint test (regex over emitted titles/descriptions), backward-compat of old response consumers, unknown/needs_replay_review path.

## 10. Do Not Touch Yet

- Metric formulas in `custom_metrics.py` / `habit_metrics.py` (Phase 1 is wording/structure only).
- Alembic history files 0001–0004 (append new revisions only).
- `frontend/src/lib/api.ts` fetch conventions (extend, don't rewrite).
- `docker-compose.yml` service topology.
- `.env` (user-owned; document required keys in `.env.example` instead).
- Rate limiter budgets (tied to Riot dev-key policy).
