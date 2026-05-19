# crbox-alerts

Self-hosted Google Alerts reader. Each Google Alert becomes a topic bucket
in the app; items roll up into an inbox, daily/weekly digests, or per-alert
views, with local read/saved/hidden marks. Single user, behind Cloudflare
Tunnel + Access at `alerts.crbox.ca`.

## Stack

- **FastAPI** + APScheduler — periodic Google Alerts RSS polling
- **SQLite** — one-file DB, nightly `.backup` to `./data/backups`
- **React + Vite + Tailwind + TanStack Query** — sidebar + item list + digest
- **Cloudflare Tunnel + Access** — no exposed ports, edge auth

## Ingestion: how to get your Google Alerts in here

Google Alerts ships an RSS feed for each alert, but you have to ask for it.

1. Open [google.com/alerts](https://www.google.com/alerts).
2. Click the **pencil** next to an alert → **Show options**.
3. Set **Deliver to: RSS feed** → **Save**.
4. Click the orange RSS icon next to the alert and **copy the feed URL**.
5. In crbox-alerts, click **+** in the sidebar, paste the URL, give it a
   name. The backend validates the feed on save and triggers an initial
   poll.

Subsequent pulls happen on the schedule (default every 30 minutes), with
ETag/If-Modified-Since so we don't hammer Google.

## Local dev

```bash
cp .env.example .env   # leave CF_ACCESS_AUD blank to bypass auth locally
docker compose up --build
```

- Frontend (built image): http://localhost:8080
- Backend API: http://localhost:8001/api/docs

For frontend HMR:

```bash
cd frontend && npm install && npm run dev
# Vite on http://localhost:5173, /api proxied to :8000
```

## Production deployment

See [CLOUDFLARE_SETUP.md](CLOUDFLARE_SETUP.md) for the one-time tunnel +
Access wiring. The stack runs on NAS3 (192.168.2.30) as a Portainer
git-stack pulling from `notoriousrig/crbox-alerts`.

## Data layout

```
data/
├── alerts.db        # SQLite — primary DB
└── backups/         # nightly sqlite3 .backup snapshots
```

## API docs

OpenAPI at `https://alerts.crbox.ca/api/docs` (behind Cloudflare Access)
or `http://localhost:8001/api/docs` locally.
