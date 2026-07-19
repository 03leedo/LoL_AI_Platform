# Per-minute Win Prediction Model v1 (Phase 7)

Required definition per `docs/ml/MODEL_RULES.md`. Code: `backend/app/ml/`
(`advantage_dataset.py`, `advantage_model.py`, `train_advantage.py`).

## Target

Blue side wins the match (binary). One prediction is produced for every minute
snapshot, so the output means **the estimated chance that blue eventually wins
given only the state available at that minute**. It is not a pre-game winner
pick and it does not read future timeline frames.

The current artifact has not passed every adoption-gate criterion, so the UI
labels it `model v1 · experimental`. This makes the intended model curve
visible for review without presenting it as a fully calibrated production
probability.

## One training row

One `(match_id, minute)` snapshot from a stored raw timeline
(`riot_match_timelines`), recomputed deterministically by
`analyze_match_timeline` (the same formula source the UI win curve uses).
Label = blue win, derived from the match payload's `info.teams[].win`
(ambiguous/contradictory flags → match excluded). Matches shorter than 300s
(remakes) are excluded. Default queue 420 (ranked solo).

## Inference-time features

`minute, gold_diff, xp_diff, cs_diff, tower_diff, dragon_diff, herald_diff,
baron_diff` (blue minus red), plus derived interactions `gold_diff_x_time` and
`xp_diff_x_time` (diff × the heuristic's game-time weight, min(1.5, 0.5+m/30)).
Derived values are computed by a single helper (`full_feature_row`) shared by
training and inference — rows never store them, so the paths cannot drift.
All features are available at the snapshot minute; no feature reads later
minutes or the match outcome.

**Terminal frames (resolved in DATASET_VERSION 2):** v1 kept each match's
final frame, whose end-of-game state nearly encodes the label, making
aggregate metrics optimistic. Since v2 (2026-07-19) the terminal frame is
excluded from every row (training, evaluation, and both baselines see the
same filtered snapshots). The remaining softer form — the second-to-last
frame is still 60s from game end — is accepted and disclosed; a per-time-
bucket gate criterion stays on the backlog.

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

- `DATASET_VERSION 2` (terminal-frame exclusion + interaction features;
  v1 = raw per-minute snapshots), `MODEL_VERSION 1` (`logistic_regression_gd`,
  pure Python, deterministic: zero init, full batch, 5000 epochs, lr 0.3,
  L2 1e-3). Artifacts record their hyperparameters, so runs are
  self-describing.

**Gate caveat (2026-07-19):** the 5000/0.3 hyperparameters were
convergence-probed against the *current temporal test split*
(`docs/ml/reports/convergence_probe_2026-07-19.json`) — that window is no
longer selection-clean. Convergence-to-plateau is the most benign form of
tuning and the verdict stayed keep_heuristic, so no contaminated adoption
occurred; but the forward rule is binding: **future tuning and model
selection (incl. boosting) use a validation slice carved from train
(temporal train/val), and any `adopt` verdict must be confirmed on matches
ingested after the last tuning date** (nearly free with the rolling
newest-30% test as data grows).
- Artifact is self-contained JSON: feature names, standardization means/stds,
  coefficients, intercept, domain, queue, train volume.
  `predict_from_artifact` is the single inference entry point (train/serve
  parity; JSON round-trip tested identical).

## Adoption gate and fallback

Verdict `adopt` requires ALL of (constants in `advantage_model.py`):
- ≥ 300 total matches and ≥ 60 test matches;
- held-out log loss AND Brier better than both baselines;
- held-out ECE ≤ 0.05.

Otherwise `keep_heuristic`: the rule-based curve remains the supported
fallback. The match-review API may expose the v1 model curve for ranked solo
queue as an explicitly experimental visualization; unsupported queues and
artifact failures use `win_probability.py` instead. Full adoption still
requires the gate above.

## Result history (reports in `docs/ml/reports/`)

| date | n (matches) | dataset | model AUC/LL/Brier/ECE | heuristic AUC/LL/Brier/ECE | verdict |
|---|---|---|---|---|---|
| 2026-07-18 | 40 | v1 | .785/.559/.193/.086 | .778/.561/.194/.077 | keep (volume, ECE) |
| 2026-07-18 | 333 | v1 | .782/.548/.189/.046 | .814/.526/.176/.030 | keep (LL+Brier) |
| 2026-07-19 | 526 | v1 | .781/.557/.191/.041 | .790/.555/.188/.044 | keep (LL+Brier) |
| 2026-07-19 | 526 | **v2** | .768/**.569**/.196/**.042** | .775/.573/**.194**/.046 | keep (**Brier only**) |

v1 and v2 rows use different snapshot populations (v2 drops each match's
easiest, terminal snapshot), so absolute values are **not comparable across
dataset versions** — compare model vs heuristic within a row only.

Reading: the 40-match "model edge" was noise; at real volume the hand-tuned
heuristic led everywhere, and successive honest changes (terminal-frame
exclusion, interaction features, converged optimization) closed the gap to a
single criterion — v2 beats the heuristic on log loss and ECE and trails only
on Brier (0.1956 vs 0.1943). Linear capacity is the remaining ceiling
(train≈test loss): per MODEL_RULES the next step is boosting, adopted only if
it beats BOTH the logistic and the heuristic on the same gate. The heuristic
stays in production.
