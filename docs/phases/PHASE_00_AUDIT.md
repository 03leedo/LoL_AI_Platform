# Phase 0 — Repository Audit

## Outcome
Map the real system before changing product code.

## Inspect
- repository/monorepo structure;
- backend, frontend, worker, ML, and local components;
- runtimes and package managers;
- build, test, lint, type-check, migration commands;
- DB schema and migrations;
- Riot ingestion and timeline types;
- current indicators and exact formulas;
- AI integration;
- API/UI contracts;
- uncommitted user changes and current failures.

## Deliver
Create `docs/ai/REPOSITORY_AUDIT.md` containing:
- architecture and data flow;
- verified commands;
- feature and indicator map;
- API/DB contracts;
- test coverage;
- risks;
- file-level Phase 1 proposal;
- files not to touch yet.

## Acceptance
- no product code changed;
- formulas are documented from code;
- unknowns remain unknown;
- status file updated;
- stop after Phase 0.
