# crbox-alerts

Self-hosted Google Alerts reader. The app reads your Google Alerts emails
directly from Gmail (read-only, via OAuth), parses each result out of the
HTML body, and buckets items into per-topic alerts with an inbox, daily/
weekly digests, and local read/saved/hidden marks. Single user, behind
Cloudflare Tunnel + Access at `alerts.crbox.ca`.

## Stack

- **FastAPI** + APScheduler — periodic Gmail polling
- **SQLite** — one-file DB, nightly `.backup` to `./data/backups`
- **React + Vite + Tailwind + TanStack Query** — sidebar + item list + digest
- **Cloudflare Tunnel + Access** — no exposed ports, edge auth
- **Gmail API** — scope `gmail.readonly`; refresh token stored locally in SQLite

## How ingestion works

Google quietly removed the RSS-delivery option for many accounts in 2025,
so crbox-alerts reads Google Alerts emails directly from Gmail instead:

1. You authorize the app once (Connect Gmail button) — read-only scope.
2. The backend polls Gmail every 30 minutes for messages matching
   `from:googlealerts-noreply@google.com newer_than:7d`.
3. For each new message, it parses the HTML body into individual results
   (title + snippet + cleaned source URL) and buckets them by matching the
   email's Subject line against each alert's name (or its
   "Subject match" override). Unmatched emails go into an auto-created
   **Unsorted** bucket.
4. Items dedup on the Gmail message ID + per-message index, so re-polling
   doesn't duplicate.

The app never writes to your Gmail — it doesn't mark messages read, label
them, or delete them.

## One-time Google Cloud setup

(Already done if you're using the deployed instance.)

1. <https://console.cloud.google.com> → create project → enable Gmail API.
2. OAuth consent screen → External → add yourself as a test user.
3. Credentials → Create OAuth client ID → Web application →
   Authorized redirect URI: `https://alerts.crbox.ca/api/auth/google/callback`.
4. Set `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET` env vars
   on the stack.
5. Visit the app → Connect Gmail → grant access. Refresh token is stored
   in the local SQLite (`setting` table).

## Local dev

```bash
cp .env.example .env   # leave CF_ACCESS_AUD blank to bypass auth locally
# Optional: paste client_id/secret if you want to test the OAuth flow
docker compose up --build
```

- Frontend: http://localhost:8080
- Backend API: http://localhost:8001/api/docs

For frontend HMR:

```bash
cd frontend && npm install && npm run dev
# Vite on http://localhost:5173, /api proxied to :8000
```

## Production deployment

See [CLOUDFLARE_SETUP.md](CLOUDFLARE_SETUP.md). Runs on NAS3 as Portainer
git-stack 69, pulling `notoriousrig/crbox-alerts`.

## Data layout

```
data/
├── alerts.db        # SQLite — primary DB (includes the OAuth refresh token!)
└── backups/         # nightly sqlite3 .backup snapshots
```

The refresh token lives in the `setting` table. Treat backups like
secrets.

## API docs

OpenAPI at `https://alerts.crbox.ca/api/docs` (behind Cloudflare Access)
or `http://localhost:8001/api/docs` locally.
