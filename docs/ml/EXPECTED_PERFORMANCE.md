# Expected-Performance Models v1 (Phase 8)

Required definition per `docs/ml/MODEL_RULES.md`. Code:
`backend/app/ml/expected_performance.py`, CLI `python -m app.ml.train_expected`.

## Target

Three lane-differential targets at minute 10: **GD@10** (gold), **CSD@10**
(lane + jungle CS), **XPD@10** (XP), each player minus their lane opponent.
The product output is the residual `actual − expected` — a context-adjusted
observation, never a positive ability score. A single match's residual is not
permanent skill.

## One training row

One `(match, participant)` from a stored raw timeline: the minute-10 frame's
`totalGold` / `xp` / `minionsKilled + jungleMinionsKilled`, differenced against
the opposing participant with the same `teamPosition`. Roles not filled exactly
once per team are skipped; matches with no minute-10 frame, no pairable roles,
remakes (<300s), or missing `game_creation` are excluded with recorded reasons.
Queue must be domain-mapped (`QUEUE_DOMAINS`, 420 → soloq only today).

## Inference-time features (grouping context)

`role`, `side` (and `patch`, currently single-valued locally). MODEL_RULES
lists more context (matchup, tier, opponent strength) — those need volume and
arrive as explicit `EXPECTED_VERSION` bumps.

## Missing-data handling

All exclusions are per-match with recorded reasons (see above); participant
frames missing from the minute-10 frame drop that role pair only.

## Baseline

Grouped averages before any model (MODEL_RULES): `zero` (expected = 0, exact
for anti-symmetric pairs), `role_mean`, `role_side_mean`. Group means are
fitted on the **train split only**; groups smaller than `MIN_GROUP_N = 10`
fall back to their parent (role_side → role → zero). Ties on held-out MAE go
to the simpler baseline.

## Split strategy

Same as Phase 7: temporal by `(game_creation, match_id)`, match-grouped —
both laners of a pair and all participants of a match stay in one split.
Solo-queue only; pro data would get separate models.

## Evaluation metrics

Held-out MAE and RMSE per target per baseline; residual mean/std for the best
baseline. Reports preserved in `docs/ml/reports/`.

## Model / feature version

`EXPECTED_VERSION 1`. Models are grouped-mean tables (JSON-serializable, with
group sizes); `predict_expected` is the single prediction entry point.

## Fallback behavior and serving

Report-only phase: residuals are wired to **no** user-facing surface. Exposing
them (e.g. in profiles) requires ≥ `SERVING_MIN_MATCHES = 300` matches, a
baseline that clearly beats `zero` out of sample, and its own explicit phase
with evidence-safe copy (residual ≠ ability, opponent context undisclosed).

## Current result (2026-07-18, `docs/ml/reports/expected_v1_2026-07-18.json`)

40 matches / 400 participant rows; held-out 12 matches / 120 rows.

| target | zero MAE | role_mean MAE | role_side_mean MAE | best |
|---|---|---|---|---|
| GD@10 | 587.5 | 587.5 | 578.0 | role_side_mean |
| CSD@10 | 9.7 | 9.7 | 9.8 | zero |
| XPD@10 | 528.4 | 528.4 | 527.2 | role_side_mean (margin 1.2 MAE — not meaningful at this volume) |

`role_mean` equals `zero` exactly — lane pairs are anti-symmetric, so per-role
means vanish by construction; only side asymmetry carries signal, and it is
marginal at this volume. **Verdict: report_only** — expected values are not
yet better than "expect 0" in any actionable way; grow data before revisiting.
