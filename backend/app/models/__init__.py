"""SQLAlchemy models. Importing this module ensures all tables register on Base.metadata."""

from app.models.activity import Activity, ActivityAttendee
from app.models.attendance import Attendance
from app.models.chat_message import ChatMessage, ChatMessageKind
from app.models.chor import Chor, ChorAction, ChorMeal
from app.models.email_outbox import EmailOutbox
from app.models.event import Event, EventDay, EventStatus
from app.models.event_photo import EventPhoto
from app.models.expense import Expense
from app.models.expense_category import ExpenseCategory
from app.models.family import Family
from app.models.invite_token import InviteToken
from app.models.password_reset_token import PasswordResetToken
from app.models.pending_notification import PendingNotification, PendingNotificationKind
from app.models.pricing_rules import PricingRules
from app.models.push_subscription import PushSubscription
from app.models.user import User, UserRole

__all__ = [
    "Activity",
    "ActivityAttendee",
    "Attendance",
    "ChatMessage",
    "ChatMessageKind",
    "Chor",
    "ChorAction",
    "ChorMeal",
    "EmailOutbox",
    "Event",
    "EventDay",
    "EventPhoto",
    "EventStatus",
    "Expense",
    "ExpenseCategory",
    "Family",
    "InviteToken",
    "PasswordResetToken",
    "PendingNotification",
    "PendingNotificationKind",
    "PricingRules",
    "PushSubscription",
    "User",
    "UserRole",
]
