from datetime import date

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import func as sa_func

from app.core.deps import CurrentUser, DbDep, require_not_child
from app.models.attendance import Attendance
from app.models.chor import Chor
from app.models.event import Event, EventDay, EventStatus
from app.models.event_photo import EventPhoto
from app.models.pricing_rules import PricingRules
from app.models.user import User, UserRole
from app.schemas.attendance import AttendanceToggle, BulkAttendance
from app.schemas.event import (
    ActivityOut,
    AttendeeSummary,
    BedDemand,
    ChorOut,
    EventCreate,
    EventDayOut,
    EventOut,
    EventPhotoOut,
    EventPhotoUpdate,
    EventUpdate,
    GalleryPhotoOut,
)
from app.models.family import Family
from app.core.security import now_utc
from app.services.budget import compute_event_budget, is_budget_locked
from app.services.email import get_email_sender
from app.services.events_factory import build_event_days_and_chors
from app.services.notifications import (
    notify_attendance_changed,
    notify_event_created,
    notify_event_finalized,
    notify_summerhouse_added,
)
from app.services.pricing import AgeBracket, classify
from app.services.scrape import fetch_summerhouse
from app.services.uploads import save_event_photo

router = APIRouter(prefix="/events", tags=["events"])


def _to_out(db, event: Event) -> EventOut:
    pr = db.get(PricingRules, 1)
    baby_max = pr.baby_max_age if pr else 2
    kid_max = pr.kid_max_age if pr else 13

    # Pre-load all attendee users in one query so per-day classification is cheap.
    all_attendee_rows = (
        db.query(Attendance.event_day_id, Attendance.user_id)
        .join(EventDay, Attendance.event_day_id == EventDay.id)
        .filter(EventDay.event_id == event.id)
        .all()
    )
    user_ids = {uid for (_, uid) in all_attendee_rows}
    users_by_id: dict[int, User] = {}
    if user_ids:
        for u in db.query(User).filter(User.id.in_(user_ids)).all():
            users_by_id[u.id] = u

    attendees_by_day: dict[int, list[int]] = {}
    for day_id, uid in all_attendee_rows:
        attendees_by_day.setdefault(day_id, []).append(uid)

    def beds_needed(uids: list[int], on_date) -> int:
        n = 0
        for uid in uids:
            u = users_by_id.get(uid)
            if u is None:
                continue
            bracket = classify(
                u.birthdate, on_date, baby_max=baby_max, kid_max=kid_max
            )
            if bracket != AgeBracket.BABY:
                n += 1
        return n

    peak = 0
    peak_date = None
    days_out: list[EventDayOut] = []
    days_attended_per_user: dict[int, int] = {}
    for day in event.days:
        day_attendees = attendees_by_day.get(day.id, [])
        demand = beds_needed(day_attendees, day.date)
        if demand > peak:
            peak = demand
            peak_date = day.date
        for uid in day_attendees:
            days_attended_per_user[uid] = days_attended_per_user.get(uid, 0) + 1
        chors = [ChorOut.model_validate(c) for c in day.chors]
        activities = []
        for a in day.activities:
            ao = ActivityOut.model_validate(a)
            ao.attendee_user_ids = [att.user_id for att in a.attendees]
            activities.append(ao)
        days_out.append(
            EventDayOut(
                id=day.id,
                date=day.date,
                chors=chors,
                activities=activities,
                attendee_user_ids=day_attendees,
                bed_demand=demand,
            )
        )

    # Build a unique-attendee summary so the frontend can render names + per-family
    # groupings without a separate users lookup (parents only see their own family
    # via /users, but the page header should still show everyone going).
    family_ids = {u.family_id for u in users_by_id.values() if u.family_id is not None}
    family_names_by_id: dict[int, str] = {}
    if family_ids:
        for f in db.query(Family).filter(Family.id.in_(family_ids)).all():
            family_names_by_id[f.id] = f.name
    attendees_out: list[AttendeeSummary] = []
    for uid, days_count in days_attended_per_user.items():
        u = users_by_id.get(uid)
        if u is None:
            continue
        attendees_out.append(
            AttendeeSummary(
                user_id=u.id,
                name=u.name,
                role=u.role.value if hasattr(u.role, "value") else str(u.role),
                family_id=u.family_id,
                family_name=(
                    family_names_by_id.get(u.family_id) if u.family_id else None
                ),
                profile_picture_url=u.profile_picture_url,
                days_attended=days_count,
            )
        )
    attendees_out.sort(
        key=lambda a: (
            a.family_name or "ÅÅÅ",
            0 if a.role != "child" else 1,
            a.name.lower(),
        )
    )

    # Photo summary: count + designated group photo URL (if any). Cheap single
    # query so list views can render hero/badge without per-event lookups.
    photo_count = (
        db.query(sa_func.count(EventPhoto.id))
        .filter(EventPhoto.event_id == event.id)
        .scalar()
        or 0
    )
    group_photo = (
        db.query(EventPhoto.url)
        .filter(
            EventPhoto.event_id == event.id,
            EventPhoto.is_group_photo.is_(True),
        )
        .order_by(EventPhoto.id.desc())
        .first()
    )

    return EventOut(
        id=event.id,
        name=event.name,
        description=event.description,
        address=event.address,
        location_url=event.location_url,
        summerhouse_url=event.summerhouse_url,
        start_date=event.start_date,
        end_date=event.end_date,
        host_user_id=event.host_user_id,
        status=event.status,
        bed_count=event.bed_count,
        summerhouse_title=event.summerhouse_title,
        summerhouse_summary=event.summerhouse_summary,
        summerhouse_image_url=event.summerhouse_image_url,
        summerhouse_scraped_at=event.summerhouse_scraped_at,
        created_at=event.created_at,
        days=days_out,
        bed_demand=BedDemand(
            bed_count=event.bed_count, peak=peak, peak_date=peak_date
        ),
        attendees=attendees_out,
        group_photo_url=group_photo[0] if group_photo else None,
        photo_count=int(photo_count),
    )


