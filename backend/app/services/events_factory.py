"""Build EventDay rows and seed the per-day chors when an event is created."""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.chor import Chor, ChorAction, ChorMeal
from app.models.event import Event, EventDay


def _date_range_inclusive(start: date, end: date):
    if end < start:
        raise ValueError("end_date must be on or after start_date")
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def build_event_days_and_chors(db: Session, event: Event) -> None:
    """Idempotently create EventDay + 6 chors per day."""
    db.flush()
    existing_days = {
        d.date: d
        for d in db.query(EventDay).filter(EventDay.event_id == event.id).all()
    }

    for d in _date_range_inclusive(event.start_date, event.end_date):
        day = existing_days.get(d)
        if day is None:
            day = EventDay(event_id=event.id, date=d)
            db.add(day)
            db.flush()

        existing_pairs = {
            (c.meal, c.action)
            for c in db.query(Chor).filter(Chor.event_day_id == day.id).all()
        }
        for meal in ChorMeal:
            for action in ChorAction:
                if (meal, action) in existing_pairs:
                    continue
                db.add(Chor(event_day_id=day.id, meal=meal, action=action))
        db.flush()
