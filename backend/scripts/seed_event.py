"""Realistic, randomised simulator for a Karkov event.

Seeds attendance, chor assignments, activities (with attendees), and a mix of
chor-/activity-linked plus stand-alone expenses for one event. Each run
produces somewhat different data; pass `SEED=<int>` to make a run
reproducible.

Usage (run from the repository root so we can read `.env` for the admin
credentials):

    EVENT_ID=7 python3 backend/scripts/seed_event.py            # random
    EVENT_ID=7 SEED=42 python3 backend/scripts/seed_event.py    # reproducible

Override the API base or the env-file location with environment variables:

    API_BASE=http://localhost:8000/api/v1 \\
    ENV_FILE=.env \\
    EVENT_ID=3 python3 backend/scripts/seed_event.py

Idempotency notes:
- Attendance is additive (the API upserts `present=true`).
- Chors that are already assigned are left alone; only unassigned ones are
  filled in. So re-running fills more chors but never reassigns.
- Activities are always created (re-runs add more activities). To start
  fresh, delete activities/expenses manually in the UI first.
- Expenses are always created (each run adds more lines).
"""

from __future__ import annotations

import http.cookiejar
import json
import os
import random
import urllib.error
import urllib.request
from datetime import time as Time
from pathlib import Path

API = os.environ.get("API_BASE", "http://localhost:8000/api/v1")
EVENT_ID = int(os.environ.get("EVENT_ID", "3"))
ENV_FILE = Path(os.environ.get("ENV_FILE", ".env"))
SEED_ENV = os.environ.get("SEED")
SEED = int(SEED_ENV) if SEED_ENV is not None else random.randrange(1 << 30)
RNG = random.Random(SEED)


def env(name: str) -> str:
    if not ENV_FILE.exists():
        raise SystemExit(
            f"env file '{ENV_FILE}' not found — run from the repo root or set "
            "ENV_FILE=/abs/path/to/.env"
        )
    for line in ENV_FILE.read_text().splitlines():
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1]
    raise SystemExit(f"missing {name} in {ENV_FILE}")


# ---- HTTP plumbing --------------------------------------------------------

JAR = http.cookiejar.CookieJar()
OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(JAR))


def request(method: str, path: str, body: dict | None = None):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(API + path, data=data, method=method, headers=headers)
    try:
        with OPENER.open(req) as r:
            code = r.getcode()
            text = r.read().decode()
    except urllib.error.HTTPError as e:
        text = e.read().decode()
        return e.code, json.loads(text) if text else None
    return code, (json.loads(text) if text else None)


def must(code_payload, *expected):
    code, payload = code_payload
    if expected and code not in expected:
        raise SystemExit(f"unexpected {code}: {payload}")
    if not expected and code >= 400:
        raise SystemExit(f"unexpected {code}: {payload}")
    return payload


# ---- Login as admin -------------------------------------------------------

print(f"Seed: {SEED}  (set SEED={SEED} to reproduce)")
must(
    request(
        "POST",
        "/auth/login",
        {"email": env("ADMIN_EMAIL"), "password": env("ADMIN_PASSWORD")},
    ),
    200,
)


# ---- Fetch context --------------------------------------------------------

event = must(request("GET", f"/events/{EVENT_ID}"))
families = must(request("GET", "/families"))
categories = {c["name"]: c["id"] for c in must(request("GET", "/expense-categories"))}

print(f"Event: {event['name']} ({event['start_date']}–{event['end_date']})")
print(f"Families: {len(families)}  Days: {len(event['days'])}")

day_ids: list[int] = [d["id"] for d in event["days"]]
days_by_id = {d["id"]: d for d in event["days"]}
fams_by_name: dict[str, dict] = {f["name"]: f for f in families}

ADMIN_FAMILY_NAMES = {"Test"}
KNOWN_FAMILY_NAMES = [
    f["name"] for f in families if f["name"] not in ADMIN_FAMILY_NAMES
]


def family_member_ids(family_name: str) -> list[int]:
    fam = fams_by_name.get(family_name)
    return [m["id"] for m in fam["members"]] if fam else []


def family_parents(family_name: str) -> list[dict]:
    fam = fams_by_name.get(family_name)
    if not fam:
        return []
    return [m for m in fam["members"] if m.get("role") in ("parent", "admin")]


def family_for_user(user_id: int) -> str | None:
    for f in families:
        for m in f["members"]:
            if m["id"] == user_id:
                return f["name"]
    return None


