# Karkov Weekend — Product Spec

A community planner for a small group of Danish families that go on a weekend
trip together once a year. Solves the classic "who goes when, who cooks what,
who paid what, who owes whom" problem with a fair, transparent, low-friction
tool.

---

## 1. Vision & principles

- Built from SOLID principles, modern best practices and TDD.
- Easy to maintain and extend — features live behind small services, not
  god-classes.
- Tested locally and end-to-end before each milestone.
- Mobile-first, light/dark mode (auto-detected from the browser), smooth
  animations, premium UX, "liquid glass" feel.
- Optimized for mobile, tablet and desktop.
- Danish UI throughout — `frontend/src/i18n/da.ts` is the single source of all
  user-facing copy.
- Repo on GitHub.

## 2. Tech stack

| Layer    | Choice                                                                                                |
| -------- | ----------------------------------------------------------------------------------------------------- |
| Backend  | Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic (+ dev schema helper) · Pydantic v2 · pytest           |
| DB       | PostgreSQL 16 (SQLite for unit tests)                                                                 |
| Auth     | Self-hosted JWT in httpOnly cookies (access 7d, refresh 30d), bcrypt                                  |
| Frontend | Next.js 16 (App Router) · TypeScript · Tailwind v4 · shadcn/ui · TanStack Query · Vitest · Playwright |
| Email    | DB outbox (always on) + optional SMTP (configurable via env)                                          |
| Scrape   | httpx + BeautifulSoup, cached on the event                                                            |
| Deploy   | Docker Compose (dev) · Docker Compose + Caddy reverse-proxy (prod)                                    |

## 3. Roles & access

- **Admin** — full control. Creates families, invites parents, can promote a
  parent to admin or demote (cannot demote the last admin), creates and edits
  events, manages global pricing rules, manages expense categories, can change
  who paid an expense.
- **Parent** — standard adult user. Belongs to one family.
- **Child** — optional login. Can sign in and toggle attendance / chors /
  activities, but cannot see or edit the budget.

## 4. Identity

### 4.1 Families

- Admin creates family units with a name and optional profile picture.
- A user belongs to exactly one family.
- Admin can build a complete family unit (parents + children) without sending
  invitations; a separate "Send invitationer" button fires the emails when the
  setup is ready.
- Pending invitations are listed per family, can be cancelled, or resent in
  bulk.
- Admin can edit family name, parent, and child profiles.
- Admin can delete a family / user / child (with confirmation).
- Admin can promote a parent to admin and demote back, except the very last
  admin.

### 4.2 Users

- Email/password login over JWT cookies (access + refresh tokens).
- Invite-based registration: parent receives an email link with a one-time
  token, sets name + password.
- Profile page: name, email, profile picture, birthdate.
- Users can edit their own profile and change their password.
- Users can opt-in/out of email notifications and are prompted on first login
  by a one-shot modal; the choice is editable later from their profile.

### 4.3 Children (kids)

- Added by their parent or by an admin.
- Optionally given an email + password so they can log in.
- A parent can manage all data on their kids (name, birthdate, password,
  email, picture).
- Children "share" between parents inside the same family unit (a family has
  one or more parents and their children).

### 4.4 Age brackets (admin-tunable on the settings page)

- **Baby** — 0 to N₁ years (default 0–2). Don't count for beds and don't pay.
- **Kid** — N₁+1 to N₂ years (default 3–13). Half price on bed/food/per-night
  categories. The summerhouse needs a bed for each kid.
- **Teen / adult** — N₂+1 and up (default 14+). Full price.
- The bracket is computed from the user's birthdate at the event start date
  and shown as a Baby / Barn / Teenager / Voksen badge throughout the app
  (family page, attendees strip, etc).

## 5. Events

- One main event per year, but the data model handles many.
- Admin creates an event with name, description, optional address, optional
  Google-Maps URL, optional summerhouse URL, date range, optional bed count
  and optional host.
- An event can be created without a summerhouse — adding a summerhouse URL
  later is a notifiable event posted to the global chat.
- Status flow: `planlagt` → `aabent` (open for sign-ups) → `låst` (attendance
  locked) → `afsluttet` (budget closed). Host or admin moves it forward.
- The host or admin can edit any event detail inline from a dialog on the
  event detail page (name, dates, address, links, beds, host).
- The home page shows the next upcoming event with a quick-action; if there
  is none, admins see "Opret arrangement" and others see "Alle arrangementer".
- An events list page shows all events with status badges and a brief summary.
- A "Plan næste år" admin button creates next year's event pre-filled with
  date+1y, same length, same host, copied address & URLs (leap-year safe).

### 5.1 Event detail header

- Title, date range, address (truncated), host with crown icon.
- "Ledige opgaver: N" line — clickable, jumps to the Chors tab. Shows
  "Alle opgaver er taget" when empty.
- Mini Google-Maps thumbnail (clickable — opens the full map in a new tab).
- Status badge, host/admin actions (open / lock / finalize), Edit dialog,
  Plan-next-year button.
- Attendees strip grouped by family with avatar pills and a "X/Y dage" badge
  when attendance is partial.
