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

## Current API surface

- `GET /api/v1/health`
- `GET /api/v1/riot/account/{game_name}/{tag_line}`
- `GET /api/v1/riot/summoner/{game_name}/{tag_line}`
- `GET /api/v1/riot/summoner/{game_name}/{tag_line}/matches?count=10`
- `GET /api/v1/riot/matches/{match_id}`

## Sprint roadmap

1. Foundation: app skeleton, Riot lookup, match details, initial schema.
2. Timeline analytics: timeline ingestion, feature extraction, charts.
3. Win probability: rule-based model, graphing, feature refinement.
4. AI agent: automated match review, pattern detection, coaching report.
5. Machine learning: dataset, model training, model replacement, SHAP.
6. Production: cache, indexing, scheduled ingestion, load tests, CI/CD.
