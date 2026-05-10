"""Initial data seeding (admin user, default expense categories, pricing rules).

Idempotent: safe to call on every boot.
"""

from app.core.config import get_settings
from app.core.db import SessionLocal


def seed_initial_data() -> None:
    """Seed defaults. Each block is guarded so adding models later is non-breaking."""
    settings = get_settings()
    db = SessionLocal()
    try:
        try:
            from app.models.pricing_rules import PricingRules
        except ImportError:
            PricingRules = None  # type: ignore[assignment]
        try:
            from app.models.expense_category import ExpenseCategory
        except ImportError:
            ExpenseCategory = None  # type: ignore[assignment]
        try:
            from app.core.security import hash_password
            from app.models.user import User, UserRole
        except ImportError:
            User = None  # type: ignore[assignment]

        if PricingRules and not db.query(PricingRules).first():
            db.add(PricingRules(id=1, baby_max_age=2, kid_max_age=13))

        if ExpenseCategory:
            # (name, is_per_person, is_per_night, is_utility)
            defaults = [
                ("Udlejning", False, False, False),
                ("Forbrug", False, False, True),
                ("Mad", True, True, False),
                ("Aktiviteter", True, False, False),
                ("Andet", False, False, False),
            ]
            for name, per_person, per_night, utility in defaults:
                existing = db.query(ExpenseCategory).filter_by(name=name).first()
                if existing is None:
                    db.add(
                        ExpenseCategory(
                            name=name,
                            is_per_person=per_person,
                            is_per_night=per_night,
                            is_utility=utility,
                        )
                    )
                elif name == "Forbrug" and not existing.is_utility:
                    # Backfill the new utility flag for previously seeded rows.
                    existing.is_utility = True

        if User and not db.query(User).filter_by(email=settings.admin_email).first():
            db.add(
                User(
                    email=settings.admin_email,
                    password_hash=hash_password(settings.admin_password),
                    name=settings.admin_name,
                    role=UserRole.ADMIN,
                )
            )

        db.commit()
    finally:
        db.close()
