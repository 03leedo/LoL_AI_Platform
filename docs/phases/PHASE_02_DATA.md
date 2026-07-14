# Phase 2 — Versioned Data and Features

## Read
- `docs/domain/DATA_AND_METRICS.md`
- repository audit data sections

## Outcome
Stored source data can deterministically regenerate versioned features and evidence.

## Required
- idempotent ingestion;
- raw/normalized/derived separation using existing equivalents;
- source lineage;
- schema, rule, and feature version;
- completeness/confidence;
- rerunnable feature generation;
- representative and incomplete fixtures.

## Acceptance
- duplicate import does not duplicate normalized records;
- selected match features regenerate from stored source;
- derived records expose version and lineage;
- migrations include recovery notes;
- checks pass;
- stop.
