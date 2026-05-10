from datetime import date

from app.models.chor import Chor
from app.models.event import Event, EventDay
from app.services.events_factory import build_event_days_and_chors


def test_builds_one_day_per_date_in_range_inclusive(db_session):
    event = Event(name="Test", start_date=date(2026, 6, 1), end_date=date(2026, 6, 4))
    db_session.add(event)
    db_session.flush()

    build_event_days_and_chors(db_session, event)
    db_session.commit()

    days = db_session.query(EventDay).filter(EventDay.event_id == event.id).all()
    assert sorted(d.date for d in days) == [
        date(2026, 6, 1),
        date(2026, 6, 2),
        date(2026, 6, 3),
        date(2026, 6, 4),
    ]


def test_seeds_six_chors_per_day(db_session):
    event = Event(name="Test", start_date=date(2026, 6, 1), end_date=date(2026, 6, 2))
    db_session.add(event)
    db_session.flush()
    build_event_days_and_chors(db_session, event)
    db_session.commit()

    chors = (
        db_session.query(Chor)
        .join(EventDay, EventDay.id == Chor.event_day_id)
        .filter(EventDay.event_id == event.id)
        .all()
    )
    assert len(chors) == 12  # 2 days * 6 chors
    per_day = {}
    for c in chors:
        per_day.setdefault(c.event_day_id, []).append((c.meal.value, c.action.value))
    for v in per_day.values():
        assert sorted(v) == sorted(
            [
                ("morgenmad", "forberedelse"),
                ("morgenmad", "oprydning"),
                ("frokost", "forberedelse"),
                ("frokost", "oprydning"),
                ("aftensmad", "forberedelse"),
                ("aftensmad", "oprydning"),
            ]
        )


def test_idempotent_does_not_duplicate(db_session):
    event = Event(name="Test", start_date=date(2026, 6, 1), end_date=date(2026, 6, 1))
    db_session.add(event)
    db_session.flush()
    build_event_days_and_chors(db_session, event)
    build_event_days_and_chors(db_session, event)
    db_session.commit()

    chors = (
        db_session.query(Chor)
        .join(EventDay, EventDay.id == Chor.event_day_id)
        .filter(EventDay.event_id == event.id)
        .all()
    )
    assert len(chors) == 6
