# Moziketo Wave

**FastAPI backend** for [موزیکتو](https://moziketo.ir) — Persian music streaming & download.

| Repo | Role |
|------|------|
| **moziketo-wave** (this) | FastAPI API — PostgreSQL catalog |
| [moz](https://github.com/thereisnofork/moz) | Next.js frontend |
| [moz-downloader](https://github.com/danielhej/moz-downloader) | Spotify ingest → S3 (`130.185.120.239`) |
| **moziketo-hand** | Production server `95.38.191.28` |

## Stack

FastAPI · PostgreSQL 16 · Redis · SQLAlchemy async · Alembic · JWT · Taskiq · Meilisearch (optional) · Docker

## Quick start

```bash
git clone git@github.com:danielhej/moziketo-wave.git
cd moziketo-wave
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env

docker compose up -d postgres redis meilisearch
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
| GET | `/api/v1/health` | Health + DB + Redis + S3 status |
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
| POST | `/api/v1/auth/me/change-email` | Bearer | Request email change (confirm via link) |
| GET | `/api/v1/auth/me/change-email/confirm` | — | Confirm email change (`?token=`) |
| GET | `/api/v1/auth/me/export` | Bearer | Export profile, favorites, playlists, history |
| DELETE | `/api/v1/auth/me` | Bearer | Soft-delete account (password or OAuth confirm) |
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

All admin routes require header **`X-Admin-Key: <ADMIN_API_KEY>`** (no JWT in this phase).

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/admin/catalog/summary` | Counts: tracks, artists, albums, users |
| GET | `/api/v1/admin/import/status` | Latest background import job |
| POST | `/api/v1/admin/import` | Enqueue WP import → **202** + `job_id` |
| POST | `/api/v1/admin/import/sync` | Synchronous import (legacy / small runs) |
| GET | `/api/v1/admin/jobs/{id}` | Background job status/result |
| POST | `/api/v1/admin/search/reindex` | Enqueue Meilisearch full reindex |
| GET | `/api/v1/admin/users` | Paginated users (masked email) |
| PATCH | `/api/v1/admin/users/{id}` | Activate/deactivate user |
| CRUD | `/api/v1/admin/webhooks` | Webhook subscriptions |
| GET | `/api/v1/admin/webhooks/{id}/deliveries` | Delivery log |
| POST | `/api/v1/admin/webhooks/{id}/test` | Send test payload |
| POST | `/api/v1/admin/import-json` | Import enriched JSON export |
| PATCH | `/api/v1/admin/tracks/{slug}` | Patch track / publish state |
| POST | `/api/v1/admin/tracks/{slug}/publish` | Publish track |
| POST | `/api/v1/admin/tracks/{slug}/unpublish` | Unpublish track |
| PATCH | `/api/v1/admin/artists/{slug}` | Patch artist |
| PATCH | `/api/v1/admin/playlists/{slug}` | Patch editorial playlist |
| POST | `/api/v1/admin/albums` | Create album |
| PATCH | `/api/v1/admin/albums/{slug}` | Patch album / track order |
| POST | `/api/v1/admin/albums/{slug}/publish` | Publish album |
| POST | `/api/v1/admin/albums/{slug}/unpublish` | Unpublish album |
| POST | `/api/v1/admin/uploads` | Upload cover/audio to S3 (presigned GET in response) |
| GET | `/api/v1/admin/analytics/overview` | Dashboard totals |
| GET | `/api/v1/admin/analytics/top-tracks` | Top tracks by period |
| GET | `/api/v1/admin/analytics/top-artists` | Top artists by period |
| GET | `/api/v1/admin/analytics/signups` | User signups time series |
| GET | `/api/v1/admin/analytics/plays` | Play events time series |

### Rate limits (public)

IP-based when `PUBLIC_RATE_LIMIT_ENABLED=true` (Redis):

| Scope | Default | Routes |
|-------|---------|--------|
| Search | 30/min | `GET /search` |
| Playback | 120/min | stream/download redirects |
| Catalog | 300/min | tracks, artists, browse |

Auth endpoints keep separate limits (`AUTH_RATE_LIMIT_ENABLED`).

### Background jobs & search

- **Taskiq worker** — `docker compose up worker` (same image, Redis broker)
- **Meilisearch** — optional; set `SEARCH_BACKEND=meili` after reindex (`POST /admin/search/reindex`)
- Stream/download URLs use **presigned S3 GET** when media is in your bucket (`S3_UPLOAD_ACL=private`)

**Scheduled sync:** copy [`deploy/cron/import-catalog.sh`](deploy/cron/import-catalog.sh) to `/opt/moziketo/cron/` and add crontab `0 */6 * * *` (expects HTTP **202** from async import).

### Ingest downloader

Spotify → S3 ingest runs on **[moz-downloader](https://github.com/danielhej/moz-downloader)** (`130.185.120.239`).

```http
POST /api/v1/admin/ingest/download
X-Admin-Key: ...
{"spotify_url":"...","title":"...","artist":"...","key":"slug.mp3"}
```

Env: `DOWNLOADER_URL`, `DOWNLOADER_SECRET` (see `deploy/wave.env.example`).

### Building an admin UI

Backend-only in Phase 3 — no bundled admin frontend. To build a panel (separate app or moz route):

1. Store **`ADMIN_API_KEY` server-side only** (Next.js API route / BFF). Never expose it in the browser bundle.
2. Call admin endpoints with `X-Admin-Key` from your server.
3. Use OpenAPI `/openapi.json` and Swagger `/docs` — tags `admin`, `admin-webhooks`.
4. CORS: allow your admin origin in `CORS_ORIGINS` if the BFF is on another domain.
5. Async import: poll `GET /admin/jobs/{id}` until `status` is `completed` or `failed`.

Key env vars: `ADMIN_API_KEY`, `MEILI_*`, `SEARCH_BACKEND`, `S3_PRESIGN_*`, `PUBLIC_RATE_LIMIT_*`, `TASKIQ_INLINE` (dev only).

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
# Set S3_*, ADMIN_API_KEY, optional MEILI_* / SEARCH_BACKEND
# docker compose includes wave, worker, meilisearch, postgres, redis, nginx
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