# ---- Phase A: attendance --------------------------------------------------

# For each known family, decide which subset of days they attend. Bias: most
# families attend the full event, some join late, some leave early, some skip
# entirely.
def random_day_window(all_days: list[int]) -> list[int] | None:
    n = len(all_days)
    roll = RNG.random()
    if roll < 0.55:
        return list(all_days)                                 # full
    if roll < 0.75:
        return list(all_days[max(0, n - 2):])                 # last 2
    if roll < 0.88:
        return list(all_days[1:])                             # all but first
    if roll < 0.96:
        return list(all_days[: max(1, n - 1)])                # all but last
    return None                                                # skip


UNLOCKED_STATUSES = {"planlagt", "aabent"}
print("\nPhase A: attendance")
if event["status"] not in UNLOCKED_STATUSES:
    print(
        f"  ! event status is '{event['status']}' – attendance is locked, "
        "skipping Phase A and using whatever attendance is already on file."
    )
else:
    for fname in KNOWN_FAMILY_NAMES:
        days = random_day_window(day_ids)
        if not days:
            print(f"  -- {fname}: not attending")
            continue
        member_ids = family_member_ids(fname)
        if not member_ids:
            continue
        payload = {"day_ids": days, "present": True, "user_ids": member_ids}
        must(request("POST", f"/events/{EVENT_ID}/attendance", payload))
        print(f"  + {fname:<20} {len(member_ids)} members  on {len(days)} day(s)")


# Re-fetch event so attendance reflects either Phase A or the pre-existing data.
event = must(request("GET", f"/events/{EVENT_ID}"))
days_by_id = {d["id"]: d for d in event["days"]}
attending_by_day: dict[int, list[int]] = {
    d["id"]: list(d["attendee_user_ids"]) for d in event["days"]
}
attending_user_ids: set[int] = {
    uid for ids in attending_by_day.values() for uid in ids
}


# ---- Phase B: chor assignments -------------------------------------------

ATTEND_RATIO = 0.78  # fraction of chors that get assigned

print(f"\nPhase B: chor assignments  (target ~{int(ATTEND_RATIO * 100)}% of slots)")
assigned_chors: list[dict] = []  # {chor_id, user_id, day_id, meal, action}

for d in event["days"]:
    parents_today = [
        m
        for fname in KNOWN_FAMILY_NAMES
        if any(uid in attending_by_day[d["id"]] for uid in family_member_ids(fname))
        for m in family_parents(fname)
        if m["id"] in attending_by_day[d["id"]]
    ]
    if not parents_today:
        continue
    for c in d["chors"]:
        if c["assignee_user_id"] is not None:
            continue
        if RNG.random() > ATTEND_RATIO:
            continue
        # bias: prefer parents who haven't taken many chors yet
        load = {p["id"]: 0 for p in parents_today}
        for r in assigned_chors:
            if r["user_id"] in load:
                load[r["user_id"]] += 1
        min_load = min(load.values())
        candidates = [p for p in parents_today if load[p["id"]] == min_load]
        choice = RNG.choice(candidates)
        result = must(
            request("POST", f"/chors/{c['id']}/assign", {"user_id": choice["id"]}),
            200,
        )
        assigned_chors.append(
            {
                "chor_id": c["id"],
                "user_id": choice["id"],
                "day_id": d["id"],
                "day_date": d["date"],
                "meal": c["meal"],
                "action": c["action"],
            }
        )
print(f"  assigned {len(assigned_chors)} chors")


# ---- Phase C: activities --------------------------------------------------

ACTIVITY_TEMPLATES: list[tuple[str, str | None, Time | None, str | None]] = [
    # name, description, time, payment hint ("entry"|"materials"|None)
    ("Krocketturnering", "Hold à 2, vinder får hjemmebagt kage", Time(14, 0), "materials"),
    ("Strandtur", "Til vandet med drager og strandbold", Time(11, 0), None),
    ("Bål og snobrød", "Møder ved bålpladsen kl. 18.30", Time(18, 30), "materials"),
    ("Brætspilsaften", "Catan, Codenames, Wingspan", Time(20, 0), None),
    ("Quiz", "Familiequiz – 5 hold", Time(20, 30), "materials"),
    ("Morgengymnastik", "På terrassen før morgenmad", Time(8, 0), None),
    ("Kanotur", "Forventer 2 timer på vandet", Time(13, 0), "entry"),
    ("Vinsmagning", "Voksne (BYO eller fælles indkøb)", Time(21, 0), "materials"),
    ("Filmaften for børnene", "Med popcorn", Time(19, 0), "materials"),
    ("Skattejagt", "For børnene – ruten klar kl. 10", Time(10, 0), "materials"),
    ("Fælles løbetur", "5 km – let tempo", Time(7, 30), None),
    ("Fugletur", "Tag kikkert med", Time(9, 0), None),
    ("Bagedyst", "Børn vs. voksne", Time(15, 30), "materials"),
    ("Træsløjd", "Snitteknive medbringes", Time(14, 30), "materials"),
]


