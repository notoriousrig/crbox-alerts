# CLAUDE.md — crbox-alerts

Google Alerts digest at `alerts.crbox.ca`. Mirrors the crbox-tube pattern:
FastAPI backend + React/Vite frontend behind nginx, single Docker Compose
stack, deployed via Portainer git-stack on NAS3.

## Local dev

```bash
cp .env.example .env
docker compose up --build
```

For frontend HMR: `cd frontend && npm install && npm run dev` — proxies
`/api` to `http://localhost:8000`. The backend binds the SQLite DB at
`./data/alerts.db` via the volume mount.

## Architecture

- **Backend**: FastAPI on port 8000, SQLAlchemy 2.x ORM, Alembic
  migrations applied on container startup. APScheduler runs the periodic
  RSS poll (default every 30m) and the nightly SQLite `.backup` job. Auth
  is Cloudflare Access JWT, verified per request via the
  `Cf-Access-Jwt-Assertion` header.
- **Frontend**: nginx on port 80, serves the built React bundle and
  proxies `/api/*` to the backend. The proxy MUST forward the
  `Cf-Access-Jwt-Assertion` header — set in `frontend/nginx.conf`.
- **DB**: SQLite at `/data/alerts.db`. Backups land in `/data/backups/`,
  retained for `BACKUP_KEEP_DAYS` (default 30) days.

## Domain model

- `alert` — one Google Alert topic. Holds the user-pasted RSS `feed_url`
  plus ETag/Last-Modified for conditional GET.
- `item` — one row per RSS entry. PK is `sha1(alert_id + guid)`. Stores
  `link` (unwrapped from Google's redirect) and `original_link` (the raw
  redirect) for debug. Indexed on `(alert_id, published_at)`.
- `item_state` — per-item local marks: `read_at`, `saved_at`, `hidden_at`.
  Absence of a row = unread / unsaved / not hidden.
- `setting` — generic key-value config store.

## RSS polling

- **Feed URL format**: `https://www.google.com/alerts/feeds/<user_id>/<alert_id>`
  (the user pastes this when creating an alert).
- **Conditional GET** via `If-None-Match` / `If-Modified-Since`, cached on
  the `alert` row.
- **Dedup** by `(alert_id, guid)`. Updates title / snippet / link on existing
  rows since Google sometimes edits these post-publish.
- **URL unwrapping**: every link in a Google Alerts feed is wrapped in
  `https://www.google.com/url?…&url=<real>&…`. [`services/url_unwrap.py`](backend/app/services/url_unwrap.py)
  extracts the underlying URL and `source_domain`.
- **Retention**: prune items older than `ITEM_RETENTION_DAYS` (default 180)
  unless `saved_at` is set.

## Adding a new feature

1. **Backend**: add the route under `backend/app/routers/`, register it
   in `app/main.py`. Add model/schema changes via Alembic
   (`alembic revision --autogenerate -m "..."`). Test with
   `curl http://localhost:8001/api/...` (skip the JWT header in local
   dev if `CF_ACCESS_AUD` is empty — auth is bypassed).
2. **Frontend**: add the component under `src/components/`, hook into
   the sidebar or item list. API calls go through `src/api.ts`. State is
   TanStack Query with one root key per resource (`["alerts"]`,
   `["items", filters]`, `["digest", window]`).

## Deployment

Portainer git-stack on NAS3 endpoint 3, pulling from
`notoriousrig/crbox-alerts` on the `main` branch. Updates pushed to
GitHub; Portainer redeploys on webhook or manual "Pull and redeploy".

Cloudflare Tunnel ingress for `alerts.crbox.ca` points at the shared
traefik on NAS3 (`http://traefik:8443`), and traefik dispatches by Host
header to this stack's `frontend` service.