@router.get("", response_model=list[EventOut])
def list_events(db: DbDep, _: CurrentUser) -> list[EventOut]:
    rows = db.query(Event).order_by(Event.start_date.desc()).all()
    return [_to_out(db, e) for e in rows]


@router.get("/next", response_model=EventOut)
def next_event(db: DbDep, _: CurrentUser) -> EventOut:
    today = date.today()
    e = (
        db.query(Event)
        .filter(Event.end_date >= today)
        .order_by(Event.start_date.asc())
        .first()
    )
    if e is None:
        raise HTTPException(status_code=404, detail="Ingen kommende arrangementer")
    return _to_out(db, e)


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: int, db: DbDep, _: CurrentUser) -> EventOut:
    e = db.get(Event, event_id)
    if e is None:
        raise HTTPException(status_code=404, detail="Arrangement findes ikke")
    return _to_out(db, e)


@router.post(
    "",
    response_model=EventOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_not_child)],
)
def create_event(payload: EventCreate, db: DbDep, user: CurrentUser) -> EventOut:
    # Only admin can create events for now (parents can be host once an admin makes them so).
    if user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Kun admin kan oprette arrangementer")
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=400, detail="Slutdato skal være på eller efter startdato")

    e = Event(
        name=payload.name,
        description=payload.description,
        address=payload.address,
        location_url=payload.location_url,
        summerhouse_url=payload.summerhouse_url,
        start_date=payload.start_date,
        end_date=payload.end_date,
        bed_count=payload.bed_count,
        host_user_id=payload.host_user_id,
        status=EventStatus.PLANLAGT,
    )
    db.add(e)
    db.flush()
    build_event_days_and_chors(db, e)
    notify_event_created(db, actor=user, event_name=e.name, event_id=e.id)
    db.commit()
    db.refresh(e)
    return _to_out(db, e)