def candidate_attendees_for_day(day_id: int, n_min: int, n_max: int) -> list[int]:
    pool = list(set(attending_by_day.get(day_id, [])))
    if not pool:
        return []
    n = RNG.randint(min(n_min, len(pool)), min(n_max, len(pool)))
    return RNG.sample(pool, n)


print("\nPhase C: activities")
created_activities: list[dict] = []
n_activities = RNG.randint(6, min(12, len(day_ids) * 3))

# Pick day-distribution so activities spread over days
day_pool = list(day_ids)
RNG.shuffle(day_pool)
day_cycle = (day_pool * ((n_activities // max(1, len(day_pool))) + 1))[:n_activities]

# Avoid duplicate (day, name) within this run
used: set[tuple[int, str]] = set()
templates_left = ACTIVITY_TEMPLATES[:]
RNG.shuffle(templates_left)

for did in day_cycle:
    if not templates_left:
        break
    template = None
    for t in templates_left:
        if (did, t[0]) not in used:
            template = t
            break
    if template is None:
        continue
    used.add((did, template[0]))
    templates_left.remove(template)

    name, desc, when, pay_hint = template
    body = {"name": name, "description": desc}
    if when is not None:
        body["time"] = when.strftime("%H:%M:%S")
    activity = must(
        request("POST", f"/events/{EVENT_ID}/days/{did}/activities", body),
        201,
    )

    attendees = candidate_attendees_for_day(did, n_min=3, n_max=12)
    if attendees:
        must(
            request(
                "POST",
                f"/activities/{activity['id']}/attendees",
                {"user_ids": attendees},
            ),
            200,
        )
    created_activities.append(
        {
            "activity_id": activity["id"],
            "name": name,
            "day_id": did,
            "day_date": days_by_id[did]["date"],
            "attendees": attendees,
            "pay_hint": pay_hint,
        }
    )
    print(f"  + {days_by_id[did]['date']}  {name:<24} ({len(attendees)} deltagere)")


# ---- Phase D: expenses ----------------------------------------------------

print("\nPhase D: expenses")


def post_expense(
    *,
    payer_id: int,
    category_name: str,
    amount_kr: int,
    description: str,
    chor_id: int | None = None,
) -> None:
    cat_id = categories.get(category_name)
    if cat_id is None:
        print(f"  ! missing category {category_name}; skipping {description}")
        return
    body: dict = {
        "category_id": cat_id,
        "amount_cents": amount_kr * 100,
        "description": description,
    }
    if chor_id is not None:
        body["chor_id"] = chor_id
    created = must(request("POST", f"/events/{EVENT_ID}/expenses", body), 201)
    must(
        request(
            "PATCH",
            f"/expenses/{created['id']}",
            {"paid_by_user_id": payer_id},
        ),
        200,
    )
    tag = f" [chor {chor_id}]" if chor_id else ""
    print(f"  +{amount_kr:>5} kr  {category_name:<11} <- user {payer_id:<3} {description}{tag}")


# D1: chor-linked groceries (most "forberedelse" chors get groceries from the
# assignee).
MEAL_PRICE_KR = {
    "morgenmad": (180, 480),
    "frokost": (260, 620),
    "aftensmad": (450, 1100),
}
MEAL_DESC = {
    "morgenmad": ["Brød + smør + ost", "Yoghurt og müsli", "Æg, bacon, juice"],
    "frokost": ["Frokostbuffet", "Smørrebrød", "Sandwich og frugt"],
    "aftensmad": [
        "Lasagne og salat",
        "Tacos",
        "Lam med rodfrugter",
        "Pasta carbonara",
        "Kylling med ovnkartofler",
    ],
}

n_chor_expenses = 0
for ch in assigned_chors:
    if ch["action"] != "forberedelse":
        continue
    if RNG.random() > 0.65:
        continue
    lo, hi = MEAL_PRICE_KR[ch["meal"]]
    amount = RNG.randint(lo, hi)
    desc = f"{ch['day_date']} {ch['meal']}: {RNG.choice(MEAL_DESC[ch['meal']])}"
    post_expense(
        payer_id=ch["user_id"],
        category_name="Mad",
        amount_kr=amount,
        description=desc,
        chor_id=ch["chor_id"],
    )
    n_chor_expenses += 1


# Only parents/admins can pay. Children may attend activities but can't be set
# as payer (the API rejects them).
adult_ids: set[int] = set()
for fname in KNOWN_FAMILY_NAMES:
    for p in family_parents(fname):
        adult_ids.add(p["id"])


# D2: activity-linked expenses (entry fees / materials), for some activities.
n_activity_expenses = 0
for act in created_activities:
    if act["pay_hint"] is None:
        continue
    if RNG.random() > 0.55:
        continue
    parent_attendees = [uid for uid in act["attendees"] if uid in adult_ids]
    if not parent_attendees:
        continue
    payer = RNG.choice(parent_attendees)
    if act["pay_hint"] == "entry":
        amount = RNG.randint(60, 180) * len(act["attendees"])
        desc = f"{act['name']} – entré ({len(act['attendees'])} pers.)"
    else:
        amount = RNG.randint(120, 700)
        desc = f"{act['name']} – materialer"
    post_expense(
        payer_id=payer,
        category_name="Aktiviteter",
        amount_kr=amount,
        description=desc,
    )
    n_activity_expenses += 1


# D3: stand-alone expenses (rental, utilities, cleaning, drinks, ...).
def random_attending_parent_id() -> int | None:
    parent_pool: list[int] = []
    for fname in KNOWN_FAMILY_NAMES:
        for p in family_parents(fname):
            if p["id"] in attending_user_ids:
                parent_pool.append(p["id"])
    return RNG.choice(parent_pool) if parent_pool else None


STANDALONE_TEMPLATES: list[tuple[str, int, int, str]] = [
    # category, kr_lo, kr_hi, description
    ("Udlejning", 18000, 24000, "Sommerhusleje"),
    ("Forbrug", 900, 1800, "El + vand depositum"),
    ("Forbrug", 180, 360, "Brænde og optænding"),
    ("Mad", 320, 720, "Vin og øl"),
    ("Mad", 220, 480, "Snacks og frugt"),
    ("Mad", 180, 360, "Kaffe og te"),
    ("Aktiviteter", 150, 320, "Brætspil indkøb"),
    ("Aktiviteter", 80, 240, "Strandbold + drage"),
    ("Andet", 120, 320, "Plaster + paracetamol"),
    ("Andet", 200, 420, "Slutrengøring tillæg"),
    ("Andet", 90, 220, "Affaldsposer + køkkenruller"),
]

n_standalone = RNG.randint(5, 9)
RNG.shuffle(STANDALONE_TEMPLATES)
n_made = 0
for tmpl in STANDALONE_TEMPLATES:
    if n_made >= n_standalone:
        break
    cat_name, kr_lo, kr_hi, desc = tmpl
    payer = random_attending_parent_id()
    if payer is None:
        continue
    amount = RNG.randint(kr_lo, kr_hi)
    post_expense(
        payer_id=payer,
        category_name=cat_name,
        amount_kr=amount,
        description=desc,
    )
    n_made += 1


# ---- Summary --------------------------------------------------------------

ev2 = must(request("GET", f"/events/{EVENT_ID}"))
total_attendees = sum(len(d["attendee_user_ids"]) for d in ev2["days"])
print(f"\nDone (seed={SEED}). Attendance person-days: {total_attendees}")
for d in ev2["days"]:
    n_chors_assigned = sum(1 for c in d["chors"] if c["assignee_user_id"] is not None)
    print(
        f"  {d['date']}: {len(d['attendee_user_ids']):>2} present, "
        f"bed_demand={d['bed_demand']:>2}, chors {n_chors_assigned}/{len(d['chors'])}, "
        f"activities {len(d['activities'])}"
    )

budget = must(request("GET", f"/events/{EVENT_ID}/budget"))
print(
    f"\nBudget total: {budget['total_cents'] / 100:.0f} kr "
    f"({len(budget['shares'])} brugere, {len(budget['settlements'])} betalinger)"
)
print(
    f"Phase totals: chor-linked expenses {n_chor_expenses}, "
    f"activity-linked {n_activity_expenses}, stand-alone {n_made}"
)
