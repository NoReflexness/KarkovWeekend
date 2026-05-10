import json
import time
from collections.abc import Iterator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.deps import CurrentUser, DbDep
from app.models.chat_message import ChatMessage, ChatMessageKind
from app.models.user import User, UserRole
from app.schemas.chat import (
    ChatMessageCreate,
    ChatMessageOut,
    NotifyPrefIn,
    NotifyPrefOut,
    ReadStateIn,
    ReadStateOut,
)
from app.core.security import now_utc
from app.services.notification_queue import flush_due_pending_notifications

router = APIRouter(prefix="/chat", tags=["chat"])


def _to_out(msg: ChatMessage, *, name: str | None) -> ChatMessageOut:
    return ChatMessageOut(
        id=msg.id,
        kind=msg.kind.value if hasattr(msg.kind, "value") else msg.kind,
        user_id=msg.user_id,
        user_name=name,
        body=msg.body,
        related_event_id=msg.related_event_id,
        icon=msg.icon,
        created_at=msg.created_at,
    )


def _hydrate(db, rows: list[ChatMessage]) -> list[ChatMessageOut]:
    user_ids = {m.user_id for m in rows if m.user_id is not None}
    names: dict[int, str] = {}
    if user_ids:
        for u in db.query(User.id, User.name).filter(User.id.in_(user_ids)).all():
            names[u.id] = u.name
    return [_to_out(m, name=names.get(m.user_id) if m.user_id else None) for m in rows]


@router.get("/messages", response_model=list[ChatMessageOut])
def list_messages(
    db: DbDep,
    _: CurrentUser,
    since_id: int | None = None,
    limit: int = 100,
) -> list[ChatMessageOut]:
    limit = max(1, min(limit, 500))
    if flush_due_pending_notifications(db):
        db.commit()
    q = db.query(ChatMessage)
    if since_id is not None:
        # New-tail polling: return only newer rows in chronological order.
        rows = (
            q.filter(ChatMessage.id > since_id)
            .order_by(ChatMessage.id.asc())
            .limit(limit)
            .all()
        )
        return _hydrate(db, rows)
    # Initial load: most recent N, returned chronologically (oldest first).
    rows = (
        q.order_by(ChatMessage.id.desc()).limit(limit).all()
    )
    rows.reverse()
    return _hydrate(db, rows)