@router.patch("/{event_id}", response_model=EventOut)
def update_event(
    event_id: int, payload: EventUpdate, db: DbDep, user: CurrentUser
) -> EventOut:
    e = db.get(Event, event_id)
    if e is None:
        raise HTTPException(status_code=404, detail="Arrangement findes ikke")
    if user.role.value != "admin" and user.id != e.host_user_id:
        raise HTTPException(status_code=403, detail="Kun host eller admin kan redigere")

    prev_summerhouse_url = (e.summerhouse_url or "").strip() or None
    for field in (
        "name", "description", "address", "location_url", "summerhouse_url",
        "bed_count", "host_user_id",
    ):
        v = getattr(payload, field)
        if v is not None:
            setattr(e, field, v)
    new_summerhouse_url = (e.summerhouse_url or "").strip() or None
    summerhouse_just_added = (
        prev_summerhouse_url is None and new_summerhouse_url is not None
    )

    new_start = payload.start_date or e.start_date
    new_end = payload.end_date or e.end_date
    if new_end < new_start:
        raise HTTPException(status_code=400, detail="Slutdato skal være på eller efter startdato")

    if (payload.start_date is not None and payload.start_date != e.start_date) or (
        payload.end_date is not None and payload.end_date != e.end_date
    ):
        e.start_date = new_start
        e.end_date = new_end
        # Drop days that no longer fall in the new range; rebuild missing ones.
        for day in list(e.days):
            if day.date < new_start or day.date > new_end:
                db.delete(day)
        db.flush()
        build_event_days_and_chors(db, e)

    if summerhouse_just_added and new_summerhouse_url:
        notify_summerhouse_added(
            db,
            actor=user,
            event_name=e.name,
            event_id=e.id,
            url=new_summerhouse_url,
        )

    db.commit()
    db.refresh(e)
    return _to_out(db, e)


@router.delete("/{event_id}", status_code=204)
def delete_event(event_id: int, db: DbDep, user: CurrentUser):
    if user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Kun admin kan slette arrangementer")
    e = db.get(Event, event_id)
    if e is None:
        return
    db.delete(e)
    db.commit()


@router.post("/{event_id}/open", response_model=EventOut)
def open_event(event_id: int, db: DbDep, user: CurrentUser) -> EventOut:
    e = db.get(Event, event_id)
    if e is None:
        raise HTTPException(status_code=404, detail="Arrangement findes ikke")
    if user.role.value != "admin" and user.id != e.host_user_id:
        raise HTTPException(status_code=403, detail="Kun host eller admin")
    e.status = EventStatus.AABENT
    db.commit()
    db.refresh(e)
    return _to_out(db, e)


@router.post("/{event_id}/lock-attendance", response_model=EventOut)
def lock_attendance(event_id: int, db: DbDep, user: CurrentUser) -> EventOut:
    e = db.get(Event, event_id)
    if e is None:
        raise HTTPException(status_code=404, detail="Arrangement findes ikke")
    if user.role.value != "admin" and user.id != e.host_user_id:
        raise HTTPException(status_code=403, detail="Kun host eller admin")
    e.status = EventStatus.DELTAGELSE_LAAST
    db.commit()
    db.refresh(e)
    return _to_out(db, e)


# ---- Attendance ----

def _users_to_toggle(db, user: User) -> list[User]:
    if user.role == UserRole.CHILD:
        return [user]
    kids = db.query(User).filter(User.parent_user_id == user.id).all()
    return [user, *kids]


def _resolve_attendance_user_ids(
    db, *, caller: User, payload_user_ids: list[int] | None
) -> list[int]:
    """Decide which users get their attendance toggled.

    - `payload_user_ids` None: backward-compatible default (caller + own kids).
    - `payload_user_ids` provided: validate every id either belongs to the
      caller's family unit or the caller is admin; otherwise 403.
    """
    if payload_user_ids is None:
        return [u.id for u in _users_to_toggle(db, caller)]
    if not payload_user_ids:
        return []
    targets = (
        db.query(User).filter(User.id.in_(set(payload_user_ids))).all()
    )
    if len(targets) != len(set(payload_user_ids)):
        raise HTTPException(status_code=404, detail="Bruger findes ikke")
    if caller.role != UserRole.ADMIN:
        for t in targets:
            if t.family_id is None or t.family_id != caller.family_id:
                raise HTTPException(
                    status_code=403,
                    detail="Du kan kun tilmelde personer i din egen familie",
                )
    return [t.id for t in targets]


def _can_toggle(event: Event) -> bool:
    return event.status in (EventStatus.PLANLAGT, EventStatus.AABENT)


def _set_attendance(db, day: EventDay, user_ids: list[int], present: bool) -> None:
    if present:
        existing = {
            uid
            for (uid,) in db.query(Attendance.user_id)
            .filter(Attendance.event_day_id == day.id, Attendance.user_id.in_(user_ids))
            .all()
        }
        for uid in user_ids:
            if uid not in existing:
                db.add(Attendance(event_day_id=day.id, user_id=uid))
    else:
        db.query(Attendance).filter(
            Attendance.event_day_id == day.id, Attendance.user_id.in_(user_ids)
        ).delete(synchronize_session=False)


