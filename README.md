# Karkov Weekend

> A closed-group family weekend planner — a web app that helps a small group of families plan shared summerhouse weekends together: sign-up, chores, activities, budget, chat and notifications.

The full product spec lives in [`prompt.md`](./prompt.md). The UI itself is in Danish (all copy lives in `frontend/src/i18n/da.ts`); this README is English-only.

## Features

### Families & users

- **Email/password login** with invite-based registration and JWT in httpOnly cookies.
- **Families & children**: every user belongs to exactly one family. Parents can create children (with or without their own login). Children may sign themselves in/out of events but never see the budget.
- **Admin tools**: bootstrap a whole family at once (parents + kids), then fire all invites in one go. Cancel/resend pending invites. Promote a parent to admin (the last admin can't be demoted). Delete families/users/children with confirmations.
- **Orphan-admin attach**: the bootstrap admin starts without a family. Either list them in the YAML import (they get attached automatically) or click the per-family "Tilknyt mig her" button on the admin settings page.
- **Age brackets** (admin-tunable): babies (0–2) don't count, kids (3–13) pay half, teens and adults pay full. Surfaced as badges anywhere children appear.

### Events

- **Create events** with name, date range, address, Google Maps URL, summerhouse URL (optional — can be filled in later as a notification), bed count and host.
- **Auto-generated days and six chores per day** (breakfast/lunch/dinner × prep/cleanup).
- **Inline editing** of every event detail (host or admin).
- **Plan next year** in one click (dates +1 year, same duration, host and links carried over).
- **Header summary**: title, date, address, host, open chores (click-through to the Chores tab), a mini map that opens Google Maps, and a per-family attendee strip with "X/Y days" badges.

### Sign-up, chores, activities

- **Per-day sign-up** (or all days at once); kids follow their parent automatically.
- **Bed-demand widget** showing peak occupancy per day against the bed count with red/amber/green bar (babies excluded).
- **Open chores** float to the top and can be claimed by anyone. Parents can claim on behalf of their kids. Host/admin can reassign.
- **Activities** per day — anyone can create, edit and sign up (themselves or their kids).

### Budget

- **Live preliminary balance per family** even before the event closes (paid, share, net).
- **Expense categories** with three flags (per-person / per-night / utility) — admin can add, rename, delete and toggle from `/indstillinger`. "Forbrug" is pre-flagged as a utility.
- **Expenses** have amount, category, description, an optional chore link and a payer. Admin can reassign the payer afterwards.
- **Utility-missing banner** plus a confirmation dialog when the host/admin closes the event, so forgotten utility receipts can't slip through.
- **Minimum-transfer settlement** between families (greedy two-pointer) shown as "Family A pays X kr to Family B" — fairness and transparency first.
- **Closing** locks the expenses, computes the final balance and emails every adult participant with payment instructions. Admin can still correct things afterwards as an escape hatch.

### Chat & notifications

- **Global chat room** with daily date separators and auto-scroll.
- **Unread divider**: a "Nye beskeder" line appears before the first message the user hasn't read yet; the view scrolls to it on open instead of jumping to the bottom. The marker advances after a short dwell, on tab-hide, and on unmount.
- **Live updates** via Server-Sent Events (`GET /api/v1/chat/stream`) — new messages stream in without a refresh. A 30-second safety-net poll takes over if the EventSource is broken.
- **System notifications**: creating an event, adding a summerhouse link to one without, sign-up changes, creating/joining an activity, claiming a chore and closing an event all post a system message in chat with an icon and a deep link — plus fan-out to opt-in adults over **email** and **web push** (excluding the actor).
- **Email notifications**: the DB outbox is always on; SMTP fires if `SMTP_HOST` is configured. Password-reset emails go through the same pipeline.
- **Web push**: opt-in per device on `/profil`. A service worker (`/service-worker.js`) shows the notification and deep-links to the event. The backend auto-generates a VAPID keypair in dev when `VAPID_PRIVATE_KEY` / `VAPID_PUBLIC_KEY` aren't set — production must always set them so subscriptions survive restarts.
- **Opt-in modal** on first login covers both email and push. Can be flipped at any time from the profile.

### Summerhouse scraper

- Host/admin can trigger a BeautifulSoup-based scrape of the summerhouse URL. We cache the title, a short description (Open Graph first, otherwise the `<h1>` + first long `<p>`, skipping generic marketing blurbs) and the hero image directly on the event.

### Look & feel

- **Light/dark mode** (system default), mobile-first with both a top nav (desktop) and a bottom nav (mobile).
- **Liquid-glass aesthetic**, the Geist sans-serif and smooth framer-motion animations.

## Stack

| Layer    | Tool                                                                                     |
| -------- | ---------------------------------------------------------------------------------------- |
| Backend  | Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · Pydantic v2 · pytest                    |
| DB       | PostgreSQL 16 (SQLite for local tests)                                                   |
| Auth     | Self-hosted JWT in httpOnly cookies (access 7d, refresh 30d), bcrypt                     |
| Frontend | Next.js 16 (App Router) · TypeScript · Tailwind v4 · shadcn/ui · TanStack Query · Vitest |
| E2E      | Playwright (chromium)                                                                    |
| Email    | DB outbox + stdout · optional SMTP via `SMTP_HOST` and friends                           |
| Push     | VAPID + `pywebpush` (backend) · service worker + `PushManager` (frontend)                |
| Scrape   | httpx + BeautifulSoup (cached on the event)                                              |
| Deploy   | Docker Compose (dev) · Docker Compose + Caddy (prod, automatic HTTPS)                    |

## Quick start (Docker)

```bash
cp .env.example .env
docker compose up --build
```

Once everything is running:

- Frontend: <http://localhost:3000>
- Backend: <http://localhost:8000> (health check at `/healthz`)
- Adminer (DB UI): <http://localhost:8080> (system: PostgreSQL, server: `db`)

The frontend container sits behind the `docker-frontend` profile. Day-to-day development runs the frontend on the host with `npm run dev`. To bring it up inside Docker:

```bash
docker compose --profile docker-frontend up
```

The default admin login (defined in `.env.example`) is `admin@karkov.example.com` / `change-me`. **Change it before using the app for anything real.**

## Local development without Docker

### Backend

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

Defaults to a local SQLite file (`karkov.db`). Set `DATABASE_URL` for Postgres.

Tests:

```bash
uv run pytest -q
```

### Frontend

```bash
cd frontend
npm install
npm run dev          # localhost:3000
npm test             # vitest unit tests
npm run test:e2e     # playwright (requires a running stack)
npm run lint         # eslint + react-hooks rules
```

## Configuration

Everything is configured through environment variables. `.env.example` shows the development defaults. The important keys:

| Variable                                        | Meaning                                                                                            |
| ----------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `DATABASE_URL`                                  | SQLAlchemy URL. Defaults to Postgres in Docker, SQLite when running locally without it.            |
| `SECRET_KEY`                                    | JWT signing key. At least 32 chars in production.                                                  |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` / `ADMIN_NAME` | Used to seed the first admin user.                                                                 |
| `PUBLIC_BASE_URL`                               | Base URL used inside invite emails.                                                                |
| `COOKIE_SECURE` / `COOKIE_SAMESITE`             | Cookie flags (set `COOKIE_SECURE=true` in production).                                             |
| `CORS_ORIGINS`                                  | JSON list of allowed origins.                                                                      |
| `SMTP_HOST` (+ port, user, password, TLS)       | Set if email should actually be delivered. If empty, messages only land in the outbox + stdout.    |
| `VAPID_PRIVATE_KEY` / `VAPID_PUBLIC_KEY`        | Web-push keys. If empty, a temporary pair is generated in dev (subscriptions are lost on restart). |
| `VAPID_SUBJECT`                                 | `mailto:` or URL identifying the sender in push headers.                                           |
| `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY`               | Frontend key. If set: uses the Maps Embed API. If empty: keyless `?q=…&output=embed`.              |

## Production

`docker-compose.prod.yml` brings up Postgres, the backend, the frontend and a Caddy reverse proxy with automatic Let's Encrypt:

```bash
cp .env.example .env
$EDITOR .env                  # PUBLIC_BASE_URL (invite links), secrets, admin password, SMTP, VAPID
docker compose -f docker-compose.prod.yml up -d --build
```

The production frontend build **pins** **`NEXT_PUBLIC_API_BASE_URL=/api/v1`** in `docker-compose.prod.yml` so API calls stay on the **same host** as the UI (LAN IP or public hostname). That avoids cross-origin cookie/CORS problems. Do **not** rely on `NEXT_PUBLIC_*` lines copied from `.env.example` for this Docker prod image.

**Router** (e.g. UniFi): forward **WAN TCP 80 → host:80** and **WAN TCP 443 → host:443**. Both are usually required for Let's Encrypt and HTTPS.

**Troubleshooting:** If LAN/WAN cannot reach the site: allow **80/tcp** and **443/tcp** on the firewall (e.g. UFW). If `docker ps` shows Caddy **without** `0.0.0.0:80->80/tcp`, free ports 80/443 and recreate the stack (`docker compose -f docker-compose.prod.yml down && docker compose -f docker-compose.prod.yml up -d`).

[`Caddyfile`](./Caddyfile) is set up for **karkovweekend.dk** (HTTPS plus plain HTTP for bare IP/LAN testing); edit the site block if you use another domain.

## Not in this release (deferred)

- Event photo upload + gallery (group and individual photos per event, historical slideshow mode).
- Bulk import of past events / photos.
- Database backup / restore.
- Auto-creation of a group-photo activity on the day with the most attendees.
- Smarter chore generation (first day without breakfast, last day without dinner, an "assistant" role).

## Repo layout

```text
.
├── backend/                 # FastAPI app
│   ├── app/
│   │   ├── api/v1/          # routers (auth, families, events, expenses, chors, activities, chat, admin, ...)
│   │   ├── core/            # config, db, security, deps
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── schemas/         # Pydantic models
│   │   ├── services/        # pricing, balance, events_factory, email, notifications, scrape, uploads, push
│   │   └── seeds.py
│   ├── scripts/             # developer utilities (e.g. seed_event.py)
│   ├── tests/               # pytest (api + services)
│   └── alembic/
├── frontend/                # Next.js 16 app
│   ├── public/              # service-worker.js, static assets
│   ├── src/app/             # routes (auth + app shell, /chat, /arrangementer/[id], …)
│   ├── src/components/      # UI + shadcn primitives + app-shell
│   ├── src/lib/             # api client, auth, types, format, age, utils, push
│   ├── src/i18n/da.ts       # all Danish copy
│   └── e2e/                 # Playwright smoke
├── docker-compose.yml       # dev stack
├── docker-compose.prod.yml  # prod stack
├── Caddyfile
├── prompt.md                # full product spec
└── .env.example
```
