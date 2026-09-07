# Moziketo Wave

**FastAPI backend** for [موزیکتو](https://moziketo.ir) — Persian music streaming & download.

| Repo | Role |
|------|------|
| **moziketo-wave** (this) | FastAPI API — PostgreSQL catalog |
| [moz](https://github.com/thereisnofork/moz) | Next.js frontend |
| **moziketo-hand** | Production server `95.38.191.28` |

## Stack

FastAPI · PostgreSQL 16 · Redis · SQLAlchemy async · Alembic · JWT · Docker

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
- Swagger: http://localhost:8000/docs
- Health: http://localhost:8000/api/v1/health

## API v1

### Catalog (public)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health` | Health + DB + Redis status |
| GET | `/api/v1/tracks` | List published tracks (paginated) |
| GET | `/api/v1/tracks/{slug}` | Track detail |
| GET | `/api/v1/tracks/{slug}/stream` | 302 redirect to CDN audio |
| GET | `/api/v1/tracks/{slug}/download` | 302 download redirect |
| GET | `/api/v1/artists` | List artists |
| GET | `/api/v1/artists/{slug}` | Artist hub + published tracks |
| GET | `/api/v1/search?q=` | Search tracks & artists |

### Auth

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/auth/register` | — | Create account |
| POST | `/api/v1/auth/login` | — | Get JWT tokens |
| POST | `/api/v1/auth/refresh` | refresh token | Rotate tokens |
| GET | `/api/v1/auth/me` | Bearer | Current user |
| POST | `/api/v1/auth/logout` | refresh token | Revoke refresh token |

### Favorites (Bearer required)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/me/favorites` | List favorite tracks |
| POST | `/api/v1/me/favorites/{slug}` | Add favorite |
| DELETE | `/api/v1/me/favorites/{slug}` | Remove favorite |

### Admin

| Method | Path | Header | Description |
|--------|------|--------|-------------|
| POST | `/api/v1/admin/import` | `X-Admin-Key` | Import from moziketo.ir WP |

OpenAPI: `/openapi.json` · Swagger: `/docs`

## Database

```bash
alembic revision --autogenerate -m "description"  # new migration
alembic upgrade head
python scripts/seed.py                            # demo data
python scripts/import_wp.py --limit 50            # import from WordPress
```

## DevOps

### CI / Deploy / Release

- **CI** — ruff, migrate, seed, pytest (+ Redis), push `ghcr.io/danielhej/moziketo-wave`
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

Production URLs:
- API: https://api.moziketo.ir
- PWA: https://pwa.moziketo.ir
- Media CDN: https://dl.moziketo.ir/music/

## Development

```bash
ruff check app tests alembic scripts
pytest
docker compose up --build
```
