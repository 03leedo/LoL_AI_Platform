# LoL AI Platform

AI-assisted League of Legends analysis platform built around Riot API data,
timeline analytics, win probability, machine learning, and agent-generated
coaching reports.

## Sprint 1 target

The first milestone is a working local foundation:

- Next.js frontend with a summoner lookup workspace.
- FastAPI backend with health checks and Riot API service boundaries.
- PostgreSQL schema for summoners, matches, and participant summaries.
- Docker Compose environment for frontend, backend, and database.
- Environment variable layout ready for a Riot API key.

## Project layout

```text
.
├── backend/          # FastAPI, SQLAlchemy, Riot API client
├── frontend/         # Next.js, TypeScript, Tailwind CSS
├── docs/             # Sprint notes and implementation decisions
├── docker-compose.yml
└── .env.example
```

## Local setup

```bash
cp .env.example .env
```

Add a Riot development key to `.env`:

```bash
RIOT_API_KEY=RGAPI_your_key_here
```

Start the stack:

```bash
docker compose up --build
```

Open:

- Frontend: http://localhost:3000
- Backend health: http://localhost:8000/api/v1/health
- API docs: http://localhost:8000/docs

## Database migrations

Schema is managed with Alembic (`backend/alembic.ini`, `backend/migrations/`).
In development the backend still auto-creates missing tables on startup
(`AUTO_CREATE_TABLES`), so migrations are optional locally.

```bash
cd backend
alembic stamp head     # one-time, for a dev DB that predates Alembic
alembic upgrade head   # fresh DB, or applying new revisions
```

## Tests

```bash
backend/.venv/bin/python -m pytest   # config in pytest.ini (pythonpath=backend)
```

## Current API surface

- `GET /api/v1/health`
- `GET /api/v1/riot/account/{game_name}/{tag_line}`
- `GET /api/v1/riot/summoner/{game_name}/{tag_line}`
- `GET /api/v1/riot/summoner/{game_name}/{tag_line}/matches?count=10`
- `GET /api/v1/riot/matches/{match_id}`

## Documentation

- [docs/master-plan.md](docs/master-plan.md) — current roadmap: milestones
  M0-M5 (MVP) and E1-E3 (replay companion, highlight/vision, live agent),
  metric catalog, data-reality notes, and architecture evolution.
- [docs/PRD-expansion.md](docs/PRD-expansion.md) — product spec (feature
  definitions, scoring design, policy constraints).
- [docs/development-plan.md](docs/development-plan.md) — superseded sprint
  plan, kept for history.

## Roadmap snapshot

1. M0 Foundation hardening: rate limiter, DB-first caching, migrations,
   moments/metric_scores tables, frontend route split.
2. M1 New metrics + kill/death heatmap + rule-based win curve.
3. M2 Role analysis tab + player scorecard (multi-match ingestion).
4. M3 AI aggregate report with cited evidence.
5. M4 High-tier benchmark comparison (+ ML win model later).
6. M5 Production hardening. Then E1-E3 expansions (replay companion,
   highlight/vision, live event agent).