def _was_present(db, day_id: int, user_id: int) -> bool:
    return (
        db.query(Attendance)
        .filter(Attendance.event_day_id == day_id, Attendance.user_id == user_id)
        .first()
        is not None
    )


@router.post("/{event_id}/days/{day_id}/attendance")
def toggle_attendance(
    event_id: int,
    day_id: int,
    payload: AttendanceToggle,
    db: DbDep,
    user: CurrentUser,
):
    event = db.get(Event, event_id)
    day = db.get(EventDay, day_id)
    if event is None or day is None or day.event_id != event.id:
        raise HTTPException(status_code=404, detail="Dag findes ikke")
    if not _can_toggle(event):
        raise HTTPException(status_code=400, detail="Tilmelding er låst")

    user_ids = _resolve_attendance_user_ids(
        db, caller=user, payload_user_ids=payload.user_ids
    )
    actor_was_present = _was_present(db, day_id, user.id)
    _set_attendance(db, day, user_ids, payload.present)
    actor_is_present = payload.present and user.id in user_ids
    days_added = 1 if (not actor_was_present and actor_is_present) else 0
    days_removed = 1 if (actor_was_present and not actor_is_present) else 0
    notify_attendance_changed(
        db,
        actor=user,
        event_name=event.name,
        event_id=event.id,
        days_added=days_added,
        days_removed=days_removed,
    )
    db.commit()

    attendees = (
        db.query(Attendance.user_id).filter(Attendance.event_day_id == day_id).all()
    )
    return {
        "event_day_id": day_id,
        "attendee_user_ids": [uid for (uid,) in attendees],
    }


@router.post("/{event_id}/attendance")
def bulk_attendance(
    event_id: int, payload: BulkAttendance, db: DbDep, user: CurrentUser
):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Arrangement findes ikke")
    if not _can_toggle(event):
        raise HTTPException(status_code=400, detail="Tilmelding er låst")
    days = db.query(EventDay).filter(
        EventDay.event_id == event.id, EventDay.id.in_(payload.day_ids)
    ).all()
    user_ids = _resolve_attendance_user_ids(
        db, caller=user, payload_user_ids=payload.user_ids
    )
    days_added = 0
    days_removed = 0
    for d in days:
        was_present = _was_present(db, d.id, user.id)
        _set_attendance(db, d, user_ids, payload.present)
        if payload.present and not was_present:
            days_added += 1
        elif not payload.present and was_present:
            days_removed += 1
    notify_attendance_changed(
        db,
        actor=user,
        event_name=event.name,
        event_id=event.id,
        days_added=days_added,
        days_removed=days_removed,
    )
    db.commit()
    return {"updated_day_ids": [d.id for d in days]}


# ---- Chors listing helper ----

@router.get("/{event_id}/unassigned-chors", response_model=list[ChorOut])
def unassigned_chors(event_id: int, db: DbDep, _: CurrentUser) -> list[ChorOut]:
    rows = (
        db.query(Chor)
        .join(EventDay, Chor.event_day_id == EventDay.id)
        .filter(EventDay.event_id == event_id, Chor.assignee_user_id.is_(None))
        .all()
    )
    return [ChorOut.model_validate(c) for c in rows]


# ---- Summerhouse scrape ----

