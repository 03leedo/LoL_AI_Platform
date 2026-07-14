# ML Rules

Use ML only when it improves on a clear baseline.

## Required definition
For every model document:

- target;
- one training row;
- inference-time features;
- missing-data handling;
- baseline;
- split strategy;
- evaluation metrics;
- model/feature version;
- fallback behavior.

## Leakage prevention
- keep all snapshots from one match in the same split;
- split by time, not random snapshot rows;
- use only information available at inference time;
- keep professional and solo-queue models separate.

## Advantage model
Start with logistic regression. Add boosting only if it improves held-out results.

Evaluate:
- ROC-AUC;
- log loss;
- Brier score;
- expected calibration error;
- calibration by game-time bucket and patch.

Call output `advantage` until calibration and held-out validation are acceptable.

## Expected-performance models
Initial targets:
- GD@10;
- CSD@10;
- XPD@10.

Output:
```text
actual - expected
```

Possible context:
- role;
- patch;
- champion matchup;
- side;
- tier/competition level;
- opponent-strength proxy;
- early event/intervention proxy.

Compare against grouped averages before complex models.

## Interpretation
Model quality is not player-skill accuracy.

Use SHAP or other explanations only after model validity is established. Explanations must not infer intent.
