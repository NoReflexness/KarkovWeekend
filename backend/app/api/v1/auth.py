from datetime import timedelta

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.core.config import Settings, get_settings
from app.core.deps import CurrentUser, DbDep
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    is_past,
    now_utc,
    random_token,
    verify_password,
)
from app.models.invite_token import InviteToken
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User, UserRole
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    ResetPasswordRequest,
    UserOut,
)
from app.services.email import get_email_sender

router = APIRouter(prefix="/auth", tags=["auth"])


def _cookie_secure(request: Request, settings: Settings) -> bool:
    """Honor COOKIE_SECURE only when the browser connection is actually HTTPS.

    With COOKIE_SECURE=true, plain HTTP (e.g. opening the site by LAN IP on :80)
    must not emit Secure cookies — browsers ignore them, so login looks broken.
    Behind Caddy, use X-Forwarded-Proto from the reverse proxy.
    """
    if not settings.cookie_secure:
        return False
    forwarded = request.headers.get("x-forwarded-proto", "").partition(",")[0].strip().lower()
    if forwarded == "https":
        return True
    if forwarded == "http":
        return False
    return request.url.scheme == "https"


def _set_auth_cookies(response: Response, request: Request, user_id: int) -> None:
    settings = get_settings()
    access = create_access_token(user_id)
    refresh = create_refresh_token(user_id)
    secure = _cookie_secure(request, settings)
    response.set_cookie(
        "access_token",
        access,
        httponly=True,
        secure=secure,
        samesite=settings.cookie_samesite,  # type: ignore[arg-type]
        max_age=settings.access_token_ttl_minutes * 60,
        path="/",
    )
    response.set_cookie(
        "refresh_token",
        refresh,
        httponly=True,
        secure=secure,
        samesite=settings.cookie_samesite,  # type: ignore[arg-type]
        max_age=settings.refresh_token_ttl_minutes * 60,
        path="/api/v1/auth",
    )


def _clear_auth_cookies(response: Response, request: Request) -> None:
    settings = get_settings()
    secure = _cookie_secure(request, settings)
    response.delete_cookie(
        "access_token",
        path="/",
        secure=secure,
        httponly=True,
        samesite=settings.cookie_samesite,  # type: ignore[arg-type]
    )
    response.delete_cookie(
        "refresh_token",
        path="/api/v1/auth",
        secure=secure,
        httponly=True,
        samesite=settings.cookie_samesite,  # type: ignore[arg-type]
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, response: Response, request: Request, db: DbDep) -> LoginResponse:
    user = db.query(User).filter(User.email == payload.email.lower()).one_or_none()
    if user is None or not user.password_hash or not verify_password(
        payload.password, user.password_hash
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Forkert email eller adgangskode")
    user.last_login_at = now_utc()
    db.commit()
    _set_auth_cookies(response, request, user.id)
    return LoginResponse(user=UserOut.model_validate(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, request: Request) -> Response:
    _clear_auth_cookies(response, request)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response, request: Request, db: DbDep) -> UserOut:
    invite = db.query(InviteToken).filter(InviteToken.token == payload.token).one_or_none()
    if invite is None:
        raise HTTPException(status_code=400, detail="Ugyldigt invitationstoken")
    if invite.used_at is not None:
        raise HTTPException(status_code=400, detail="Invitationstoken allerede brugt")
    if is_past(invite.expires_at):
        raise HTTPException(status_code=400, detail="Invitationstoken udløbet")

    if db.query(User).filter(User.email == invite.email.lower()).one_or_none():
        raise HTTPException(status_code=400, detail="Email er allerede registreret")

    user = User(
        family_id=invite.family_id,
        email=invite.email.lower(),
        password_hash=hash_password(payload.password),
        name=payload.name,
        role=UserRole.PARENT,
        birthdate=payload.birthdate,
    )
    db.add(user)
    invite.used_at = now_utc()
    db.commit()
    db.refresh(user)

    _set_auth_cookies(response, request, user.id)
    return UserOut.model_validate(user)


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
def forgot_password(payload: ForgotPasswordRequest, db: DbDep) -> Response:
    user = db.query(User).filter(User.email == payload.email.lower()).one_or_none()
    # Always 204 to avoid email enumeration.
    if user is not None:
        token = random_token()
        prt = PasswordResetToken(
            token=token,
            user_id=user.id,
            expires_at=now_utc() + timedelta(hours=2),
        )
        db.add(prt)
        settings = get_settings()
        body = (
            "Hej {name},\n\nKlik for at nulstille din adgangskode:\n"
            "{base}/nulstil-adgangskode?token={token}\n\n"
            "Linket udløber om 2 timer."
        ).format(name=user.name, base=settings.public_base_url, token=token)
        get_email_sender().send(
            db, to=user.email or "", subject="Nulstil din adgangskode", body=body
        )
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(payload: ResetPasswordRequest, db: DbDep) -> Response:
    prt = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token == payload.token)
        .one_or_none()
    )
    if prt is None or prt.used_at is not None or is_past(prt.expires_at):
        raise HTTPException(status_code=400, detail="Ugyldigt eller udløbet token")
    user = db.get(User, prt.user_id)
    if user is None:
        raise HTTPException(status_code=400, detail="Bruger findes ikke")
    user.password_hash = hash_password(payload.new_password)
    prt.used_at = now_utc()
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
