from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session

from app.api.auth_deps import get_linked_parent_for_account
from app.api.deps import get_db_session
from app.core.config import Settings, get_settings
from app.domain.models import utcnow
from app.services.auth_codes import request_magic_code, verify_magic_code
from app.services.auth_security import mask_phone, normalize_email, normalize_phone
from app.services.parent_sessions import (
    auth_session_payload,
    clear_parent_session,
    create_parent_session,
    get_session_account,
    touch_parent_session,
)
from app.services.email_sender import get_email_sender

router = APIRouter(prefix="/api/auth", tags=["auth"])


class MagicCodeRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    alpha_session_id: str = Field(default="", max_length=120)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


class MagicCodeVerify(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    code: str = Field(min_length=6, max_length=6)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


class PhoneBindRequest(BaseModel):
    phone: str = Field(min_length=3, max_length=32)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        return normalize_phone(value)


@router.post("/magic-codes/request")
def request_parent_magic_code(
    payload: MagicCodeRequest,
    fastapi_request: Request,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
):
    request_ip = fastapi_request.client.host if fastapi_request.client else None
    sender = get_email_sender(settings)
    return request_magic_code(
        session,
        settings,
        payload.email,
        payload.alpha_session_id,
        request_ip,
        sender,
    )


@router.post("/magic-codes/verify")
def verify_parent_magic_code(
    payload: MagicCodeVerify,
    response: Response,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
):
    account = verify_magic_code(session, settings, payload.email, payload.code)
    create_parent_session(
        db=session,
        settings=settings,
        account=account,
        response=response,
    )
    session.commit()
    session.refresh(account)

    parent = get_linked_parent_for_account(db=session, account_id=account.id)
    return auth_session_payload(account=account, parent_id=parent.id if parent else None)


@router.get("/session")
def get_parent_session(
    request: Request,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
):
    session_result = get_session_account(
        db=session,
        settings=settings,
        token=request.cookies.get(settings.auth_session_cookie_name),
    )
    if session_result is None:
        return {"authenticated": False}

    account, parent_session = session_result
    if touch_parent_session(db=session, settings=settings, parent_session=parent_session):
        session.commit()

    parent = get_linked_parent_for_account(db=session, account_id=account.id)
    return auth_session_payload(account=account, parent_id=parent.id if parent else None)


@router.post("/logout")
def logout_parent_session(
    request: Request,
    response: Response,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
):
    session_result = get_session_account(
        db=session,
        settings=settings,
        token=request.cookies.get(settings.auth_session_cookie_name),
    )
    if session_result is not None:
        _, parent_session = session_result
        parent_session.revoked_at = utcnow()
        session.add(parent_session)
    clear_parent_session(response=response, settings=settings)
    session.commit()
    return {"ok": True}


@router.patch("/account/phone")
def bind_parent_account_phone(
    payload: PhoneBindRequest,
    request: Request,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
):
    session_result = get_session_account(
        db=session,
        settings=settings,
        token=request.cookies.get(settings.auth_session_cookie_name),
    )
    if session_result is None:
        raise HTTPException(status_code=401, detail="Authentication required.")

    account, _ = session_result
    account.phone_e164 = payload.phone
    account.phone_bound_at = utcnow()
    account.phone_verified_at = None
    session.add(account)
    session.commit()
    session.refresh(account)
    return {"phone_masked": mask_phone(account.phone_e164), "phone_bound": True}
