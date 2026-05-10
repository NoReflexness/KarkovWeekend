from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.core.config import get_settings
from app.core.deps import CurrentUser, DbDep, require_admin
from app.core.security import now_utc, random_token
from app.models.expense import Expense
from app.models.family import Family
from app.models.invite_token import InviteToken
from app.models.user import User, UserRole
from app.schemas.family import (
    FamilyCreate,
    FamilyOut,
    FamilyUpdate,
    InviteCreate,
    InviteOut,
    InviteSendResult,
)
from app.services.email import get_email_sender
from app.services.uploads import save_profile_picture

router = APIRouter(prefix="/families", tags=["families"])


@router.get("", response_model=list[FamilyOut])
def list_families(db: DbDep, user: CurrentUser) -> list[FamilyOut]:
    if user.role == UserRole.ADMIN:
        rows = db.query(Family).order_by(Family.name).all()
    else:
        rows = db.query(Family).filter(Family.id == user.family_id).all()
    return [FamilyOut.model_validate(f) for f in rows]


@router.post(
    "",
    response_model=FamilyOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_family(payload: FamilyCreate, db: DbDep) -> FamilyOut:
    fam = Family(name=payload.name)
    db.add(fam)
    db.commit()
    db.refresh(fam)
    return FamilyOut.model_validate(fam)


@router.get("/{family_id}", response_model=FamilyOut)
def get_family(family_id: int, db: DbDep, user: CurrentUser) -> FamilyOut:
    fam = db.get(Family, family_id)
    if fam is None:
        raise HTTPException(status_code=404, detail="Familie findes ikke")
    if user.role != UserRole.ADMIN and user.family_id != family_id:
        raise HTTPException(status_code=403, detail="Adgang nægtet")
    return FamilyOut.model_validate(fam)


@router.patch("/{family_id}", response_model=FamilyOut)
def update_family(
    family_id: int, payload: FamilyUpdate, db: DbDep, user: CurrentUser
) -> FamilyOut:
    fam = db.get(Family, family_id)
    if fam is None:
        raise HTTPException(status_code=404, detail="Familie findes ikke")
    if user.role != UserRole.ADMIN and user.family_id != family_id:
        raise HTTPException(status_code=403, detail="Adgang nægtet")
    if payload.name is not None:
        fam.name = payload.name
    if payload.profile_picture_url is not None:
        fam.profile_picture_url = payload.profile_picture_url
    db.commit()
    db.refresh(fam)
    return FamilyOut.model_validate(fam)


@router.post("/{family_id}/profile-picture", response_model=FamilyOut)
def upload_family_picture(
    family_id: int, file: UploadFile, db: DbDep, user: CurrentUser
) -> FamilyOut:
    fam = db.get(Family, family_id)
    if fam is None:
        raise HTTPException(status_code=404, detail="Familie findes ikke")
    if user.role != UserRole.ADMIN and user.family_id != family_id:
        raise HTTPException(status_code=403, detail="Adgang nægtet")
    fam.profile_picture_url = save_profile_picture(file, subdir=f"families/{family_id}")
    db.commit()
    db.refresh(fam)
    return FamilyOut.model_validate(fam)


def _invite_email_body(fam: Family, invite: InviteToken) -> str:
    settings = get_settings()
    return (
        f"Hej!\n\nDu er blevet inviteret til familien '{fam.name}' på {settings.app_name}.\n"
        f"Tilmeld dig her:\n{settings.public_base_url}/registrer?token={invite.token}\n\n"
        "Linket udløber om 14 dage."
    )


def _invite_to_out(invite: InviteToken) -> InviteOut:
    return InviteOut(
        id=invite.id,
        email=invite.email,
        family_id=invite.family_id,
        token=invite.token,
        expires_at=invite.expires_at,
        notified_at=invite.notified_at,
        used_at=invite.used_at,
    )


@router.get(
    "/{family_id}/invites",
    response_model=list[InviteOut],
    dependencies=[Depends(require_admin)],
)
def list_invites(family_id: int, db: DbDep, include_used: bool = False) -> list[InviteOut]:
    q = db.query(InviteToken).filter(InviteToken.family_id == family_id)
    if not include_used:
        q = q.filter(InviteToken.used_at.is_(None))
    return [_invite_to_out(i) for i in q.order_by(InviteToken.created_at.desc()).all()]


@router.post(
    "/{family_id}/invites",
    response_model=InviteOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_invite(family_id: int, payload: InviteCreate, db: DbDep) -> InviteOut:
    fam = db.get(Family, family_id)
    if fam is None:
        raise HTTPException(status_code=404, detail="Familie findes ikke")

    email = payload.email.lower()
    if db.query(User).filter(User.email == email).one_or_none():
        raise HTTPException(status_code=400, detail="Email er allerede registreret")
    existing = (
        db.query(InviteToken)
        .filter(InviteToken.family_id == family_id, InviteToken.email == email, InviteToken.used_at.is_(None))
        .one_or_none()
    )
    if existing is not None:
        raise HTTPException(
            status_code=400,
            detail="En ubrugt invitation til denne email findes allerede for denne familie",
        )

    invite = InviteToken(
        token=random_token(),
        email=email,
        family_id=family_id,
        expires_at=now_utc() + timedelta(days=14),
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    if payload.notify:
        get_email_sender().send(
            db, to=email, subject=f"Invitation til {fam.name}", body=_invite_email_body(fam, invite)
        )
        invite.notified_at = now_utc()
        db.commit()
        db.refresh(invite)

    return _invite_to_out(invite)


@router.post(
    "/{family_id}/invites/send-pending",
    response_model=InviteSendResult,
    dependencies=[Depends(require_admin)],
)
def send_pending_invites(family_id: int, db: DbDep) -> InviteSendResult:
    fam = db.get(Family, family_id)
    if fam is None:
        raise HTTPException(status_code=404, detail="Familie findes ikke")

    pending = (
        db.query(InviteToken)
        .filter(
            InviteToken.family_id == family_id,
            InviteToken.used_at.is_(None),
            InviteToken.notified_at.is_(None),
        )
        .all()
    )
    sender = get_email_sender()
    sent_now = []
    for invite in pending:
        sender.send(
            db,
            to=invite.email,
            subject=f"Invitation til {fam.name}",
            body=_invite_email_body(fam, invite),
        )
        invite.notified_at = now_utc()
        sent_now.append(invite)
    db.commit()
    for invite in sent_now:
        db.refresh(invite)
    return InviteSendResult(sent=len(sent_now), invites=[_invite_to_out(i) for i in sent_now])


@router.delete(
    "/{family_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_family(family_id: int, db: DbDep, user: CurrentUser) -> None:
    """Admin-only deletion of a family.

    Cascade deletes all family members (and their children) via the ORM
    relationship and pending invites via DB-level FK. Refuses if any member has
    registered expenses, or if the calling admin is themselves in the family.
    """
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Kun admin kan slette familier")
    fam = db.get(Family, family_id)
    if fam is None:
        raise HTTPException(status_code=404, detail="Familie findes ikke")
    if user.family_id == family_id:
        raise HTTPException(
            status_code=400, detail="Du kan ikke slette din egen familie"
        )
    member_ids = [m.id for m in fam.members]
    if member_ids:
        has_expenses = (
            db.query(Expense).filter(Expense.paid_by_user_id.in_(member_ids)).first()
        )
        if has_expenses is not None:
            raise HTTPException(
                status_code=400,
                detail="Familien har registrerede udgifter og kan ikke slettes. Slet udgifterne først.",
            )
    db.delete(fam)
    db.commit()


@router.delete(
    "/{family_id}/invites/{invite_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
def delete_invite(family_id: int, invite_id: int, db: DbDep) -> None:
    invite = db.get(InviteToken, invite_id)
    if invite is None or invite.family_id != family_id:
        return
    if invite.used_at is not None:
        raise HTTPException(status_code=400, detail="Invitation er allerede brugt")
    db.delete(invite)
    db.commit()
