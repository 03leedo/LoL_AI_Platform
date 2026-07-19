# Data and Metric Rules

## Logical layers
Use existing equivalents where possible:

1. raw source;
2. normalized match, participant, snapshot, and event records;
3. derived episodes and per-match features;
4. versioned profile/model output;
5. evidence and explanation.

## Required properties
- idempotent ingestion;
- deterministic regeneration;
- source lineage;
- schema/rule/feature/model version;
- completeness or confidence;
- calculation timestamp.

## Existing metric protection
Before changing a current metric:

1. locate the actual implementation;
2. document its inputs and exact formula;
3. find API and UI consumers;
4. find tests;
5. preserve numeric behavior unless a verified bug or explicit requirement changes it.

Known names may include:
- Death Cost;
- Throw Index;
- Stability;
- Objective;
- Lead Conversion;
- 10-minute Laning Score;
- Gold Retention;
- Gambler Index;
- Teamfight Durability;
- Death Acceleration.

These names are discovery hints, not authoritative formulas.

## 10-minute laning score
This per-match score compares the player with the opposite team's participant
in the same Riot role at the 10-minute timeline frame. It is a snapshot of the
lane result in that match, not a permanent measure of player skill.

Inputs:

- `GD@10`: player gold minus same-role opponent gold;
- `XPD@10`: player experience minus same-role opponent experience;
- `CSD@10`: player lane and jungle CS minus same-role opponent CS.

The differences are divided by held-out residual standard deviations from
`expected_v1_2026-07-19_n524`, then combined as:

```text
z = 0.45 * GD@10 / 851.4679
  + 0.35 * XPD@10 / 686.3047
  + 0.20 * CSD@10 / 15.7186

score = round(50 + 50 * clamp(z, -3, 3) / 3)
```

`50` means roughly even, a higher score means the player was ahead at 10
minutes, and a lower score means the player was behind. Raw differences are
kept in evidence. Confidence is capped at `medium` because the score cannot
separate lane play from jungle pressure, roams, swaps, or matchup context.

## Preferred profile dimensions
Initial profile dimensions:

- early growth stability;
- resource conversion efficiency;
- risk exposure management;
- objective readiness;
- fight outcome contribution only when reliable.

## Aggregation
- calculate per-match features first;
- do not silently mix roles;
- use comparable queue, patch, tier, and role cohorts;
- expose sample size;
- apply recency weighting;
- shrink small samples toward a cohort baseline;
- expose confidence;
- link supporting evidence.

## Team variables
Team gold, damage, objectives, and result may normalize an individual's output. Do not convert them into team-fit, teammate-effect, or synergy scores.
