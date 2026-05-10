from fastapi import APIRouter, HTTPException, status

from app.core.deps import CurrentUser, DbDep
from app.models.event import Event
from app.models.expense import Expense
from app.models.expense_category import ExpenseCategory
from app.models.user import User, UserRole
from app.schemas.expense import (
    BudgetOut,
    ExpenseCreate,
    ExpenseOut,
    ExpenseUpdate,
    SettlementOut,
    UserShareOut,
)
from app.services.budget import compute_event_budget, is_budget_locked

router = APIRouter(tags=["expenses"])


def _ensure_not_child(user) -> None:
    if user.role == UserRole.CHILD:
        raise HTTPException(status_code=403, detail="Børn kan ikke se eller redigere budget")


def _payer_names_for(db, expenses: list[Expense]) -> dict[int, str]:
    ids = {e.paid_by_user_id for e in expenses}
    if not ids:
        return {}
    rows = db.query(User).filter(User.id.in_(ids)).all()
    return {u.id: u.name for u in rows}


def _to_out(e: Expense, names: dict[int, str]) -> ExpenseOut:
    out = ExpenseOut.model_validate(e)
    out.paid_by_user_name = names.get(e.paid_by_user_id)
    return out


@router.get("/events/{event_id}/expenses", response_model=list[ExpenseOut])
def list_expenses(event_id: int, db: DbDep, user: CurrentUser) -> list[ExpenseOut]:
    _ensure_not_child(user)
    rows = (
        db.query(Expense)
        .filter(Expense.event_id == event_id)
        .order_by(Expense.created_at.desc())
        .all()
    )
    names = _payer_names_for(db, rows)
    return [_to_out(r, names) for r in rows]


@router.post(
    "/events/{event_id}/expenses",
    response_model=ExpenseOut,
    status_code=status.HTTP_201_CREATED,
)
def create_expense(
    event_id: int, payload: ExpenseCreate, db: DbDep, user: CurrentUser
) -> ExpenseOut:
    _ensure_not_child(user)
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Arrangement findes ikke")
    if is_budget_locked(event) and user.role != UserRole.ADMIN:
        raise HTTPException(status_code=400, detail="Budget er afsluttet og låst")
    cat = db.get(ExpenseCategory, payload.category_id)
    if cat is None:
        raise HTTPException(status_code=404, detail="Kategori findes ikke")

    e = Expense(
        event_id=event_id,
        category_id=payload.category_id,
        chor_id=payload.chor_id,
        paid_by_user_id=user.id,
        amount_cents=payload.amount_cents,
        description=payload.description,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return _to_out(e, _payer_names_for(db, [e]))


@router.patch("/expenses/{expense_id}", response_model=ExpenseOut)
def update_expense(
    expense_id: int, payload: ExpenseUpdate, db: DbDep, user: CurrentUser
) -> ExpenseOut:
    e = db.get(Expense, expense_id)
    if e is None:
        raise HTTPException(status_code=404, detail="Udgift findes ikke")
    event = db.get(Event, e.event_id)
    if event and is_budget_locked(event) and user.role != UserRole.ADMIN:
        raise HTTPException(status_code=400, detail="Budget er afsluttet og låst")
    if user.role != UserRole.ADMIN and e.paid_by_user_id != user.id:
        raise HTTPException(status_code=403, detail="Adgang nægtet")
    for f in ("category_id", "amount_cents", "description", "chor_id"):
        v = getattr(payload, f)
        if v is not None:
            setattr(e, f, v)
    if payload.paid_by_user_id is not None and payload.paid_by_user_id != e.paid_by_user_id:
        if user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=403,
                detail="Kun administratorer kan ændre, hvem der har betalt",
            )
        target = db.get(User, payload.paid_by_user_id)
        if target is None:
            raise HTTPException(status_code=404, detail="Bruger findes ikke")
        if target.role == UserRole.CHILD:
            raise HTTPException(
                status_code=400, detail="Et barn kan ikke stå som betaler"
            )
        e.paid_by_user_id = target.id
    db.commit()
    db.refresh(e)
    return _to_out(e, _payer_names_for(db, [e]))


@router.delete("/expenses/{expense_id}", status_code=204)
def delete_expense(expense_id: int, db: DbDep, user: CurrentUser):
    e = db.get(Expense, expense_id)
    if e is None:
        return
    event = db.get(Event, e.event_id)
    if event and is_budget_locked(event) and user.role != UserRole.ADMIN:
        raise HTTPException(status_code=400, detail="Budget er afsluttet og låst")
    if user.role != UserRole.ADMIN and e.paid_by_user_id != user.id:
        raise HTTPException(status_code=403, detail="Adgang nægtet")
    db.delete(e)
    db.commit()


@router.get("/events/{event_id}/budget", response_model=BudgetOut)
def get_event_budget(event_id: int, db: DbDep, user: CurrentUser) -> BudgetOut:
    _ensure_not_child(user)
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Arrangement findes ikke")
    result = compute_event_budget(db, event)

    family_ids = {s.family_id for s in result.shares}
    family_ids.update(t.from_family_id for t in result.settlements)
    family_ids.update(t.to_family_id for t in result.settlements)
    from app.models.family import Family

    family_names: dict[int, str] = {}
    if family_ids:
        rows = db.query(Family).filter(Family.id.in_(family_ids)).all()
        for f in rows:
            family_names[f.id] = f.name

    return BudgetOut(
        event_id=event.id,
        is_final=is_budget_locked(event),
        total_cents=sum(result.per_category_totals.values()),
        per_category_cents=result.per_category_totals,
        shares=[
            UserShareOut(
                user_id=s.user_id,
                family_id=s.family_id,
                paid_cents=s.paid_cents,
                share_cents=s.share_cents,
                net_cents=s.net_cents,
            )
            for s in result.shares
        ],
        settlements=[
            SettlementOut(
                from_family_id=t.from_family_id,
                to_family_id=t.to_family_id,
                amount_cents=t.amount_cents,
            )
            for t in result.settlements
        ],
        family_names=family_names,
    )
