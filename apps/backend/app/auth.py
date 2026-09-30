"""Invite-only authentication and request ownership context.

Session and invitation bearer values are random, one-time secrets. Only their
SHA-256 digests are stored. Passwords use cryptography's memory-hard Scrypt.
"""
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select

from app.config import settings
from app.database import db
from app.models import AuthAttempt, Invitation, Session, UsageLedger, User
from app.passwords import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["authentication"])
current_user_id: ContextVar[str] = ContextVar("current_user_id", default="legacy")
current_is_admin: ContextVar[bool] = ContextVar("current_is_admin", default=False)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _check_rate_limit(request: Request, email: str, action: str, *, limit: int = 8) -> None:
    """Persist attempts so restarts and multiple workers do not reset limits."""
    subject = _digest(f"{request.client.host if request.client else 'unknown'}|{email.lower()}")
    cutoff = (_now() - timedelta(minutes=15)).isoformat()
    with db._sync_write_session() as session:
        count = session.scalar(select(func.count()).select_from(AuthAttempt).where(
            AuthAttempt.subject_hash == subject, AuthAttempt.action == action,
            AuthAttempt.created_at >= cutoff)) or 0
        if count >= limit:
            raise HTTPException(429, "Too many attempts; try again later")
        session.add(AuthAttempt(attempt_id=str(uuid4()), subject_hash=subject, action=action))
        session.commit()


class LoginBody(BaseModel):
    email: str
    password: str = Field(min_length=12, max_length=256)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or len(value) > 254:
            raise ValueError("valid email required")
        return value


class AcceptBody(LoginBody):
    invitation_token: str = Field(min_length=32, max_length=256)


class InviteBody(BaseModel):
    email: str
    expires_hours: int = Field(default=72, ge=1, le=168)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        return LoginBody.valid_email(value)


def resolve_session(raw: str | None) -> tuple[User, Session] | None:
    """Resolve an unexpired cookie without ever persisting its bearer value."""
    if not raw:
        return None
    db._ensure_initialized()
    with db._sync() as session:
        record = session.get(Session, _digest(raw))
        if record is None or record.expires_at <= _now().isoformat():
            return None
        user = session.get(User, record.user_id)
        return (user, record) if user else None


def _set_session(response: Response, user_id: str) -> str:
    raw, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
    expires = _now() + timedelta(hours=settings.session_hours)
    with db._sync_write_session() as session:
        session.add(Session(token_hash=_digest(raw), user_id=user_id, csrf_token=csrf,
                            expires_at=expires.isoformat()))
        session.commit()
    response.set_cookie("shpe_session", raw, httponly=True, secure=settings.cookie_secure,
                        samesite="strict", max_age=settings.session_hours * 3600, path="/")
    return csrf


@router.post("/login")
def login(body: LoginBody, request: Request, response: Response) -> dict[str, Any]:
    _check_rate_limit(request, body.email, "login")
    with db._sync() as session:
        user = session.scalar(select(User).where(func.lower(User.email) == body.email.lower()))
    valid = bool(user) and verify_password(user.password_hash, body.password)
    if not valid or user is None:
        raise HTTPException(401, "Invalid email or password")
    return {"csrf_token": _set_session(response, user.user_id), "email": user.email,
            "is_admin": user.is_admin}


@router.post("/accept-invitation", status_code=201)
def accept_invitation(body: AcceptBody, request: Request, response: Response) -> dict[str, Any]:
    _check_rate_limit(request, body.email, "invitation")
    now = _now().isoformat()
    with db._sync_write_session() as session:
        invite = session.get(Invitation, _digest(body.invitation_token))
        if invite is None or invite.used_at or invite.expires_at <= now or invite.email.lower() != body.email.lower():
            raise HTTPException(400, "Invitation is invalid or expired")
        if session.scalar(select(User).where(func.lower(User.email) == body.email.lower())):
            raise HTTPException(409, "Account already exists")
        user = User(user_id=str(uuid4()), email=body.email.lower(),
                    password_hash=hash_password(body.password), is_admin=False)
        invite.used_at = now
        session.add(user)
        session.commit()
    return {"csrf_token": _set_session(response, user.user_id), "email": user.email,
            "is_admin": False}


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response) -> None:
    raw = request.cookies.get("shpe_session")
    if raw:
        with db._sync_write_session() as session:
            record = session.get(Session, _digest(raw))
            if record:
                session.delete(record)
            session.commit()
    response.delete_cookie("shpe_session", path="/")


@router.get("/me")
def me(request: Request) -> dict[str, Any]:
    return {"email": request.state.user.email, "is_admin": request.state.user.is_admin,
            "csrf_token": request.state.session.csrf_token}


@router.post("/invitations", status_code=201)
def invite(body: InviteBody, request: Request) -> dict[str, str]:
    if not request.state.user.is_admin:
        raise HTTPException(403, "Administrator access required")
    raw = secrets.token_urlsafe(48)
    with db._sync_write_session() as session:
        session.add(Invitation(token_hash=_digest(raw), email=body.email.lower(),
                    expires_at=(_now() + timedelta(hours=body.expires_hours)).isoformat(),
                    created_by=request.state.user.user_id))
        session.commit()
    # Manual delivery only: no email integration and token is shown exactly once.
    return {"invitation_token": raw, "email": body.email.lower()}


@router.get("/admin/usage")
def usage(request: Request) -> dict[str, Any]:
    if not request.state.user.is_admin:
        raise HTTPException(403, "Administrator access required")
    with db._sync() as session:
        rows = session.execute(select(UsageLedger.owner_id, func.sum(
            func.coalesce(UsageLedger.actual_cents, UsageLedger.reserved_cents))).group_by(
                UsageLedger.owner_id)).all()
    return {"allowance_cents": settings.ai_allowance_cents,
            "note": "App ledger only; it does not read Claude Console balance or other applications.",
            "members": [{"owner_id": owner, "accounted_cents": cents or 0} for owner, cents in rows]}
