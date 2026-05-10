"""Dev-only debug endpoints. In prod, set DEBUG=false to disable."""

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.core.deps import DbDep
from app.models.email_outbox import EmailOutbox

router = APIRouter(prefix="/_debug", tags=["debug"])


def _ensure_debug() -> None:
    if not get_settings().debug:
        raise HTTPException(status_code=404, detail="Not found")


@router.get("/last-email")
def last_email(db: DbDep):
    _ensure_debug()
    msg = db.query(EmailOutbox).order_by(EmailOutbox.id.desc()).first()
    if msg is None:
        raise HTTPException(status_code=404, detail="No emails sent")
    return {"id": msg.id, "to": msg.to, "subject": msg.subject, "body": msg.body}


@router.get("/outbox")
def list_outbox(db: DbDep, limit: int = 50):
    _ensure_debug()
    rows = db.query(EmailOutbox).order_by(EmailOutbox.id.desc()).limit(limit).all()
    return [{"id": r.id, "to": r.to, "subject": r.subject, "created_at": r.created_at} for r in rows]