- Tabs: Days, Chors, Activities, Budget (Budget hidden for children).

### 5.2 Days & attendance

- An event auto-builds one EventDay per day in the date range.
- Editing the date range adds/removes days and rebuilds chors as needed.
- Each parent toggles attendance per day (or in bulk for many days).
- Their children follow them automatically when added.
- A bed-demand widget shows peak occupancy across the days vs the event's
  bed count, with a green/amber/red bar (babies excluded). The faster the
  users sign up, the faster the host can find a place that fits everyone.

### 5.3 Chors (opgaver)

- A fixed grid of 6 chors per day:
  `(morgenmad, frokost, aftensmad) × (forberedelse, oprydning)`.
- Auto-created when an event is created (or when a day is added by extending
  the date range). Admins can extend the catalog.
- Anyone can claim or release a chor for themselves; parents can claim for
  their children.
- Unassigned chors are surfaced clearly: counted in the event header (jumps
  to the Chors tab) and listed at the top of the Chors tab.
- The host or admin can reassign any chor.

### 5.4 Activities

- Per-day list created by users.
- Anyone can create, edit, or sign themselves and their children up to an
  activity.
- An activity has a name, optional description, optional start time, and a
  list of attendees.

## 6. Budget

### 6.1 Categories

- Default categories: rental ("Udlejning"), utilities ("Forbrug"), food
  ("Mad"), activities ("Aktiviteter"), other ("Andet").
- Admins can add, rename, delete (only if unused) and toggle three flags per
  category from `/indstillinger`:
  - `is_per_person` — split per attendee, not per family.
  - `is_per_night` — multiplied by attended days.
  - `is_utility` — must be registered after the event (e.g. heating, water).
- Forbrug is seeded with `is_utility = true`.

### 6.2 Expenses

- An expense has: amount, category, optional description, optional link to a
  chor (e.g. "groceries for Saturday lunch") and a payer.
- The current user is the default payer when creating; admins can change the
  payer of any expense afterwards (children cannot be set as a payer).
- Anyone (except children) can add expenses while the event is open. Once
  finalized, only admins can edit, as a controlled escape hatch.

### 6.3 Budget tab

- **Total** with the user's own family share, paid amount and net.
- **Foreløbigt regnskab** — per-family running totals (paid, share, net)
  updated live, even before the event is closed.
- **Settlements** — minimum-overflow transfers between families (greedy
  two-pointer), shown by family name not by ID.
- **Expenses list** — grouped row with category, optional chor badge, "Betalt
  af X", inline edit (rename, change category/amount/chor, change payer for
  admins).
- A warning banner shows when there are utility categories with no expenses
  yet.
- The "Endeligt afsluttet" button opens a confirmation dialog whose copy
  escalates if utilities are still missing.
- Children cannot view the Budget tab.

### 6.4 Splitting & fairness

- Per-category total is distributed in proportion to each user's "units":
  - units = `weight × (attendance_days if is_per_night else 1 if attended else 0)`
  - weight = 0 (baby) / 0.5 (kid) / 1.0 (teen+adult)
- The last cent is balanced via the largest-remainder method so totals are
  exact.
