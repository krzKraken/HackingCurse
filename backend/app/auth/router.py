from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.rate_limit import clear_failed_attempts, is_locked_out, register_failed_attempt
from app.auth.schemas import LoginRequest, LoginResponse, MfaVerifyRequest, UserOut
from app.auth.security import verify_password
from app.auth.sessions import create_session, delete_session, get_session, upgrade_session
from app.auth.totp import verify_totp_code
from app.config import settings
from app.db import get_db
from app.models.user import User

router = APIRouter()


def _set_session_cookie(response: Response, session_id: str, max_age: int) -> None:
    response.set_cookie(
        settings.cookie_name,
        session_id,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=max_age,
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> LoginResponse:
    if is_locked_out(payload.username):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many failed attempts")

    user = db.query(User).filter(User.username == payload.username).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        register_failed_attempt(payload.username)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    clear_failed_attempts(payload.username)
    session_id = create_session(
        str(user.id), mfa_verified=False, ttl_seconds=settings.session_ttl_pending_seconds
    )
    _set_session_cookie(response, session_id, settings.session_ttl_pending_seconds)
    return LoginResponse(mfa_required=True)


@router.post("/mfa/verify", response_model=UserOut)
def mfa_verify(
    payload: MfaVerifyRequest,
    response: Response,
    db: Session = Depends(get_db),
    session_id: str | None = Cookie(default=None, alias=settings.cookie_name),
) -> UserOut:
    if session_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No pending session")

    session = get_session(session_id)
    if session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired")

    user = db.get(User, session["user_id"])
    if user is None or not verify_totp_code(user.totp_secret, payload.code):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid MFA code")

    upgrade_session(session_id, settings.session_ttl_authenticated_seconds)
    _set_session_cookie(response, session_id, settings.session_ttl_authenticated_seconds)
    return UserOut(id=str(user.id), username=user.username)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut(id=str(user.id), username=user.username)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    session_id: str | None = Cookie(default=None, alias=settings.cookie_name),
) -> None:
    if session_id:
        delete_session(session_id)
    response.delete_cookie(settings.cookie_name)
