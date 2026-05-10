"""Glue between DB models and the pure balance service."""

from datetime import date

from sqlalchemy.orm import Session

from app.models.attendance import Attendance
from app.models.event import Event, EventDay, EventStatus
from app.models.expense import Expense
from app.models.expense_category import ExpenseCategory
from app.models.pricing_rules import PricingRules
from app.models.user import User
from app.services.balance import (
    BudgetCategoryInput,
    BudgetInput,
    BudgetUserInput,
    compute_balance,
)
from app.services.pricing import classify, weight_for


def build_budget_input(db: Session, event: Event) -> BudgetInput:
    pr = db.get(PricingRules, 1) or PricingRules(id=1, baby_max_age=2, kid_max_age=13)

    day_ids = [d.id for d in event.days]
    attendances = (
        db.query(Attendance)
        .join(EventDay, EventDay.id == Attendance.event_day_id)
        .filter(EventDay.event_id == event.id)
        .all()
    )
    attended_days_per_user: dict[int, int] = {}
    for a in attendances:
        attended_days_per_user[a.user_id] = attended_days_per_user.get(a.user_id, 0) + 1

    user_ids = list(attended_days_per_user.keys())
    if not user_ids:
        return BudgetInput(users=[], categories=[])

    users = db.query(User).filter(User.id.in_(user_ids)).all()
    today = event.start_date or date.today()

    user_inputs: list[BudgetUserInput] = []
    for u in users:
        bracket = classify(
            u.birthdate, today, baby_max=pr.baby_max_age, kid_max=pr.kid_max_age
        )
        user_inputs.append(
            BudgetUserInput(
                user_id=u.id,
                family_id=u.family_id or 0,
                attendance_days=attended_days_per_user.get(u.id, 0),
                weight=weight_for(bracket),
            )
        )

    expenses = db.query(Expense).filter(Expense.event_id == event.id).all()
    by_cat: dict[int, list[tuple[int, int]]] = {}
    for e in expenses:
        by_cat.setdefault(e.category_id, []).append((e.paid_by_user_id, e.amount_cents))

    categories = db.query(ExpenseCategory).all()
    cat_inputs = [
        BudgetCategoryInput(
            category_id=c.id,
            name=c.name,
            is_per_night=c.is_per_night,
            expenses=by_cat.get(c.id, []),
        )
        for c in categories
        if c.id in by_cat  # only categories that have expenses
    ]
    return BudgetInput(users=user_inputs, categories=cat_inputs)


def compute_event_budget(db: Session, event: Event):
    bi = build_budget_input(db, event)
    return compute_balance(bi)


def is_budget_locked(event: Event) -> bool:
    return event.status == EventStatus.AFSLUTTET
