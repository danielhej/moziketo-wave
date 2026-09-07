# Moziketo Wave

**FastAPI backend** for [موزیکتو](https://moziketo.ir) — Persian music streaming and download platform.

Part of the greenfield Moziketo stack (replacing legacy WordPress):

| Repo | Role |
|------|------|
| **moziketo-wave** (this) | FastAPI API — catalog, auth, media |
| [moziketo-web](https://github.com/danielhej/moziketo-web) | Next.js frontend |
| **moziketo-hand** | Production server (`95.38.191.28`) |

## Stack

- **FastAPI** + Pydantic v2
- **PostgreSQL** + SQLAlchemy async (Alembic migrations — coming)
- **Redis** — cache, sessions, rate limits
- **Docker** — deploy on `moziketo-hand`

## Quick start

```bash
# Clone
git clone git@github.com:danielhej/moziketo-wave.git
cd moziketo-wave

# Local dev (Python 3.12+)
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload --port 8000

# Or Docker Compose (API + Postgres + Redis)
docker compose up --build
```

- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/api/v1/health

## API (v1)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health` | Health check |
| GET | `/api/v1/tracks` | List tracks |
| GET | `/api/v1/tracks/{slug}` | Track detail |
| GET | `/api/v1/artists` | List artists |
| GET | `/api/v1/artists/{slug}` | Artist detail |

OpenAPI schema: `/openapi.json` — use for Next.js client codegen.

## Project layout

```
app/
├── main.py           # FastAPI app factory
├── core/             # config, logging
├── api/v1/           # route handlers
└── schemas/          # Pydantic models
tests/
docker-compose.yml
Dockerfile
```

## Deploy (moziketo-hand)

```bash
ssh moziketo
cd /opt/moziketo
docker compose up -d --build wave
```

Server path: `/opt/moziketo/wave` (or monorepo compose at `/opt/moziketo`).

## Development

```bash
ruff check app tests
pytest
```

## License

Private — Moziketo project.
