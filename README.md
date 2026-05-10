# Karkov Weekend

> Familieweekendens samlingssted — en webapp der hjælper en lukket gruppe danske familier med at planlægge fælles weekendture i feriehus: tilmelding, opgaver, aktiviteter, budget, chat og notifikationer.

Den fulde produktbeskrivelse ligger i [`prompt.md`](./prompt.md).

[Read this in English ↓](#english)

---

## Funktioner

### Familier & brugere

- **Email/adgangskode-login** med invitationsbaseret registrering og JWT i httpOnly-cookies.
- **Familier & børn**: hver bruger tilhører én familie. Forældre kan oprette børn (med eller uden egen login). Børn må logge ind og melde sig til/fra, men ikke se budget.
- **Admin-værktøjer**: opret familier komplet (forældre + børn) først og send invitationerne i ét hug. Cancel/resend pending invites. Promovér forælder til admin (sidste admin kan ikke degraderes). Slet familier/brugere/børn med bekræftelse.
- **Aldersbrackets** (admin-justerbare): baby (0–2) tæller ikke, barn (3–13) halv pris, teenager+voksen fuld pris. Vises som badges overalt hvor børn nævnes.

### Arrangementer

- **Opret event** med navn, dato, adresse, Google-Maps-URL, feriehus-URL (valgfri — kan tilføjes senere som notifikation), antal sengepladser, host.
- **Auto-genererede dage og 6 gøremål per dag** (morgenmad/frokost/aftensmad × forberedelse/oprydning).
- **Inline-redigering** af alle event-detaljer (host eller admin).
- **Plan næste år** med ét klik (datoer +1 år, samme længde, host og links overført).
- **Headeropsummering**: titel, dato, adresse, host, ledige gøremål (klikbar genvej til Chors-tab), mini-kort der åbner i Google Maps, og en deltager-strip grupperet pr. familie med "X/Y dage" badges.

### Tilmelding, gøremål, aktiviteter

- **Tilmelding pr. dag** (eller alle på én gang); børn følger automatisk forælderen.
- **Bed-demand widget** der viser top-belægning per dag mod sengetal med rød/gul/grøn-bar (babyer ekskluderet).
- **Ledige gøremål** vises øverst og kan tages af alle. Forældre kan tage på vegne af deres børn. Host/admin kan omfordele.
- **Aktiviteter** pr. dag — alle kan oprette, redigere og tilmelde sig (eller deres børn).

### Budget

- **Live foreløbigt regnskab pr. familie** allerede inden eventet er afsluttet (betalt, andel, netto).
- **Udgiftskategorier** med tre flag (per-person / per-nat / forbrug) — admin kan tilføje, omdøbe, slette og toggle fra `/indstillinger`. "Forbrug" er forhåndsmarkeret som utility.
- **Udgifter** har beløb, kategori, beskrivelse, valgfri tilknytning til et gøremål og en betaler. Admin kan ændre betaleren bagefter.
- **Forbrug-mangler**-banner og en bekræftelses-dialog når host/admin afslutter, så glemt forbrug ikke smutter med.
- **Færrest mulige overførsler** mellem familier (greedy two-pointer) vises som "Familie A betaler X kr til Familie B" — fairness og gennemsigtighed first.
- **Afslutning** låser udgifterne, beregner endeligt regnskab og emailer alle voksne deltagere med betalingsinstruktioner. Admin kan stadig korrigere efterfølgende som nødløsning.

### Chat & notifikationer

- **Globalt chat-rum** med daglige date-separators og auto-scroll. Polling hver 5. sekund.
- **Notifikationerne**: oprettelse af event, tilføjelse af feriehus til et event uden, ændringer i tilmelding, oprettelse/tilmelding til aktivitet, valg af gøremål og afslutning af event ryger som system-besked i chatten med ikon og link til eventet.
- **Email-notifikationer** til opt-in voksne (eksklusive aktøren). DB-outbox er altid på; SMTP fyrer hvis `SMTP_HOST` er sat.
- **Opt-in modal** vises ved første login, kan altid ændres fra profilen.
- **Web-push** (telefon-notifikationer) er klargjort i interfacet, men implementeres senere.

### Feriehus-scrape

- Host/admin kan trigge en BeautifulSoup-baseret scrape af feriehus-URL'en. Vi cacher titel, kort beskrivelse (Open Graph først, ellers `<h1>` + første lange `<p>`, med skip af generiske marketing-blurbs) og hero-billede direkte på eventet.

### Look & feel

- **Light/dark mode** (system default), mobil-first med både top-nav (desktop) og bottom-nav (mobil).
- **Liquid-glass-æstetik**, sans-serif Geist, smooth framer-motion-animationer.
- **Dansk overalt** — al copy lever i `frontend/src/i18n/da.ts`.

## Stack

| Lag       | Værktøj                                                                                  |
| --------- | ---------------------------------------------------------------------------------------- |
| Backend   | Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · Pydantic v2 · pytest                    |
| DB        | PostgreSQL 16 (SQLite til lokale tests)                                                  |
| Auth      | Selvhostet JWT i httpOnly-cookies (access 7d, refresh 30d), bcrypt                       |
| Frontend  | Next.js 16 (App Router) · TypeScript · Tailwind v4 · shadcn/ui · TanStack Query · Vitest |
| Test E2E  | Playwright (chromium)                                                                    |
| Email     | DB-outbox + stdout · valgfri SMTP via `SMTP_HOST` m.fl.                                  |
| Scrape    | httpx + BeautifulSoup (cache på eventet)                                                 |
| Deploy    | Docker Compose (dev) · Docker Compose + Caddy (prod, auto-HTTPS)                         |

## Hurtigstart (Docker)

```bash
cp .env.example .env
docker compose up --build
```

Når alt kører:

- Frontend: <http://localhost:3000>
- Backend: <http://localhost:8000> (helbredstjek `/healthz`)
- Adminer (DB-UI): <http://localhost:8080> (system: PostgreSQL, server: `db`)

Frontend-containeren er bag profilen `docker-frontend`. I dagligt udviklingsarbejde kør den på værten med `npm run dev`. For at få den med op i Docker:

```bash
docker compose --profile docker-frontend up
```

Standard admin-login (defineret i `.env.example`): `admin@karkov.example.com` / `change-me`. **Skift før du tager det i brug.**

## Lokal udvikling uden Docker

### Backend

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

Kører som standard mod en lokal SQLite (`karkov.db`). Sæt `DATABASE_URL` for Postgres.

Test:

```bash
uv run pytest -q
```

### Frontend

```bash
cd frontend
npm install
npm run dev          # localhost:3000
npm test             # vitest unit tests
npm run test:e2e     # playwright (kræver kørende stack)
npm run lint         # eslint + react-hooks regler
```

## Konfiguration

Alt sættes via miljøvariabler. `.env.example` viser standardværdier for udvikling. Vigtige nøgler:

| Variabel                                        | Forklaring                                                                          |
| ----------------------------------------------- | ----------------------------------------------------------------------------------- |
| `DATABASE_URL`                                  | SQLAlchemy-URL. Default Postgres i Docker, SQLite ved lokal kørsel uden den.        |
| `SECRET_KEY`                                    | JWT-signing nøgle. Min. 32 tegn i prod.                                             |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` / `ADMIN_NAME` | Bruges til at seede første admin-bruger.                                            |
| `PUBLIC_BASE_URL`                               | Base-URL der bruges i invitations-emails.                                           |
| `COOKIE_SECURE` / `COOKIE_SAMESITE`             | Cookie-flags (sæt `COOKIE_SECURE=true` i prod).                                     |
| `CORS_ORIGINS`                                  | JSON-liste af tilladte origins.                                                     |
| `SMTP_HOST` (+ port, user, pw, tls)             | Sættes hvis emails skal sendes rigtigt. Hvis tom skrives kun til outbox + stdout.   |

## Produktion

`docker-compose.prod.yml` starter Postgres, backend, frontend og en Caddy reverse-proxy med automatisk Let's Encrypt:

```bash
cp .env.example .env
$EDITOR .env                  # sæt rigtige domæner, secrets, admin password, SMTP
$EDITOR Caddyfile             # ændr karkov.example.com til dit domæne
docker compose -f docker-compose.prod.yml up -d --build
```

## Ikke med endnu (deferred)

- Rigtig password-reset-email (siden findes, men afsendelse er stub).
- Web-push notifikationer (interface er klar, mangler VAPID + service worker).
- Live updates over WebSockets (i dag: TanStack Query polling).
- Upload-UI for familie/barn profilbilleder (backend understøtter det).
- Maps med rigtig API-nøgle (i dag: keyless iframe).

---

## English

Karkov Weekend is a closed-group Danish family weekend planner: invite-only login, families, kids, multi-day events with auto-generated chores, activities, a fair shared budget with minimum cross-family settlement, a global chat room with system notifications, optional email + (future) push, and a summerhouse-page scraper.

The full product spec lives in [`prompt.md`](./prompt.md).

### Quick start

```bash
cp .env.example .env
docker compose up --build
```

Then open <http://localhost:3000> and sign in with the seeded admin (`ADMIN_EMAIL` / `ADMIN_PASSWORD` from `.env`).

### Architecture

- `backend/` — FastAPI + SQLAlchemy 2 + Alembic. Pure-Python pricing/balance services with heavy unit tests (`tests/services/test_balance.py`, `test_pricing.py`). Notifications and email delivery are isolated behind small services (`services/notifications.py`, `services/email.py`).
- `frontend/` — Next.js 16 App Router with TypeScript, Tailwind v4 and shadcn/ui. Server cookies + JWT, TanStack Query for fetching, framer-motion for animations.
- `docker-compose.yml` — local stack (Postgres, backend, frontend behind a profile, Adminer).
- `docker-compose.prod.yml` + `Caddyfile` — production stack with auto-HTTPS via Caddy.

### Running tests

```bash
# Backend
cd backend && uv run pytest -q

# Frontend unit tests
cd frontend && npm test

# Playwright happy-path against a running stack
cd frontend && npm run test:e2e
```

### Deferred

Real password-reset emails, web-push notifications, real-time websocket updates, family/child picture upload UI, and Maps API key integration are deliberately deferred and clearly stubbed behind interfaces (`EmailSender`, the notification queue, etc).

---

## Repo layout

```text
.
├── backend/                 # FastAPI app
│   ├── app/
│   │   ├── api/v1/          # routers (auth, families, events, expenses, chors, activities, chat, admin, ...)
│   │   ├── core/            # config, db, security, deps
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── schemas/         # Pydantic models
│   │   ├── services/        # pricing, balance, events_factory, email, notifications, scrape, uploads
│   │   └── seeds.py
│   ├── tests/               # pytest (api + services)
│   └── alembic/
├── frontend/                # Next.js 16 app
│   ├── src/app/             # routes (auth + app shell, /chat, /arrangementer/[id], …)
│   ├── src/components/      # UI + shadcn primitives + app-shell
│   ├── src/lib/             # api client, auth, types, format, age, utils
│   ├── src/i18n/da.ts       # all Danish copy
│   └── e2e/                 # Playwright smoke
├── docker-compose.yml       # dev stack
├── docker-compose.prod.yml  # prod stack
├── Caddyfile
├── prompt.md                # full product spec
└── .env.example
```
