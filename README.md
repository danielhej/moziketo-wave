# Moziketo Wave

**FastAPI backend** for [موزیکتو](https://moziketo.ir) — Persian music streaming & download.

| Repo | Role |
|------|------|
| **moziketo-wave** (this) | FastAPI API — PostgreSQL catalog |
| [moz](https://github.com/thereisnofork/moz) | Next.js frontend |
| **moziketo-hand** | Production server `95.38.191.28` |

## Stack

FastAPI · PostgreSQL 16 · Redis · SQLAlchemy async · Alembic · Docker

## Quick start

```bash
git clone git@github.com:danielhej/moziketo-wave.git
cd moziketo-wave
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env

docker compose up -d postgres redis
alembic upgrade head
python scripts/seed.py
uvicorn app.main:app --reload --port 8000
```

- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/api/v1/health

## API v1

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health` | Health + DB status |
| GET | `/api/v1/tracks` | List tracks (paginated) |
| GET | `/api/v1/tracks/{slug}` | Track detail |
| GET | `/api/v1/artists` | List artists |
| GET | `/api/v1/artists/{slug}` | Artist hub + tracks |

OpenAPI: `/openapi.json`

## Database

```bash
alembic revision --autogenerate -m "description"  # new migration
alembic upgrade head
python scripts/seed.py                            # demo data
```

## DevOps

### CI / Deploy / Release

- **CI** — ruff, migrate, seed, pytest, push `ghcr.io/danielhej/moziketo-wave`
- **Deploy** — full stack to moziketo-hand (wave + web + postgres + nginx)
- **Release** — tag `v*.*.*` → GitHub Release + deploy

### GitHub Secrets

| Secret | Value |
|--------|-------|
| `DEPLOY_HOST` | `95.38.191.28` |
| `DEPLOY_USER` | `deploy` |
| `SSH_PRIVATE_KEY` | CI deploy key |

### Production (moziketo-hand)

```bash
ssh moziketo
cd /opt/moziketo
# wave.env + web.env from deploy/*.env.example
docker compose up -d
```

Nginx routes:
- `/` → Next.js
- `/api/` → FastAPI
- `/docs` → OpenAPI UI

## Development

```bash
ruff check app tests alembic scripts
pytest
docker compose up --build
```
