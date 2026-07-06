# Sprint 1: Foundation

## Objective

Create a local full-stack foundation that can query Riot API data, persist the
first normalized records, and give the frontend a stable API to build on.

## Deliverables

- Docker Compose stack for PostgreSQL, FastAPI, and Next.js.
- Backend health endpoint with database visibility.
- Riot Account-V1 and Match-V5 client boundaries.
- Summoner lookup endpoint by Riot ID.
- Recent match IDs endpoint.
- Match detail endpoint.
- Initial PostgreSQL tables:
  - `summoners`
  - `riot_matches`
  - `summoner_matches`
- Frontend dashboard shell with health and lookup states.

## Acceptance criteria

- `docker compose up --build` starts all services.
- `GET /api/v1/health` returns API status and database status.
- With `RIOT_API_KEY` configured, summoner lookup returns Riot account and
  summoner profile data.
- The frontend can call the backend and show loading, success, and error
  states without a page refresh.

## Deferred to later sprints

- Timeline feature extraction.
- Win probability calculation.
- Agent-generated reports.
- Redis caching.
- ML training jobs and model serving.
