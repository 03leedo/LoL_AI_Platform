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

## 10-minute early comparison
Early play is split into separate resource and combat outputs. This prevents a
roam or jungle-assisted kill from being treated as lane pressure, and prevents
sparse health snapshots from silently changing the main score.

### Resource advantage
This per-match score compares the player with the opposite team's participant
in the same Riot role at the 10-minute timeline frame. It is a snapshot of the
resource result in that match, not a permanent measure of player skill.

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

### Early combat impact
Champion-kill events up to 10 minutes produce a separate score:

- player early KP = player kills and assists / allied team kills;
- opponent early KP uses the same calculation for the same-role opponent;
- direct takedown differential counts player involvement in the opponent's
  death minus opponent involvement in the player's death.

Small kill counts are smoothed toward 50 percent before scoring:

```text
smoothed_kp = (early_takedowns + 1) / (team_early_kills + 2)

score = clamp(
  50
  + 40 * (player_smoothed_kp - opponent_smoothed_kp)
  + 10 * clamp(direct_takedown_diff, -2, 2),
  0,
  100
)
```

The score is `null` when neither team has a kill by 10 minutes. Confidence is
`low` with one to three total early kills and at most `medium` from four kills.
This is an early combat-impact measure, not a pure laning-skill measure.

### Health-pressure evidence
Health does not affect either score. For minutes 3 through 10, health pressure
is shown only when both same-role players:

- are alive and have valid timeline health values;
- have valid positions;
- are within 3,500 map units of each other.

The evidence counts snapshots at or below 35 percent health. At least three
comparable one-minute frames are required for a directional description.
Confidence is always `low` because Match-V5 timeline frames do not capture the
continuous trade, recall, potion, shield, or jungle-pressure sequence.

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
