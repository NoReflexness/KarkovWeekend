from fastapi import APIRouter, HTTPException, status

from app.core.deps import CurrentUser, DbDep
from app.models.chor import Chor
from app.models.event import EventDay
from app.models.expense import Expense
from app.models.user import User, UserRole
from app.schemas.activity import ChorAssignIn
from app.schemas.event import ChorOut
from app.services.notifications import notify_chor_assigned

router = APIRouter(prefix="/chors", tags=["chors"])


def _load_chor(db, chor_id: int) -> Chor:
    c = db.get(Chor, chor_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Opgaven findes ikke")
    return c


@router.post("/{chor_id}/assign", response_model=ChorOut)
def assign_chor(chor_id: int, payload: ChorAssignIn, db: DbDep, user: CurrentUser) -> ChorOut:
    c = _load_chor(db, chor_id)
    target = db.get(User, payload.user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Bruger findes ikke")

    # Caller permissions: admin, the user themself, the user's parent, or the host.
    is_self = user.id == target.id
    is_parent = target.parent_user_id == user.id
    is_admin = user.role == UserRole.ADMIN
    if not (is_self or is_parent or is_admin):
        raise HTTPException(status_code=403, detail="Adgang nægtet")

    if c.assignee_user_id is not None and c.assignee_user_id != target.id:
        raise HTTPException(status_code=400, detail="Opgaven er allerede tildelt")

    c.assignee_user_id = target.id
    day = db.get(EventDay, c.event_day_id)
    event_id = day.event_id if day else None
    label = f"{c.meal.value if hasattr(c.meal, 'value') else c.meal} ({c.action.value if hasattr(c.action, 'value') else c.action})"
    notify_chor_assigned(
        db, actor=user, target_name=target.name, chor_label=label, event_id=event_id
    )
    db.commit()
    db.refresh(c)
    return ChorOut.model_validate(c)


@router.delete("/{chor_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chor(chor_id: int, db: DbDep, user: CurrentUser) -> None:
    """Admin-only deletion of a chor.

    Linked expenses keep their `chor_id` cleared so spending history is preserved
    without dangling references. Done explicitly rather than relying on the FK
    `ON DELETE SET NULL` so it works under SQLite (tests) too.
    """
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Kun admin kan slette opgaver")
    c = db.get(Chor, chor_id)
    if c is None:
        return
    db.query(Expense).filter(Expense.chor_id == chor_id).update(
        {Expense.chor_id: None}, synchronize_session=False
    )
    db.delete(c)
    db.commit()


@router.post("/{chor_id}/unassign", response_model=ChorOut)
def unassign_chor(chor_id: int, db: DbDep, user: CurrentUser) -> ChorOut:
    c = _load_chor(db, chor_id)
    if c.assignee_user_id is None:
        return ChorOut.model_validate(c)
    assignee = db.get(User, c.assignee_user_id)
    is_self = assignee is not None and assignee.id == user.id
    is_parent = assignee is not None and assignee.parent_user_id == user.id
    is_admin = user.role == UserRole.ADMIN
    if not (is_self or is_parent or is_admin):
        raise HTTPException(status_code=403, detail="Adgang nægtet")
    c.assignee_user_id = None
    db.commit()
    db.refresh(c)
    return ChorOut.model_validate(c)