@router.post("/{event_id}/scrape-summerhouse", response_model=EventOut)
def scrape_summerhouse_endpoint(event_id: int, db: DbDep, user: CurrentUser) -> EventOut:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Arrangement findes ikke")
    if user.role != UserRole.ADMIN and user.id != event.host_user_id:
        raise HTTPException(status_code=403, detail="Kun host eller admin kan hente feriehus")
    if not event.summerhouse_url:
        raise HTTPException(status_code=400, detail="Intet feriehus-link på arrangementet")

    try:
        result = fetch_summerhouse(event.summerhouse_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Kunne ikke hente feriehus: {e}") from e

    event.summerhouse_title = result.title
    event.summerhouse_summary = result.summary
    event.summerhouse_image_url = result.image_url
    event.summerhouse_scraped_at = now_utc()
    db.commit()
    db.refresh(event)
    return _to_out(db, event)


# ---- Finalize ----

@router.post("/{event_id}/finalize", response_model=EventOut)
def finalize_event(event_id: int, db: DbDep, user: CurrentUser) -> EventOut:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Arrangement findes ikke")
    if user.role != UserRole.ADMIN and user.id != event.host_user_id:
        raise HTTPException(status_code=403, detail="Kun host eller admin kan afslutte")

    if is_budget_locked(event):
        return _to_out(db, event)

    result = compute_event_budget(db, event)
    event.status = EventStatus.AFSLUTTET
    db.flush()
    notify_event_finalized(db, actor=user, event_name=event.name, event_id=event.id)

    sender = get_email_sender()

    # Aggregate shares per family so each family gets one email per recipient.
    family_totals: dict[int, dict[str, int]] = {}
    for s in result.shares:
        agg = family_totals.setdefault(
            s.family_id, {"paid": 0, "share": 0, "net": 0}
        )
        agg["paid"] += s.paid_cents
        agg["share"] += s.share_cents
        agg["net"] += s.net_cents

    total = sum(result.per_category_totals.values())
    settlement_lines = [
        f"  Familie {t.from_family_id} betaler {t.amount_cents/100:.2f} kr til familie {t.to_family_id}"
        for t in result.settlements
    ] or ["  Ingen overførsler nødvendige"]

    user_ids = [s.user_id for s in result.shares]
    family_recipients: dict[int, list[User]] = {}
    if user_ids:
        for u in db.query(User).filter(User.id.in_(user_ids)).all():
            if not u.email or u.role == UserRole.CHILD:
                continue
            family_recipients.setdefault(u.family_id or 0, []).append(u)

    for family_id, agg in family_totals.items():
        for u in family_recipients.get(family_id, []):
            body = (
                f"Hej {u.name},\n\n"
                f"Arrangementet '{event.name}' er nu afsluttet.\n"
                f"Total udgift: {total/100:.2f} kr.\n"
                f"Din families andel: {agg['share']/100:.2f} kr.\n"
                f"Din families betalt: {agg['paid']/100:.2f} kr.\n"
                f"Din families netto: {agg['net']/100:.2f} kr.\n\n"
                f"Overførsler:\n" + "\n".join(settlement_lines) + "\n\n"
                "Tak for denne gang. Vi ses næste år!"
            )
            sender.send(
                db, to=u.email, subject=f"Endeligt regnskab: {event.name}", body=body
            )

    db.commit()
    db.refresh(event)
    return _to_out(db, event)


# ---- Cross-event gallery ---------------------------------------------------
#
# Declared BEFORE the `/{event_id}/photos/...` routes so the literal
# `/photos/gallery` segment isn't mis-matched as `event_id=photos`.


@router.get("/photos/gallery", response_model=list[GalleryPhotoOut])
def gallery(
    db: DbDep,
    _: CurrentUser,
    limit: int = 200,
    offset: int = 0,
) -> list[GalleryPhotoOut]:
    """Cross-event photo feed for the history gallery / dias mode.

    Newest events first, then chronologically by `taken_at` within each event.
    Paginated to keep the initial payload sane on a large archive.
    """
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    rows = (
        db.query(EventPhoto, Event.name, Event.start_date)
        .join(Event, EventPhoto.event_id == Event.id)
        .order_by(
            Event.start_date.desc(),
            EventPhoto.taken_at.asc().nullslast(),
            EventPhoto.id.asc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        GalleryPhotoOut(
            id=p.id,
            event_id=p.event_id,
            event_name=ename,
            event_start_date=edate,
            url=p.url,
            caption=p.caption,
            is_group_photo=p.is_group_photo,
            taken_at=p.taken_at,
            width=p.width,
            height=p.height,
        )
        for (p, ename, edate) in rows
    ]


# ---- Per-event photos ------------------------------------------------------
#
# Authorization model:
# - Any authenticated user can list & upload photos to any event. We deliberately
#   don't gate on attendance — partners want to share the album with extended
#   family who didn't make it that year.
# - Edit/delete is restricted to (a) the photo's uploader, (b) the event host,
#   (c) any admin. Group-photo flag follows the same rule.


def _can_edit_photo(*, user: User, event: Event, photo: EventPhoto) -> bool:
    if user.role == UserRole.ADMIN:
        return True
    if event.host_user_id and event.host_user_id == user.id:
        return True
    if photo.uploader_user_id and photo.uploader_user_id == user.id:
        return True
    return False


@router.get("/{event_id}/photos", response_model=list[EventPhotoOut])
def list_event_photos(
    event_id: int, db: DbDep, _: CurrentUser
) -> list[EventPhotoOut]:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Arrangement findes ikke")
    rows = (
        db.query(EventPhoto)
        .filter(EventPhoto.event_id == event_id)
        .order_by(
            # Group photo first, then chronologically by taken_at (falling back
            # to upload order when EXIF is missing).
            EventPhoto.is_group_photo.desc(),
            EventPhoto.taken_at.asc().nullslast(),
            EventPhoto.id.asc(),
        )
        .all()
    )
    return [EventPhotoOut.model_validate(p) for p in rows]


@router.post(
    "/{event_id}/photos",
    response_model=list[EventPhotoOut],
    status_code=status.HTTP_201_CREATED,
)
def upload_event_photos(
    event_id: int,
    files: list[UploadFile],
    db: DbDep,
    user: CurrentUser,
) -> list[EventPhotoOut]:
    """Upload one or more photos to an event.

    Accepts multipart `files` (repeatable form field) so the frontend can
    drop a whole batch in one request. Each file is independently validated
    and saved; partial failures abort the whole request.
    """
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Arrangement findes ikke")
    if not files:
        raise HTTPException(status_code=400, detail="Ingen filer")

    created: list[EventPhoto] = []
    for f in files:
        saved = save_event_photo(f, event_id=event_id)
        photo = EventPhoto(
            event_id=event_id,
            uploader_user_id=user.id,
            url=saved.url,
            taken_at=saved.taken_at,
            width=saved.width,
            height=saved.height,
        )
        db.add(photo)
        created.append(photo)
    db.commit()
    for p in created:
        db.refresh(p)
    return [EventPhotoOut.model_validate(p) for p in created]


@router.patch(
    "/{event_id}/photos/{photo_id}", response_model=EventPhotoOut
)
def update_event_photo(
    event_id: int,
    photo_id: int,
    payload: EventPhotoUpdate,
    db: DbDep,
    user: CurrentUser,
) -> EventPhotoOut:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Arrangement findes ikke")
    photo = db.get(EventPhoto, photo_id)
    if photo is None or photo.event_id != event_id:
        raise HTTPException(status_code=404, detail="Foto findes ikke")
    if not _can_edit_photo(user=user, event=event, photo=photo):
        raise HTTPException(status_code=403, detail="Adgang nægtet")

    if "caption" in payload.model_fields_set:
        photo.caption = (payload.caption or "").strip() or None
    if payload.is_group_photo is True and not photo.is_group_photo:
        # Enforce "exactly one group photo per event" by clearing any siblings.
        (
            db.query(EventPhoto)
            .filter(
                EventPhoto.event_id == event_id,
                EventPhoto.id != photo.id,
                EventPhoto.is_group_photo.is_(True),
            )
            .update({EventPhoto.is_group_photo: False})
        )
        photo.is_group_photo = True
    elif payload.is_group_photo is False:
        photo.is_group_photo = False
    db.commit()
    db.refresh(photo)
    return EventPhotoOut.model_validate(photo)


@router.delete(
    "/{event_id}/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_event_photo(
    event_id: int, photo_id: int, db: DbDep, user: CurrentUser
) -> None:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Arrangement findes ikke")
    photo = db.get(EventPhoto, photo_id)
    if photo is None or photo.event_id != event_id:
        raise HTTPException(status_code=404, detail="Foto findes ikke")
    if not _can_edit_photo(user=user, event=event, photo=photo):
        raise HTTPException(status_code=403, detail="Adgang nægtet")
    # Best-effort delete the file on disk.
    from app.core.config import get_settings

    settings = get_settings()
    if photo.url.startswith("/uploads/"):
        rel = photo.url[len("/uploads/"):]
        candidate = settings.uploads_dir / rel
        try:
            candidate.unlink(missing_ok=True)
        except OSError:
            pass
    db.delete(photo)
    db.commit()
