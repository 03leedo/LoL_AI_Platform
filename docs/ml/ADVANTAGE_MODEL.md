# Advantage Model v1 (Phase 7)

Required definition per `docs/ml/MODEL_RULES.md`. Code: `backend/app/ml/`
(`advantage_dataset.py`, `advantage_model.py`, `train_advantage.py`).

## Target

Blue side wins the match (binary). Output is called **advantage (우세도)** —
never "win probability" in user-facing copy — until calibration and held-out
validation pass the adoption gate below.

## One training row

One `(match_id, minute)` snapshot from a stored raw timeline
(`riot_match_timelines`), recomputed deterministically by
`analyze_match_timeline` (the same formula source the UI win curve uses).
Label = blue win, derived from the match payload's `info.teams[].win`
(ambiguous/contradictory flags → match excluded). Matches shorter than 300s
(remakes) are excluded. Default queue 420 (ranked solo).

## Inference-time features

`minute, gold_diff, xp_diff, cs_diff, tower_diff, dragon_diff, herald_diff,
baron_diff` (blue minus red). All are available at the snapshot minute on the
existing win-curve path; no feature reads later minutes or the match outcome.

**Known limitation — terminal frames:** the analyzer keeps each match's final
frame, whose state (nexus turrets count as towers, end-of-game gold) nearly
determines the label. This is observable in-game at that minute — not strict
leakage, and both baselines see identical rows — but aggregate metrics are
optimistic, and the adoption gate is aggregate-only: a candidate could win
mostly on terminal frames while being worse mid-game. Planned as an explicit
`DATASET_VERSION 2` change (final-frame exclusion or a per-time-bucket gate
criterion); v1 keeps the frames and this disclosure.

## Missing-data handling

- No winner derivable → match excluded (reason recorded in `matches_excluded`).
- No frames → match excluded.
- Missing `game_creation` → match excluded (`missing_game_creation`) so the
  temporal split stays exact.
- Missing patch string → `patch: null`, grouped as `unknown` in calibration.
- Feature fields are always present in analyzer output (0-defaulted counters).
- Queues without an explicit domain mapping (`QUEUE_DOMAINS`, currently only
  420 → soloq) are refused: mixed or unlabeled datasets cannot be built.

## Baselines

1. `constant_train_rate` — predicts the train-set blue winrate everywhere.
2. `heuristic_v0` — the production hand-tuned curve (`win_probability.py`),
   evaluated on exactly the same held-out snapshots.

The model is a candidate only if it beats **both** on held-out log loss and
Brier.

## Split strategy

Temporal, match-grouped: distinct matches ordered by `(game_creation,
match_id)`, oldest → train, newest 30% → test. Every snapshot follows its
match; no random row splits. Solo-queue only (`domain: soloq`); professional
data, if ever ingested, gets a separate model.

## Evaluation metrics

ROC-AUC, log loss, Brier score, ECE (10 bins), reliability curve, calibration
by game-time bucket (0–9/10–19/20–29/30+) and by patch. Reports are written to
`docs/ml/reports/`.

## Model / feature version

- `DATASET_VERSION 1`, `MODEL_VERSION 1` (`logistic_regression_gd`, pure
  Python, deterministic: zero init, full batch, fixed 1500 epochs, L2 1e-3).
- Artifact is self-contained JSON: feature names, standardization means/stds,
  coefficients, intercept, domain, queue, train volume.
  `predict_from_artifact` is the single inference entry point (train/serve
  parity; JSON round-trip tested identical).

## Adoption gate and fallback

Verdict `adopt` requires ALL of (constants in `advantage_model.py`):
- ≥ 300 total matches and ≥ 60 test matches;
- held-out log loss AND Brier better than both baselines;
- held-out ECE ≤ 0.05.

Otherwise `keep_heuristic`: the serving path (`win_probability.py`) is
untouched — it remains the production curve and the fallback at all times.
Adoption, when justified, is a separate explicit change behind the same output
shape.

## Current result (2026-07-18, `docs/ml/reports/advantage_v1_2026-07-18.json`)

40 usable matches / 1137 snapshots (1 match excluded: remake_or_short).
Held-out (12 matches, 350 rows): model AUC 0.785, log loss 0.559, Brier 0.193,
ECE 0.086 vs heuristic AUC 0.778, log loss 0.561, Brier 0.194, ECE 0.077.

**Verdict: keep_heuristic** — volume far below gate (40 < 300 matches,
12 < 60 test matches) and ECE above threshold (0.086 > 0.05; the heuristic is
currently better calibrated). The deliverable of this phase is the validated,
reproducible pipeline and this honest report, not a model swap. Re-run
`docker compose exec backend python -m app.ml.train_advantage` as ingested
volume grows.
