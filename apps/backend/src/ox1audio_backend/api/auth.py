from __future__ import annotations

from io import BytesIO
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ox1audio_backend import storage
from ox1audio_backend.api.deps import CurrentMaster, CurrentUser, DbSession
from ox1audio_backend.auth.passwords import (
    hash_password,
    validate_password_strength,
    verify_password,
)
from ox1audio_backend.auth.tokens import create_access_token
from ox1audio_backend.config import get_settings
from ox1audio_backend.models import User, UserRole
from ox1audio_backend.shared_constants import (
    ALLOWED_IMAGE_MIME_TYPES,
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
)

router = APIRouter()

_AVATAR_TYPES = set(ALLOWED_IMAGE_MIME_TYPES)
_MAX_AVATAR_BYTES = 5 * 1024 * 1024


class AuthCredentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)


class RegisterBody(AuthCredentials):
    display_name: str | None = Field(default=None, max_length=120)


class UserOut(BaseModel):
    id: UUID
    email: EmailStr
    role: UserRole
    display_name: str | None = None
    must_change_password: bool = False
    has_avatar: bool = False

    model_config = {"from_attributes": True}


class AuthStatus(BaseModel):
    registration_open: bool


class UpdateProfileBody(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)


class ChangePasswordBody(BaseModel):
    current_password: str | None = Field(default=None, max_length=PASSWORD_MAX_LENGTH)
    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)


class ChangeEmailBody(BaseModel):
    current_password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)
    new_email: EmailStr


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        role=UserRole(user.role),
        display_name=user.display_name,
        must_change_password=bool(user.must_change_password),
        has_avatar=user.avatar_object_key is not None,
    )


def _set_session_cookie(response: Response, user_id: UUID) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.session_cookie,
        value=create_access_token(user_id),
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=settings.session_max_age_seconds,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(key=settings.session_cookie, path="/")


async def _user_count(db: AsyncSession) -> int:
    return int(await db.scalar(select(func.count()).select_from(User)) or 0)


def _clean_display_name(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split()).strip()
    return cleaned[:120] or None


@router.get("/status", response_model=AuthStatus, operation_id="authStatus")
async def auth_status(db: DbSession) -> AuthStatus:
    return AuthStatus(registration_open=await _user_count(db) == 0)


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    operation_id="register",
)
async def register(
    body: RegisterBody,
    response: Response,
    db: DbSession,
) -> UserOut:
    if await _user_count(db) > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is closed. Ask the master account to create a user.",
        )

    email = body.email.lower()
    strength_error = validate_password_strength(body.password)
    if strength_error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=strength_error)
    user = User(
        email=email,
        password_hash=hash_password(body.password),
        role=UserRole.MASTER,
        display_name=_clean_display_name(body.display_name),
        must_change_password=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    _set_session_cookie(response, user.id)
    return _user_out(user)


@router.post(
    "/users",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    operation_id="createUser",
)
async def create_user(
    body: AuthCredentials,
    db: DbSession,
    _master: CurrentMaster,
) -> UserOut:
    email = body.email.lower()
    existing = await db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=email,
        password_hash=hash_password(body.password),
        role=UserRole.USER,
        must_change_password=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return _user_out(user)


@router.post("/login", response_model=UserOut, operation_id="login")
async def login(
    body: AuthCredentials,
    response: Response,
    db: DbSession,
) -> UserOut:
    email = body.email.lower()
    user = await db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    _set_session_cookie(response, user.id)
    return _user_out(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, operation_id="logout")
async def logout(response: Response) -> None:
    _clear_session_cookie(response)


@router.get("/me", response_model=UserOut, operation_id="me")
async def me(user: CurrentUser) -> UserOut:
    return _user_out(user)


@router.patch("/me", response_model=UserOut, operation_id="updateMe")
async def update_me(
    body: UpdateProfileBody,
    db: DbSession,
    user: CurrentUser,
) -> UserOut:
    cleaned = _clean_display_name(body.display_name)
    if not cleaned:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Display name required")
    user.display_name = cleaned
    await db.commit()
    await db.refresh(user)
    return _user_out(user)


@router.post("/me/password", response_model=UserOut, operation_id="changePassword")
async def change_password(
    body: ChangePasswordBody,
    db: DbSession,
    user: CurrentUser,
) -> UserOut:
    if user.must_change_password:
        # First-login forced change: temp password already proved via login.
        pass
    else:
        if not body.current_password or not verify_password(
            body.current_password, user.password_hash
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )
        if body.current_password == body.new_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be different",
            )
    strength_error = validate_password_strength(body.new_password)
    if strength_error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=strength_error)
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    await db.commit()
    await db.refresh(user)
    return _user_out(user)


@router.post("/me/email", response_model=UserOut, operation_id="changeEmail")
async def change_email(
    body: ChangeEmailBody,
    db: DbSession,
    user: CurrentUser,
) -> UserOut:
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    new_email = body.new_email.lower()
    if new_email == user.email:
        return _user_out(user)
    existing = await db.scalar(select(User).where(User.email == new_email))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user.email = new_email
    await db.commit()
    await db.refresh(user)
    return _user_out(user)


@router.put("/me/avatar", response_model=UserOut, operation_id="updateMyAvatar")
async def update_my_avatar(
    db: DbSession,
    user: CurrentUser,
    file: UploadFile = File(...),
) -> UserOut:
    content_type = (file.content_type or "").lower()
    if content_type == "image/jpg":
        content_type = "image/jpeg"
    if content_type not in _AVATAR_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Avatar must be JPEG, PNG, or WebP")
    data = await file.read()
    if not data or len(data) > _MAX_AVATAR_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid avatar file")
    ext = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[content_type]
    object_key = f"users/{user.id}/avatar.{ext}"
    if user.avatar_object_key and user.avatar_object_key != object_key:
        try:
            storage.remove_object(user.avatar_object_key)
        except Exception:
            pass
    storage.put_object(object_key, BytesIO(data), len(data), content_type)
    user.avatar_object_key = object_key
    await db.commit()
    await db.refresh(user)
    return _user_out(user)


@router.get("/me/avatar", operation_id="getMyAvatar")
async def get_my_avatar(user: CurrentUser) -> Response:
    if not user.avatar_object_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No avatar")
    try:
        data, content_type = storage.get_object_bytes(user.avatar_object_key)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Avatar missing") from exc
    return Response(content=data, media_type=content_type)
