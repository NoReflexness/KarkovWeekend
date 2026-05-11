"""Email sender abstraction.

Two implementations live here, both behind the same `EmailSender` Protocol:

- `OutboxEmailSender` (always-on, persists to the EmailOutbox table) is used in
  dev/test so we can verify content without a live SMTP server.
- `SmtpEmailSender` is used additionally in prod when `SMTP_HOST` is configured.
  It still writes to the outbox first so we always have an audit trail; if the
  SMTP delivery fails we log and keep the outbox row.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from typing import Protocol

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.email_outbox import EmailOutbox

log = logging.getLogger(__name__)


class EmailSender(Protocol):
    def send(self, db: Session, *, to: str, subject: str, body: str) -> EmailOutbox: ...


class OutboxEmailSender:
    """Persist email to DB outbox and log to stdout for visibility."""

    def send(self, db: Session, *, to: str, subject: str, body: str) -> EmailOutbox:
        msg = EmailOutbox(to=to, subject=subject, body=body)
        db.add(msg)
        db.flush()
        log.info("EMAIL [outbox#%s] -> %s | %s\n%s", msg.id, to, subject, body)
        return msg


def deliver_via_smtp(*, to: str, subject: str, body: str) -> None:
    """Send a single message via the configured SMTP server and raise on failure.

    Used by `SmtpEmailSender` (which swallows the error and logs it) and by the
    admin `POST /admin/test-email` endpoint (which surfaces the error to the
    caller so misconfigurations are immediately obvious instead of silently
    being captured into the outbox).
    """
    settings = get_settings()
    if not settings.smtp_host:
        raise RuntimeError("SMTP_HOST is not configured")
    message = EmailMessage()
    message["From"] = formataddr((settings.smtp_from_name, settings.smtp_from_address))
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    if settings.smtp_use_tls and not settings.smtp_starttls:
        client_cls: type = smtplib.SMTP_SSL
    else:
        client_cls = smtplib.SMTP
    with client_cls(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        if settings.smtp_starttls and client_cls is smtplib.SMTP:
            smtp.starttls()
        if settings.smtp_username and settings.smtp_password:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


class SmtpEmailSender:
    """Outbox-first SMTP sender. Outbox row is always written; SMTP failure is logged."""

    def send(self, db: Session, *, to: str, subject: str, body: str) -> EmailOutbox:
        outbox = OutboxEmailSender().send(db, to=to, subject=subject, body=body)
        if not get_settings().smtp_host:
            return outbox
        try:
            deliver_via_smtp(to=to, subject=subject, body=body)
        except Exception:  # noqa: BLE001
            log.exception("SMTP send failed; outbox#%s retained", outbox.id)
        return outbox


def _build_sender() -> EmailSender:
    settings = get_settings()
    if settings.smtp_host:
        log.info("Email: using SMTP sender via %s:%s", settings.smtp_host, settings.smtp_port)
        return SmtpEmailSender()
    return OutboxEmailSender()


_sender: EmailSender = _build_sender()


def get_email_sender() -> EmailSender:
    return _sender


def reset_email_sender_for_tests() -> None:
    """Pytest fixture helper — re-evaluate sender after env changes."""
    global _sender
    _sender = _build_sender()