- Family net = Σ user net within the family.
- Settlements are minimised via a greedy two-pointer pairing of biggest
  creditor and biggest debtor — each transfer is shown ("Familie A betaler
  X kr til Familie B") so the math is transparent and fair.
- Rental (per-family) and food (per-person, per-night) split differently by
  default; admins can rebalance via the category flags.

### 6.5 Finalization

- Host or admin clicks "Endeligt afsluttet" → confirm → status `afsluttet`,
  budget locked.
- A summary email is sent to all opted-in adults with totals and payment
  instructions.
- After lock, only admins can edit expenses.

## 7. Notifications & chat

- A single global chat room visible to all logged-in users (children
  included).
- The Chat tab in the app shell shows messages with daily date separators
  and auto-scroll.
- **Live updates** are delivered over Server-Sent Events
  (`GET /api/v1/chat/stream`). The client opens an `EventSource` after the
  initial fetch; new messages stream in within seconds. A 30-second safety
  poll covers SSE outages.
- A user can post chat messages; chat-only messages are NOT a notifiable
  event.
- The following actions DO post a system message in the chat (with an icon
  and a link to the related event) AND fan out to opted-in adults excluding
  the actor over **email** + **web push**:
  - Event created
  - Summerhouse URL added to an event that didn't have one
  - Attendance changed
  - Activity created or joined
  - Chor assigned
  - Event finalized
- **Email delivery** — always written to the DB outbox + stdout. If
  `SMTP_HOST` is set, also attempted via SMTP. Failures don't break the
  underlying user action (`@_safe` decorator on every notification call).
- **Password reset** — `POST /auth/forgot-password` always returns 204 (to
  avoid email enumeration). When the address matches a real user a token is
  generated and emailed via the same pipeline; the user follows
  `/nulstil-adgangskode?token=…` to set a new password.
- **Web push** — opt-in per device on the profile page. The service worker
  at `/service-worker.js` displays the notification and routes clicks to the
  related event. Backed by VAPID keys; the backend auto-generates an
  ephemeral keypair if `VAPID_PRIVATE_KEY` / `VAPID_PUBLIC_KEY` are unset
  (development only — production must set them so subscriptions survive
  restarts).
- A user can opt in/out of notifications (email + push share the same
  toggle). On first login they get a one-shot modal asking. They can change
  it later under their profile.

## 8. Summerhouse scrape

- The host can paste a summerhouse URL on the event.
- Hosts/admins can hit "Refresh" to fetch the page; the scraper extracts
  title, summary (Open Graph first, then `<h1>` + first long `<p>`, with
  generic-blurb skipping for known commercial sites) and a hero image.
- Result is cached on the event (`summerhouse_title`, `summerhouse_summary`,
  `summerhouse_image_url`, `summerhouse_scraped_at`).
- The Summerhouse hero card on the event page renders the image, title,
  summary and a link out.

## 9. Maps

- When `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` is set, the app uses the official
  Google **Maps Embed API** (`/maps/embed/v1/place?key=...`) — no
  "for development purposes only" watermark and a richer pin.
- Without a key the app falls back to the keyless `?q=…&output=embed` form,
  which works for casual use but is technically unsupported by Google.
- The mini-map tile in the event header is click-through: it opens
  `event.location_url` if set, otherwise a Google Maps search of the address.
- Mobile is the priority: it must be one tap from the event to "open in
  Maps".

## 10. Pages

- `/login` — email + password.
- `/register?token=…` — invite landing (sets name + password).
- `/glemt-adgangskode` — forgot-password landing.
- `/nulstil-adgangskode?token=…` — set-new-password landing.
- `/` — home with next-event hero and quick-action.
- `/arrangementer` — list of all events (each card uses the event's group
  photo as a hero when set).
- `/arrangementer/[id]` — event detail (header + tabs: Dage, Opgaver,
  Aktiviteter, Billeder, Budget).
- `/galleri` — cross-event photo history with sections per event and a
  full-screen "Dias-visning" autoplay carousel.
- `/familie` — your family unit (with age-category badges on children).
- `/chat` — global chat room.
- `/profil` — your profile, password change, notification preference.
- `/indstillinger` — admin only: pricing rules, expense categories CRUD,
  families list (create / edit / invite / promote / delete).

## 11. Deployment

- **Dev** — `docker compose up --build` brings up Postgres, backend, Adminer,
  and optionally the frontend container (otherwise run `npm run dev` from
  `frontend/` on the host).
- **Prod** — `docker compose -f docker-compose.prod.yml up -d --build` adds
  Caddy with auto-HTTPS via Let's Encrypt.
- All secrets via `.env` — never commit real values.

## 12. Future / nice-to-have

- Bulk import of past events / photos (drop a folder of photos into an
  event, parse EXIF for date placement, optional manifest YAML for captions
  and group-photo selection).
- Backup / restore of the database.
- Group photo event automatically created on the date most users are
  attending.
- Chors generated from a list of possible chors. Adjustment: first day only
  has dinner, last day only has breakfast.
- Ability to join as an assistant for a chor. When a user picks a chor they
  can specify how many assistants they need.

### Recently shipped (was on this list)

- Event photo upload UI — drop a batch of photos into the "Billeder" tab on
  any event. Pillow validates the bytes, normalizes EXIF orientation,
  downsizes anything above 2560px on the long edge to keep transfers sane,
  and extracts `DateTimeOriginal` for chronological gallery sort.
- Per-event photo gallery with lightbox + keyboard nav (←/→/Esc) under the
  "Billeder" tab. Uploader / host / admin can edit captions, mark the group
  photo, and delete.
- Group photo: one photo per event can be flagged via the edit dialog.
  Surfaced as the hero on event cards (`/arrangementer`) and the
  `group_photo_url` field on `EventOut`. Flipping the flag automatically
  unsets the previous group photo for that event.
- History gallery at `/galleri` with chronological sections per event and a
  full-screen "Dias-visning" carousel that auto-advances every 4s
  (Space toggles play/pause; ←/→/Esc work as expected).
- Per-family "Send opsætningslinks" button — issues a fresh 24h
  password-reset token for every parent in the family who hasn't activated
  yet (covers YAML-imported families that never had invite tokens). Pending
  invite tokens are resent in the same call.
- Admin can edit any user's name/email/birthdate/password via the pencil
  icon on each parent row, and send an individual password-reset link via
  the key icon.
- Real password-reset emails — fully wired end-to-end. Set `SMTP_HOST` and
  friends in `.env` to deliver real mail; otherwise the dev outbox writes
  rows to `email_outbox` so you can copy the link out manually.
- Web-push notifications via VAPID + service worker — opt in per device on
  the profile page. Falls back to email when push is unavailable.
- Live chat updates over Server-Sent Events (`GET /api/v1/chat/stream`).
  Replaces the 5-second polling; falls back to a 30-second safety poll if
  the browser cannot keep an EventSource open.
- Family + child profile-picture upload UI on the profile page.
- Maps Embed API key support — set `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` and the
  app uses the official Embed API; without a key it falls back to the
  keyless `?q=…&output=embed` form.
