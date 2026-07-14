# Phase 3 — Episode Engine

## Read
- `docs/domain/ANALYSIS_RULES.md`
- `docs/domain/DATA_AND_METRICS.md`

## Outcome
Group related fight, death, and objective events into deterministic review episodes.

## Required
- centralized, versioned thresholds;
- fight grouping by time and available position context;
- death context with pre-state, exchange, and 30/60/90-second follow-up;
- objective availability/readiness;
- explicit objective-analyzable predicate;
- confidence reduction for missing data.

## Critical tests
- one objective loss is not multiplied by several deaths;
- distant kills are not merged by time alone;
- missing positions lower confidence;
- denominator is reproducible;
- map-side handling is symmetric.

Stop after this phase.
