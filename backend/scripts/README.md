# Backend scripts

One-off and developer helpers. They run against a live backend and are not
part of the test suite — keep them small and self-contained (stdlib only) so
they can be run without `uv sync`.

## `seed_event.py`

Realistic, randomised simulator for a single Karkov event. Logs in as the
admin (credentials read from `.env`), then for the chosen event:

1. **Attendance** — every known family rolls a window of days they attend
   (full event, last two days, all-but-first, all-but-last, or skip).
2. **Chors** — fills unassigned chors with attending parents, biased
   towards parents who have taken the fewest chors so far.
3. **Activities** — creates 6–12 activities spread across the days using a
   curated template list, then signs up a random subset of attendees.
4. **Expenses** — produces three flavours: chor-linked groceries (linked to
   the relevant prep chor), activity-linked entry/material fees, and a
   handful of stand-alone expenses (rental, utilities, drinks, cleaning).

The script is idempotent for attendance and chor assignments (it never
reassigns an already-taken chor) but additive for activities and expenses,
so each re-run grows the dataset.

### Usage

Run from the repository root so the script can read `.env`:

```bash
EVENT_ID=7 python3 backend/scripts/seed_event.py            # random
EVENT_ID=7 SEED=42 python3 backend/scripts/seed_event.py    # reproducible
```

Optional overrides:

| Variable    | Default                                | Notes                                |
| ----------- | -------------------------------------- | ------------------------------------ |
| `API_BASE`  | `http://localhost:8000/api/v1`         | Point at a remote backend if needed. |
| `ENV_FILE`  | `.env`                                 | Absolute path also accepted.         |
| `EVENT_ID`  | `3`                                    | Must be an existing event.           |
| `SEED`      | random per run                         | Reuse for reproducible output.       |

The script prints the seed it used so failed runs can be replayed
deterministically.
