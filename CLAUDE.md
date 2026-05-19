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
  Gmail poll (default every 30m) and the nightly SQLite `.backup` job.
  Auth is Cloudflare Access JWT, verified per request via the
  `Cf-Access-Jwt-Assertion` header.
- **Frontend**: nginx on port 80, serves the built React bundle and
  proxies `/api/*` to the backend. The proxy MUST forward the
  `Cf-Access-Jwt-Assertion` header — set in `frontend/nginx.conf`.
- **DB**: SQLite at `/data/alerts.db`. Backups land in `/data/backups/`,
  retained for `BACKUP_KEEP_DAYS` (default 30) days.

## Ingestion: Gmail, not RSS

Google deprecated RSS delivery on Google Alerts for many accounts, so
this app reads Alert emails directly from Gmail via the Gmail API.

- **Scope**: `gmail.readonly` only. We never write to Gmail.
- **OAuth flow** lives in [`routers/oauth.py`](backend/app/routers/oauth.py).
  Refresh token is stored in the `setting` table (key `google_refresh_token`).
- **Poller** is [`services/gmail_poller.py`](backend/app/services/gmail_poller.py).
  Query: `from:googlealerts-noreply@google.com newer_than:{N}d`. Each
  message is parsed by BeautifulSoup; we extract every `<a>` whose href
  starts with `google.com/url`, unwrap to the real URL, and pull a
  snippet from the next sibling.
- **Bucketing**: each Alert has a `subject_match` field (default = the
  alert's name). On poll we case-insensitively check whether
  `alert.subject_match` appears in the email's Subject. Longest match
  wins. Unmatched emails go into an auto-created **Unsorted** alert.
- **Dedup**: `item.guid = f"{gmail_message_id}:{entry_index}"`. The
  poller short-circuits if any item with `guid LIKE '{msg_id}:%'` is
  already present.

## Domain model

- `alert` — one topic bucket. `subject_match` is the substring matched
  against incoming email Subject lines. `feed_url` is a legacy nullable
  column from when ingestion was RSS-based; unused.
- `item` — one row per parsed result link. PK is `sha1(msg_id + index)`.
  Stores `link` (unwrapped from Google's redirect) and `original_link`.
  Indexed on `(alert_id, published_at)`.
- `item_state` — per-item local marks: `read_at`, `saved_at`, `hidden_at`.
- `setting` — generic key-value store. Holds the OAuth refresh token,
  the connected Gmail address, the granted scopes, and the last-poll
  timestamp under `google_*` keys.

## Adding a new feature

1. **Backend**: add the route under `backend/app/routers/`, register it
   in `app/main.py`. Add model/schema changes via a new Alembic
   migration. Test with `curl http://localhost:8001/api/...` (skip the
   JWT header in local dev if `CF_ACCESS_AUD` is empty — auth is
   bypassed).
2. **Frontend**: add the component under `src/components/`, hook into
   the sidebar or item list. API calls go through `src/api.ts`. State is
   TanStack Query with one root key per resource (`["alerts"]`,
   `["items", filters]`, `["digest", window]`, `["google", "status"]`).

## Deployment

Portainer git-stack on NAS3 endpoint 3, stack id 69, pulling from
`notoriousrig/crbox-alerts` on the `main` branch. Updates pushed to
GitHub; Portainer redeploys on webhook or manual "Pull and redeploy".

Cloudflare Tunnel ingress for `alerts.crbox.ca` points at the shared
traefik on NAS3 (`http://traefik:8443`), and traefik dispatches by Host
header to this stack's `frontend` service.

### Required env vars (set in Portainer)

- `CF_ACCESS_TEAM_DOMAIN=crbox.cloudflareaccess.com`
- `CF_ACCESS_AUD=06bb0121c9032fe3c7d2a2059e99603dc95e3173ae0dfe60adfe432499e96d6f`
- `GOOGLE_OAUTH_CLIENT_ID=<from Google Cloud Console>`
- `GOOGLE_OAUTH_CLIENT_SECRET=<from Google Cloud Console>`
- `PUBLIC_BASE_URL=https://alerts.crbox.ca`
- `LOG_LEVEL=INFO`
- `POLL_INTERVAL_MINUTES=30`
