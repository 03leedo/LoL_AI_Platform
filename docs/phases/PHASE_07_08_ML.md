# Phases 7–8 — ML

## Read
- `docs/ml/MODEL_RULES.md`
- relevant data/profile docs

## Phase 7
Build and validate an advantage model with leakage-safe temporal splits and calibration.

## Phase 8
Build expected GD@10, CSD@10, and XPD@10 models, comparing residuals against grouped baselines.

## Gate
Do not begin ML until source lineage, deterministic features, and sufficient data are verified.

Each phase requires:
- reproducible dataset builder;
- baseline;
- held-out report;
- leakage checks;
- artifact/version management;
- inference parity;
- separate pro and solo-queue domains.

Complete one ML phase at a time and stop.
