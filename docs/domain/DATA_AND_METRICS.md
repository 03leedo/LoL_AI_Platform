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
- Gold Retention;
- Gambler Index;
- Teamfight Durability;
- Death Acceleration.

These names are discovery hints, not authoritative formulas.

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
