from fastapi import APIRouter, HTTPException, UploadFile, status

from app.core.deps import CurrentUser, DbDep
from app.core.security import hash_password, verify_password
from app.models.expense import Expense
from app.models.user import User, UserRole
from app.schemas.auth import UserOut
from app.schemas.user import (
    AdminUserUpdate,
    ChangePasswordRequest,
    ChildCreate,
    RoleUpdate,
    UserUpdate,
)
from app.services.uploads import save_profile_picture

router = APIRouter(tags=["users"])


@router.get("/users", response_model=list[UserOut])
def list_users(
    db: DbDep,
    user: CurrentUser,
    role: UserRole | None = None,
    family_id: int | None = None,
) -> list[UserOut]:
    """List users.

    - Admins see everyone.
    - Non-admins see only users in their own family (used to populate event-host
      and chor-assignment dropdowns without leaking other families).
    """
    q = db.query(User)
    if user.role != UserRole.ADMIN:
        if user.family_id is None:
            return [UserOut.model_validate(user)]
        q = q.filter(User.family_id == user.family_id)
    if role is not None:
        q = q.filter(User.role == role)
    if family_id is not None:
        q = q.filter(User.family_id == family_id)
    rows = q.order_by(User.role.asc(), User.name.asc()).all()
    return [UserOut.model_validate(u) for u in rows]


@router.patch("/me", response_model=UserOut)
def update_me(payload: UserUpdate, db: DbDep, user: CurrentUser) -> UserOut:
    if payload.name is not None:
        user.name = payload.name
    if payload.birthdate is not None:
        user.birthdate = payload.birthdate
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.post("/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(payload: ChangePasswordRequest, db: DbDep, user: CurrentUser):
    if not user.password_hash or not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Forkert nuværende adgangskode")
    user.password_hash = hash_password(payload.new_password)
    db.commit()


@router.post("/me/profile-picture", response_model=UserOut)
def upload_profile_picture(file: UploadFile, db: DbDep, user: CurrentUser) -> UserOut:
    user.profile_picture_url = save_profile_picture(file, subdir=f"users/{user.id}")
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.get("/me/children", response_model=list[UserOut])
def list_my_children(db: DbDep, user: CurrentUser) -> list[UserOut]:
    rows = db.query(User).filter(User.parent_user_id == user.id).all()
    return [UserOut.model_validate(c) for c in rows]


@router.post(
    "/me/children",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
)
def create_my_child(payload: ChildCreate, db: DbDep, user: CurrentUser) -> UserOut:
    return _create_child_for(payload, db, parent=user)


@router.post(
    "/users/{parent_id}/children",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
)
def create_child_for_parent(
    parent_id: int, payload: ChildCreate, db: DbDep, user: CurrentUser
) -> UserOut:
    parent = db.get(User, parent_id)
    if parent is None or parent.role == UserRole.CHILD:
        raise HTTPException(status_code=404, detail="Forælder findes ikke")
    if user.role != UserRole.ADMIN and user.id != parent.id:
        raise HTTPException(status_code=403, detail="Adgang nægtet")
    return _create_child_for(payload, db, parent=parent)


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int, payload: AdminUserUpdate, db: DbDep, user: CurrentUser
) -> UserOut:
    """Edit another user's profile.

    Permissions:
    - Admin can change any field, including password (used to bootstrap or
      recover access to a parent).
    - A parent in the same family unit can change name, birthdate and email
      of any other non-child user in that family. Password changes are
      explicitly NOT allowed for spouses (they go through self-change with
      the current password, or admin reset).
    - Otherwise: 403.
    """
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Bruger findes ikke")

    is_admin = user.role == UserRole.ADMIN
    is_self = user.id == target.id
    is_same_family_adult = (
        user.role == UserRole.PARENT
        and target.role != UserRole.CHILD
        and user.family_id is not None
        and user.family_id == target.family_id
    )
    if not (is_admin or is_self or is_same_family_adult):
        raise HTTPException(status_code=403, detail="Adgang nægtet")

    if payload.password is not None and not (is_admin or is_self):
        raise HTTPException(
            status_code=403,
            detail="Kun admin eller brugeren selv kan ændre adgangskoden",
        )

    if payload.name is not None:
        target.name = payload.name
    if payload.birthdate is not None:
        target.birthdate = payload.birthdate
    if payload.email is not None:
        new_email = payload.email.lower()
        if (
            db.query(User)
            .filter(User.email == new_email, User.id != target.id)
            .first()
        ):
            raise HTTPException(status_code=400, detail="Email er allerede registreret")
        target.email = new_email
    if payload.password is not None:
        target.password_hash = hash_password(payload.password)
    db.commit()
    db.refresh(target)
    return UserOut.model_validate(target)


@router.patch("/users/{user_id}/role", response_model=UserOut)
def update_user_role(
    user_id: int, payload: RoleUpdate, db: DbDep, user: CurrentUser
) -> UserOut:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Kun admin kan ændre roller")
    target = db.get(User, user_id)
    if target is None or target.role == UserRole.CHILD:
        raise HTTPException(status_code=404, detail="Bruger findes ikke")
    new_role = UserRole(payload.role)
    if target.id == user.id and new_role != UserRole.ADMIN:
        admins_left = (
            db.query(User).filter(User.role == UserRole.ADMIN, User.id != user.id).count()
        )
        if admins_left == 0:
            raise HTTPException(
                status_code=400, detail="Du kan ikke fjerne din egen admin-rolle som sidste admin"
            )
    target.role = new_role
    db.commit()
    db.refresh(target)
    return UserOut.model_validate(target)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: DbDep, user: CurrentUser) -> None:
    """Admin-only deletion of any user (parent, admin, or child).

    Cascades children via the ORM `parent` relationship; DB-level FK rules handle
    attendances, activity attendees, password reset tokens, and host/assignee
    references. Refuses if the user has expenses (RESTRICT) or if removing them
    would leave zero admins.
    """
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Kun admin kan slette brugere")
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Bruger findes ikke")
    if target.id == user.id:
        raise HTTPException(status_code=400, detail="Du kan ikke slette dig selv")
    if target.role == UserRole.ADMIN:
        admins_left = (
            db.query(User).filter(User.role == UserRole.ADMIN, User.id != target.id).count()
        )
        if admins_left == 0:
            raise HTTPException(
                status_code=400, detail="Mindst én admin skal være tilbage"
            )
    if db.query(Expense).filter(Expense.paid_by_user_id == target.id).first():
        raise HTTPException(
            status_code=400,
            detail="Brugeren har registrerede udgifter og kan ikke slettes. Slet udgifterne først.",
        )
    db.delete(target)
    db.commit()


def _create_child_for(payload: ChildCreate, db, *, parent: User) -> UserOut:
    if payload.email and db.query(User).filter(User.email == payload.email.lower()).first():
        raise HTTPException(status_code=400, detail="Email er allerede registreret")
    child = User(
        family_id=parent.family_id,
        parent_user_id=parent.id,
        name=payload.name,
        role=UserRole.CHILD,
        birthdate=payload.birthdate,
        email=payload.email.lower() if payload.email else None,
        password_hash=hash_password(payload.password) if payload.password else None,
    )
    db.add(child)
    db.commit()
    db.refresh(child)
    return UserOut.model_validate(child)
