from fastapi import APIRouter, HTTPException, UploadFile, status

from app.core.deps import CurrentUser, DbDep
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.schemas.auth import UserOut
from app.schemas.user import ChildUpdate
from app.services.uploads import save_profile_picture

router = APIRouter(prefix="/children", tags=["children"])


def _load_child_for_caller(child_id: int, db, caller: User) -> User:
    child = db.get(User, child_id)
    if child is None or child.role != UserRole.CHILD:
        raise HTTPException(status_code=404, detail="Barn findes ikke")
    if caller.role == UserRole.ADMIN:
        return child
    if caller.role == UserRole.PARENT and child.family_id == caller.family_id:
        return child
    raise HTTPException(status_code=403, detail="Adgang nægtet")


@router.get("/{child_id}", response_model=UserOut)
def get_child(child_id: int, db: DbDep, user: CurrentUser) -> UserOut:
    return UserOut.model_validate(_load_child_for_caller(child_id, db, user))


@router.patch("/{child_id}", response_model=UserOut)
def update_child(
    child_id: int, payload: ChildUpdate, db: DbDep, user: CurrentUser
) -> UserOut:
    child = _load_child_for_caller(child_id, db, user)
    if payload.name is not None:
        child.name = payload.name
    if payload.birthdate is not None:
        child.birthdate = payload.birthdate
    if payload.email is not None:
        if db.query(User).filter(User.email == payload.email.lower(), User.id != child.id).first():
            raise HTTPException(status_code=400, detail="Email er allerede registreret")
        child.email = payload.email.lower()
    if payload.password is not None:
        child.password_hash = hash_password(payload.password)
    db.commit()
    db.refresh(child)
    return UserOut.model_validate(child)


@router.post("/{child_id}/profile-picture", response_model=UserOut)
def upload_child_picture(
    child_id: int, file: UploadFile, db: DbDep, user: CurrentUser
) -> UserOut:
    child = _load_child_for_caller(child_id, db, user)
    child.profile_picture_url = save_profile_picture(file, subdir=f"children/{child.id}")
    db.commit()
    db.refresh(child)
    return UserOut.model_validate(child)


@router.delete("/{child_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_child(child_id: int, db: DbDep, user: CurrentUser):
    child = _load_child_for_caller(child_id, db, user)
    db.delete(child)
    db.commit()