@router.get("/stream")
def stream_messages(_: CurrentUser, since_id: int = 0) -> StreamingResponse:
    """Server-Sent Events stream of new chat messages.

    Pushes messages to the client as they appear, replacing the polling that
    used to happen every 5 seconds. Auth is via the same access-token cookie
    used elsewhere; we resolve it once via the regular `CurrentUser` dependency
    and then tail the database with short-lived sessions inside the generator
    so the request session itself can be closed by FastAPI right away.
    """
    settings = get_settings()
    poll = max(0.0, float(settings.chat_stream_poll_seconds))
    max_seconds = max(1.0, float(settings.chat_stream_max_seconds))
    keepalive = max(1.0, float(settings.chat_stream_keepalive_seconds))

    def _generate() -> Iterator[bytes]:
        last_id = max(0, int(since_id))
        started = time.monotonic()
        last_emit = started
        # Tell the browser to back off a little before reconnecting.
        yield b"retry: 3000\n\n"
        while True:
            with SessionLocal() as db:
                if flush_due_pending_notifications(db):
                    db.commit()
                rows = (
                    db.query(ChatMessage)
                    .filter(ChatMessage.id > last_id)
                    .order_by(ChatMessage.id.asc())
                    .limit(200)
                    .all()
                )
                if rows:
                    out = _hydrate(db, rows)
                    last_id = rows[-1].id
                    payload = json.dumps([m.model_dump(mode="json") for m in out])
                    yield f"event: messages\ndata: {payload}\n\n".encode()
                    last_emit = time.monotonic()
            now = time.monotonic()
            if now - started >= max_seconds:
                yield b"event: bye\ndata: {}\n\n"
                return
            if now - last_emit >= keepalive:
                yield b": keepalive\n\n"
                last_emit = now
            if poll > 0:
                time.sleep(poll)
            else:
                # Drain immediately for tests; bail after one pass.
                return

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post(
    "/messages", response_model=ChatMessageOut, status_code=status.HTTP_201_CREATED
)
def post_message(
    payload: ChatMessageCreate, db: DbDep, user: CurrentUser
) -> ChatMessageOut:
    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=400, detail="Beskeden må ikke være tom")
    msg = ChatMessage(
        kind=ChatMessageKind.USER,
        user_id=user.id,
        body=body,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return _to_out(msg, name=user.name)


@router.delete("/messages/{message_id}", status_code=204)
def delete_message(message_id: int, db: DbDep, user: CurrentUser):
    msg = db.get(ChatMessage, message_id)
    if msg is None:
        return
    if user.role != UserRole.ADMIN and msg.user_id != user.id:
        raise HTTPException(status_code=403, detail="Adgang nægtet")
    if msg.kind == ChatMessageKind.SYSTEM and user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Systembeskeder kan kun slettes af admin")
    db.delete(msg)
    db.commit()


# ---- Notification preferences ---------------------------------------------


@router.get("/notify-pref", response_model=NotifyPrefOut)
def get_notify_pref(_: DbDep, user: CurrentUser) -> NotifyPrefOut:
    needs = user.notify_email is None and user.notify_prompted_at is None
    return NotifyPrefOut(
        notify_email=user.notify_email,
        notify_prompted_at=user.notify_prompted_at,
        needs_prompt=needs,
    )


@router.put("/notify-pref", response_model=NotifyPrefOut)
def set_notify_pref(
    payload: NotifyPrefIn, db: DbDep, user: CurrentUser
) -> NotifyPrefOut:
    user.notify_email = payload.notify_email
    user.notify_prompted_at = now_utc()
    db.commit()
    db.refresh(user)
    return NotifyPrefOut(
        notify_email=user.notify_email,
        notify_prompted_at=user.notify_prompted_at,
        needs_prompt=False,
    )


@router.post("/notify-pref/dismiss", response_model=NotifyPrefOut)
def dismiss_notify_prompt(db: DbDep, user: CurrentUser) -> NotifyPrefOut:
    """Mark prompt as seen without setting a preference (user clicked 'spørg senere')."""
    user.notify_prompted_at = now_utc()
    db.commit()
    db.refresh(user)
    return NotifyPrefOut(
        notify_email=user.notify_email,
        notify_prompted_at=user.notify_prompted_at,
        needs_prompt=False,
    )


# ---- Read state -----------------------------------------------------------


def _latest_chat_id(db) -> int:
    row = db.query(ChatMessage.id).order_by(ChatMessage.id.desc()).first()
    return int(row[0]) if row else 0


@router.get("/read-state", response_model=ReadStateOut)
def get_read_state(db: DbDep, user: CurrentUser) -> ReadStateOut:
    return ReadStateOut(
        last_read_message_id=user.last_read_chat_message_id or 0,
        latest_message_id=_latest_chat_id(db),
    )


@router.put("/read-state", response_model=ReadStateOut)
def set_read_state(
    payload: ReadStateIn, db: DbDep, user: CurrentUser
) -> ReadStateOut:
    """Advance (monotonically) the user's last-read chat message id.

    Lower values are silently ignored so that a stale tab cannot rewind a
    fresher tab's marker. Values above the current latest message id are
    clamped to the latest id so the marker never points at the future.
    """
    latest = _latest_chat_id(db)
    capped = min(int(payload.last_read_message_id), latest)
    if capped > (user.last_read_chat_message_id or 0):
        user.last_read_chat_message_id = capped
        db.commit()
        db.refresh(user)
    return ReadStateOut(
        last_read_message_id=user.last_read_chat_message_id or 0,
        latest_message_id=latest,
    )
