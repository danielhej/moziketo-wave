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
| GET | `/api/v1/browse` | Home sections (popular, latest, new) |
| GET | `/api/v1/tracks` | List tracks (`sort`, `genre`, `mood`, `tag` filters) |
| GET | `/api/v1/tracks/{slug}` | Track detail |
| GET | `/api/v1/tracks/{slug}/stream` | 302 redirect to CDN audio |
| GET | `/api/v1/tracks/{slug}/download` | 302 download redirect |
| GET | `/api/v1/artists` | List artists |
| GET | `/api/v1/artists/{slug}` | Artist hub + published tracks |
| GET | `/api/v1/search?q=` | Search tracks & artists |
| GET | `/api/v1/genres` | List genres |
| GET | `/api/v1/genres/{slug}/tracks` | Tracks by genre |
| GET | `/api/v1/moods` | List moods |
| GET | `/api/v1/moods/{slug}/tracks` | Tracks by mood |
| GET | `/api/v1/tags/{slug}/tracks` | Tracks by station tag |
| GET | `/api/v1/playlists` | Editorial playlists |
| GET | `/api/v1/playlists/{slug}` | Editorial playlist detail |
| GET | `/api/v1/albums` | List published albums |
| GET | `/api/v1/albums/{slug}` | Album detail + tracks |
| GET | `/api/v1/tracks/{slug}/similar` | Similar tracks |

### Personalization (Bearer required unless noted)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/me/plays/{slug}` | Record play (for history/recommendations) |
| GET | `/api/v1/me/history/recent` | Recently played (deduplicated) |
| DELETE | `/api/v1/me/history` | Clear play history |
| DELETE | `/api/v1/me/history/{slug}` | Remove track from history |
| GET | `/api/v1/me/recommendations` | Personalized sections |
| POST | `/api/v1/me/uploads/avatar` | Upload profile avatar → S3 |

### Auth

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/auth/register` | — | Create account (+ dev verify token if SMTP off) |
| POST | `/api/v1/auth/login` | — | Get JWT tokens |
| PATCH | `/api/v1/auth/me` | Bearer | Update display name / avatar URL |
| POST | `/api/v1/auth/change-password` | Bearer | Change password |
| POST | `/api/v1/auth/set-password` | Bearer | Set password (OAuth-only accounts) |
| POST | `/api/v1/auth/forgot-password` | — | Request password reset |
| POST | `/api/v1/auth/reset-password` | — | Reset password with token |
| POST | `/api/v1/auth/verify-email/request` | Bearer | Resend verification email |
| GET | `/api/v1/auth/verify-email/confirm` | — | Confirm email (`?token=`) |
| GET | `/api/v1/auth/oauth/{provider}` | — | OAuth redirect (google/github) |
| POST | `/api/v1/auth/oauth/exchange` | — | Exchange OAuth code for JWT |
| GET | `/api/v1/auth/me/oauth` | Bearer | List linked OAuth providers |
| DELETE | `/api/v1/auth/me/oauth/{provider}` | Bearer | Unlink OAuth provider |
| POST | `/api/v1/auth/refresh` | refresh token | Rotate tokens |
| GET | `/api/v1/auth/me` | Bearer | Current user |
| POST | `/api/v1/auth/logout` | refresh token | Revoke refresh token |

**Apple Sign In** is disabled by default (`OAUTH_APPLE_ENABLED=false`). Enable when Apple credentials are configured.

### Favorites & playlists (Bearer required)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/me/favorites` | List favorite tracks |
| POST | `/api/v1/me/favorites/{slug}` | Add favorite |
| DELETE | `/api/v1/me/favorites/{slug}` | Remove favorite |
| GET/POST | `/api/v1/me/playlists` | User playlists CRUD |

### Admin

| Method | Path | Header | Description |
|--------|------|--------|-------------|
| POST | `/api/v1/admin/import` | `X-Admin-Key` | Import from WP (`limit=0` = all pages) |
| POST | `/api/v1/admin/import-json` | `X-Admin-Key` | Import enriched JSON export |
| PATCH | `/api/v1/admin/tracks/{slug}` | `X-Admin-Key` | Patch track / publish state |
| POST | `/api/v1/admin/tracks/{slug}/publish` | `X-Admin-Key` | Publish track |
| POST | `/api/v1/admin/tracks/{slug}/unpublish` | `X-Admin-Key` | Unpublish track |
| PATCH | `/api/v1/admin/artists/{slug}` | `X-Admin-Key` | Patch artist |
| PATCH | `/api/v1/admin/playlists/{slug}` | `X-Admin-Key` | Patch editorial playlist |
| POST | `/api/v1/admin/albums` | `X-Admin-Key` | Create album |
| PATCH | `/api/v1/admin/albums/{slug}` | `X-Admin-Key` | Patch album / track order |
| POST | `/api/v1/admin/albums/{slug}/publish` | `X-Admin-Key` | Publish album |
| POST | `/api/v1/admin/albums/{slug}/unpublish` | `X-Admin-Key` | Unpublish album |
| POST | `/api/v1/admin/uploads` | `X-Admin-Key` | Upload cover/audio to S3 |
| GET | `/api/v1/admin/analytics/overview` | `X-Admin-Key` | Dashboard totals |
| GET | `/api/v1/admin/analytics/top-tracks` | `X-Admin-Key` | Top tracks by period |
| GET | `/api/v1/admin/analytics/top-artists` | `X-Admin-Key` | Top artists by period |
| GET | `/api/v1/admin/analytics/signups` | `X-Admin-Key` | User signups time series |
| GET | `/api/v1/admin/analytics/plays` | `X-Admin-Key` | Play events time series |

**Scheduled sync:** copy [`deploy/cron/import-catalog.sh`](deploy/cron/import-catalog.sh) to `/opt/moziketo/cron/` and add crontab `0 */6 * * *`.

**OAuth production setup:**

```bash
source ~/.cursor/skills/moziketo-access/oauth.env
./scripts/configure_oauth_production.sh
```

OpenAPI: `/openapi.json` · Swagger: `/docs`

## Database

```bash
alembic revision --autogenerate -m "description"  # new migration
alembic upgrade head
python scripts/seed.py                            # demo data
python scripts/import_wp.py --limit 0             # import all WP stations
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
# Set S3_* credentials for uploads; run migrations on deploy (docker entrypoint)
docker compose up -d
alembic upgrade head  # if not auto-run by container
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
