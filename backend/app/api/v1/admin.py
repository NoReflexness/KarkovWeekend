from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, EmailStr, Field

from app.core.config import get_settings
from app.core.deps import CurrentUser, DbDep, require_admin
from app.models.expense_category import ExpenseCategory
from app.models.pricing_rules import PricingRules
from app.models.email_outbox import EmailOutbox
from app.services.email import deliver_via_smtp
from app.services.family_io import (
    FamilyIOError,
    ImportSummary,
    export_families_yaml,
    import_families_yaml,
)

router = APIRouter(tags=["admin"])


class PricingRulesIn(BaseModel):
    baby_max_age: int = Field(ge=0, le=18)
    kid_max_age: int = Field(ge=1, le=21)


class PricingRulesOut(BaseModel):
    baby_max_age: int
    kid_max_age: int


@router.get("/pricing-rules", response_model=PricingRulesOut)
def get_pricing_rules(db: DbDep, _: CurrentUser) -> PricingRulesOut:
    pr = db.get(PricingRules, 1)
    if pr is None:
        raise HTTPException(status_code=500, detail="Pricing rules not seeded")
    return PricingRulesOut(baby_max_age=pr.baby_max_age, kid_max_age=pr.kid_max_age)


@router.patch(
    "/pricing-rules",
    response_model=PricingRulesOut,
    dependencies=[Depends(require_admin)],
)
def update_pricing_rules(payload: PricingRulesIn, db: DbDep) -> PricingRulesOut:
    if payload.baby_max_age >= payload.kid_max_age:
        raise HTTPException(status_code=400, detail="baby_max_age skal være mindre end kid_max_age")
    pr = db.get(PricingRules, 1)
    if pr is None:
        pr = PricingRules(id=1, **payload.model_dump())
        db.add(pr)
    else:
        pr.baby_max_age = payload.baby_max_age
        pr.kid_max_age = payload.kid_max_age
    db.commit()
    return PricingRulesOut(baby_max_age=pr.baby_max_age, kid_max_age=pr.kid_max_age)


class ExpenseCategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    is_per_person: bool = False
    is_per_night: bool = False
    is_utility: bool = False


class ExpenseCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    is_per_person: bool | None = None
    is_per_night: bool | None = None
    is_utility: bool | None = None


class ExpenseCategoryOut(BaseModel):
    id: int
    name: str
    is_per_person: bool
    is_per_night: bool
    is_utility: bool


def _to_out(cat: ExpenseCategory) -> ExpenseCategoryOut:
    return ExpenseCategoryOut(
        id=cat.id,
        name=cat.name,
        is_per_person=cat.is_per_person,
        is_per_night=cat.is_per_night,
        is_utility=cat.is_utility,
    )


@router.get("/expense-categories", response_model=list[ExpenseCategoryOut])
def list_expense_categories(db: DbDep, _: CurrentUser) -> list[ExpenseCategoryOut]:
    return [
        _to_out(c)
        for c in db.query(ExpenseCategory).order_by(ExpenseCategory.name).all()
    ]


