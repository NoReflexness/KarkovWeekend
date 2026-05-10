"""Family import/export in YAML.

Export dumps every family along with its parents/admins and their children,
deliberately *omitting* anything secret (passwords, invite tokens, password
reset tokens, internal IDs, timestamps).

Import reads a YAML structure and creates only what is missing. Existing
families (matched by name), users (matched by email, case-insensitive) and
children (matched by parent + name) are left untouched. Passwords are *never*
written from the import file: new parents must finish onboarding via an invite
token (admin can issue one) or a parent re-create can set the child's data.

YAML schema::

    families:
      - name: Karkov
        profile_picture_url: null
        members:
          - name: Mads
            email: mads@example.com
            birthdate: 1985-05-04
            role: parent       # parent | admin (child role goes under children:)
            notify_email: true
            profile_picture_url: null
            children:
              - name: Liva
                birthdate: 2020-04-01
                email: null
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session

from app.models.family import Family
from app.models.user import User, UserRole

# ---- Pydantic input models -------------------------------------------------


class ChildIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = Field(min_length=1, max_length=120)
    birthdate: date | None = None
    email: str | None = None
    profile_picture_url: str | None = None


class MemberIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = Field(min_length=1, max_length=120)
    email: str | None = None
    birthdate: date | None = None
    role: str = "parent"
    notify_email: bool | None = None
    profile_picture_url: str | None = None
    children: list[ChildIn] = Field(default_factory=list)


class FamilyIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = Field(min_length=1, max_length=120)
    profile_picture_url: str | None = None
    members: list[MemberIn] = Field(default_factory=list)


class FamiliesDocIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    families: list[FamilyIn] = Field(default_factory=list)


# ---- Errors ---------------------------------------------------------------


class FamilyIOError(ValueError):
    """Raised for malformed YAML or schema violations during import."""


# ---- Export ---------------------------------------------------------------


def _user_to_dict(u: User, *, include_children: list[dict] | None) -> dict[str, Any]:
    out: dict[str, Any] = {"name": u.name}
    if u.email:
        out["email"] = u.email
    if u.birthdate:
        out["birthdate"] = u.birthdate.isoformat()
    out["role"] = (u.role.value if hasattr(u.role, "value") else str(u.role))
    if u.notify_email is not None:
        out["notify_email"] = bool(u.notify_email)
    if u.profile_picture_url:
        out["profile_picture_url"] = u.profile_picture_url
    if include_children is not None:
        out["children"] = include_children
    return out


def _child_to_dict(c: User) -> dict[str, Any]:
    out: dict[str, Any] = {"name": c.name}
    if c.birthdate:
        out["birthdate"] = c.birthdate.isoformat()
    if c.email:
        out["email"] = c.email
    if c.profile_picture_url:
        out["profile_picture_url"] = c.profile_picture_url
    return out


def export_families_yaml(db: Session) -> str:
    families = db.query(Family).order_by(Family.name).all()
    famdocs: list[dict[str, Any]] = []
    for fam in families:
        non_children = [
            m for m in fam.members if m.role != UserRole.CHILD
        ]
        non_children.sort(key=lambda u: (u.name or ""))
        members_out: list[dict[str, Any]] = []
        for member in non_children:
            child_dicts = [
                _child_to_dict(c)
                for c in sorted(member.children, key=lambda c: c.name or "")
            ]
            members_out.append(
                _user_to_dict(member, include_children=child_dicts)
            )
        fam_dict: dict[str, Any] = {"name": fam.name}
        if fam.profile_picture_url:
            fam_dict["profile_picture_url"] = fam.profile_picture_url
        fam_dict["members"] = members_out
        famdocs.append(fam_dict)
    doc = {
        "exported_at": (
            datetime.now(UTC).replace(microsecond=0, tzinfo=None).isoformat() + "Z"
        ),
        "families": famdocs,
    }
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)


# ---- Import ---------------------------------------------------------------


class ImportSummary(BaseModel):
    families_created: int = 0
    parents_created: int = 0
    children_created: int = 0
    skipped: dict[str, int] = Field(
        default_factory=lambda: {"families": 0, "parents": 0, "children": 0}
    )


def _parse_role(value: str) -> UserRole:
    v = (value or "").lower()
    if v == "admin":
        return UserRole.ADMIN
    return UserRole.PARENT


def import_families_yaml(db: Session, text: str) -> ImportSummary:
    if not isinstance(text, str) or not text.strip():
        raise FamilyIOError("Tom YAML")
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as e:  # noqa: BLE001
        raise FamilyIOError(f"Ugyldig YAML: {e}") from e
    if raw is None:
        raise FamilyIOError("Tom YAML")
    try:
        doc = FamiliesDocIn.model_validate(raw)
    except ValidationError as e:
        raise FamilyIOError(f"Ugyldigt YAML-skema: {e.errors()[:3]}") from e

    summary = ImportSummary()
    for fam_in in doc.families:
        existing_fam = (
            db.query(Family).filter(Family.name == fam_in.name).one_or_none()
        )
        if existing_fam is None:
            fam = Family(
                name=fam_in.name, profile_picture_url=fam_in.profile_picture_url
            )
            db.add(fam)
            db.flush()
            summary.families_created += 1
        else:
            fam = existing_fam
            summary.skipped["families"] += 1

        for m_in in fam_in.members:
            user = _import_member(db, fam=fam, m_in=m_in, summary=summary)
            for c_in in m_in.children:
                _import_child(db, parent=user, c_in=c_in, family_id=fam.id, summary=summary)

    db.commit()
    return summary


def _import_member(
    db: Session, *, fam: Family, m_in: MemberIn, summary: ImportSummary
) -> User:
    if m_in.email:
        existing = (
            db.query(User).filter(User.email == m_in.email.lower()).one_or_none()
        )
        if existing is not None:
            summary.skipped["parents"] += 1
            return existing
    user = User(
        family_id=fam.id,
        name=m_in.name,
        email=m_in.email.lower() if m_in.email else None,
        birthdate=m_in.birthdate,
        role=_parse_role(m_in.role),
        notify_email=m_in.notify_email,
        profile_picture_url=m_in.profile_picture_url,
    )
    db.add(user)
    db.flush()
    summary.parents_created += 1
    return user


def _import_child(
    db: Session,
    *,
    parent: User,
    c_in: ChildIn,
    family_id: int,
    summary: ImportSummary,
) -> User:
    existing = (
        db.query(User)
        .filter(User.parent_user_id == parent.id, User.name == c_in.name)
        .one_or_none()
    )
    if existing is not None:
        summary.skipped["children"] += 1
        return existing
    child = User(
        family_id=family_id,
        parent_user_id=parent.id,
        name=c_in.name,
        email=c_in.email.lower() if c_in.email else None,
        birthdate=c_in.birthdate,
        role=UserRole.CHILD,
        profile_picture_url=c_in.profile_picture_url,
    )
    db.add(child)
    db.flush()
    summary.children_created += 1
    return child
