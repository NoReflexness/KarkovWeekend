from fastapi import APIRouter, HTTPException, status

from app.core.deps import CurrentUser, DbDep
from app.models.activity import Activity, ActivityAttendee
from app.models.event import Event, EventDay
from app.models.user import User, UserRole
from app.schemas.activity import ActivityCreate, ActivityUpdate, AttendeesIn
from app.schemas.event import ActivityOut
from app.services.notifications import notify_activity_created, notify_activity_joined

router = APIRouter(tags=["activities"])


def _hydrate(activity: Activity) -> ActivityOut:
    out = ActivityOut.model_validate(activity)
    out.attendee_user_ids = [a.user_id for a in activity.attendees]
    return out


@router.post(
    "/events/{event_id}/days/{day_id}/activities",
    response_model=ActivityOut,
    status_code=status.HTTP_201_CREATED,
)
def create_activity(
    event_id: int,
    day_id: int,
    payload: ActivityCreate,
    db: DbDep,
    user: CurrentUser,
) -> ActivityOut:
    event = db.get(Event, event_id)
    day = db.get(EventDay, day_id)
    if event is None or day is None or day.event_id != event.id:
        raise HTTPException(status_code=404, detail="Dag findes ikke")
    a = Activity(
        event_day_id=day.id,
        name=payload.name,
        description=payload.description,
        time=payload.time,
        created_by_user_id=user.id,
    )
    db.add(a)
    db.flush()
    notify_activity_created(
        db, actor=user, event_name=event.name, event_id=event.id, activity_name=a.name
    )
    db.commit()
    db.refresh(a)
    return _hydrate(a)


@router.patch("/activities/{activity_id}", response_model=ActivityOut)
def update_activity(
    activity_id: int, payload: ActivityUpdate, db: DbDep, user: CurrentUser
) -> ActivityOut:
    a = db.get(Activity, activity_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Aktivitet findes ikke")
    if user.role != UserRole.ADMIN and a.created_by_user_id != user.id:
        raise HTTPException(status_code=403, detail="Adgang nægtet")
    for f in ("name", "description", "time"):
        v = getattr(payload, f)
        if v is not None:
            setattr(a, f, v)
    db.commit()
    db.refresh(a)
    return _hydrate(a)


@router.delete("/activities/{activity_id}", status_code=204)
def delete_activity(activity_id: int, db: DbDep, user: CurrentUser):
    a = db.get(Activity, activity_id)
    if a is None:
        return
    if user.role != UserRole.ADMIN and a.created_by_user_id != user.id:
        raise HTTPException(status_code=403, detail="Adgang nægtet")
    db.delete(a)
    db.commit()


@router.post("/activities/{activity_id}/attendees", response_model=ActivityOut)
def add_attendees(
    activity_id: int, payload: AttendeesIn, db: DbDep, user: CurrentUser
) -> ActivityOut:
    a = db.get(Activity, activity_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Aktivitet findes ikke")

    existing = {att.user_id for att in a.attendees}
    added: list[User] = []
    for uid in payload.user_ids:
        target = db.get(User, uid)
        if target is None:
            raise HTTPException(status_code=404, detail=f"Bruger {uid} findes ikke")
        is_admin = user.role == UserRole.ADMIN
        is_self = target.id == user.id
        is_parent = target.parent_user_id == user.id
        if not (is_admin or is_self or is_parent):
            raise HTTPException(status_code=403, detail="Adgang nægtet")
        if uid in existing:
            continue
        db.add(ActivityAttendee(activity_id=a.id, user_id=uid))
        added.append(target)
    db.flush()
    day = db.get(EventDay, a.event_day_id)
    event_id = day.event_id if day else None
    for target in added:
        notify_activity_joined(
            db,
            actor=user,
            target_name=target.name,
            activity_name=a.name,
            event_id=event_id,
        )
    db.commit()
    db.refresh(a)
    return _hydrate(a)


@router.delete("/activities/{activity_id}/attendees/{user_id}", status_code=204)
def remove_attendee(activity_id: int, user_id: int, db: DbDep, user: CurrentUser):
    a = db.get(Activity, activity_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Aktivitet findes ikke")
    target = db.get(User, user_id)
    if target is None:
        return
    is_admin = user.role == UserRole.ADMIN
    is_self = target.id == user.id
    is_parent = target.parent_user_id == user.id
    if not (is_admin or is_self or is_parent):
        raise HTTPException(status_code=403, detail="Adgang nægtet")
    db.query(ActivityAttendee).filter(
        ActivityAttendee.activity_id == a.id, ActivityAttendee.user_id == user_id
    ).delete(synchronize_session=False)
    db.commit()