@router.post(
    "/expense-categories",
    response_model=ExpenseCategoryOut,
    status_code=201,
    dependencies=[Depends(require_admin)],
)
def create_expense_category(payload: ExpenseCategoryIn, db: DbDep) -> ExpenseCategoryOut:
    if db.query(ExpenseCategory).filter(ExpenseCategory.name == payload.name).first():
        raise HTTPException(status_code=400, detail="Kategori findes allerede")
    cat = ExpenseCategory(**payload.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return _to_out(cat)


@router.patch(
    "/expense-categories/{category_id}",
    response_model=ExpenseCategoryOut,
    dependencies=[Depends(require_admin)],
)
def update_expense_category(
    category_id: int, payload: ExpenseCategoryUpdate, db: DbDep
) -> ExpenseCategoryOut:
    cat = db.get(ExpenseCategory, category_id)
    if cat is None:
        raise HTTPException(status_code=404, detail="Kategori findes ikke")
    if payload.name is not None and payload.name != cat.name:
        clash = (
            db.query(ExpenseCategory)
            .filter(ExpenseCategory.name == payload.name, ExpenseCategory.id != cat.id)
            .first()
        )
        if clash is not None:
            raise HTTPException(status_code=400, detail="Kategori findes allerede")
        cat.name = payload.name
    for field_name in ("is_per_person", "is_per_night", "is_utility"):
        v = getattr(payload, field_name)
        if v is not None:
            setattr(cat, field_name, v)
    db.commit()
    db.refresh(cat)
    return _to_out(cat)


@router.delete(
    "/expense-categories/{category_id}",
    status_code=204,
    dependencies=[Depends(require_admin)],
)
def delete_expense_category(category_id: int, db: DbDep) -> None:
    from app.models.expense import Expense

    cat = db.get(ExpenseCategory, category_id)
    if cat is None:
        return
    in_use = db.query(Expense).filter(Expense.category_id == category_id).first()
    if in_use is not None:
        raise HTTPException(
            status_code=400,
            detail="Kategorien er i brug af mindst én udgift og kan ikke slettes",
        )
    db.delete(cat)
    db.commit()


# ---- Family import / export (admin) ---------------------------------------


class FamilyImportIn(BaseModel):
    yaml: str = Field(min_length=1)


@router.get(
    "/admin/families/export",
    response_class=PlainTextResponse,
    dependencies=[Depends(require_admin)],
)
def export_families(db: DbDep) -> PlainTextResponse:
    """Dump all families/parents/children as YAML (no passwords or tokens)."""
    body = export_families_yaml(db)
    return PlainTextResponse(
        content=body,
        media_type="application/yaml; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="families.yaml"',
        },
    )


@router.post(
    "/admin/families/import",
    response_model=ImportSummary,
    dependencies=[Depends(require_admin)],
)
def import_families(payload: FamilyImportIn, db: DbDep) -> ImportSummary:
    """Create families/parents/children from a YAML document.

    Existing rows (matched by family name, parent email, child name within
    parent) are left untouched. Passwords are *never* set from the import;
    new parents complete onboarding via an invite token as today.
    """
    try:
        return import_families_yaml(db, payload.yaml)
    except FamilyIOError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ---- Email probe (admin) --------------------------------------------------


class TestEmailIn(BaseModel):
    to: EmailStr
    subject: str = Field(default="Karkov Weekend SMTP test", min_length=1, max_length=200)
    body: str = Field(
        default=(
            "Hej!\n\nDette er en SMTP-test fra Karkov Weekend. Hvis du modtager "
            "denne mail, så er udsendelse konfigureret korrekt.\n"
        ),
        min_length=1,
        max_length=4000,
    )


class TestEmailOut(BaseModel):
    outbox_id: int
    to: EmailStr
    subject: str
    smtp_attempted: bool
    smtp_error: str | None = None


@router.post(
    "/admin/test-email",
    response_model=TestEmailOut,
    dependencies=[Depends(require_admin)],
)
def send_test_email(payload: TestEmailIn, db: DbDep) -> TestEmailOut:
    """Send a probe email to verify SMTP is wired correctly.

    Always writes an outbox row (so it shows up next to real notifications).
    When `SMTP_HOST` is set we also fire the real SMTP delivery and surface
    any error directly to the caller — the regular notification path swallows
    SMTP errors, which is great for not breaking user requests but useless
    for debugging credentials, ports or TLS.
    """
    # Write the outbox row up-front so the test message shows up alongside
    # real notifications. Then deliver via SMTP exactly once (if configured),
    # capturing the error for the caller instead of swallowing it like the
    # background notification path does.
    outbox = EmailOutbox(to=payload.to, subject=payload.subject, body=payload.body)
    db.add(outbox)
    db.commit()
    db.refresh(outbox)
    settings = get_settings()
    smtp_attempted = bool(settings.smtp_host)
    smtp_error: str | None = None
    if smtp_attempted:
        try:
            deliver_via_smtp(to=payload.to, subject=payload.subject, body=payload.body)
        except Exception as e:  # noqa: BLE001
            smtp_error = f"{type(e).__name__}: {e}"
    return TestEmailOut(
        outbox_id=outbox.id,
        to=payload.to,
        subject=payload.subject,
        smtp_attempted=smtp_attempted,
        smtp_error=smtp_error,
    )
