from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tunelink_backend.auth.deps import get_current_master, get_current_user
from tunelink_backend.auth.passwords import hash_password, verify_password
from tunelink_backend.auth.tokens import create_access_token
from tunelink_backend.config import get_settings
from tunelink_backend.db import get_db
from tunelink_backend.models import User, UserRole

router = APIRouter()


class AuthCredentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    id: UUID
    email: EmailStr
    role: UserRole

    model_config = {"from_attributes": True}


class AuthStatus(BaseModel):
    registration_open: bool


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


@router.get("/status", response_model=AuthStatus, operation_id="authStatus")
async def auth_status(db: AsyncSession = Depends(get_db)) -> AuthStatus:
    return AuthStatus(registration_open=await _user_count(db) == 0)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED, operation_id="register")
async def register(
    body: AuthCredentials,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> User:
    if await _user_count(db) > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is closed. Ask the master account to create a user.",
        )

    email = body.email.lower()
    user = User(
        email=email,
        password_hash=hash_password(body.password),
        role=UserRole.MASTER,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    _set_session_cookie(response, user.id)
    return user


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED, operation_id="createUser")
async def create_user(
    body: AuthCredentials,
    db: AsyncSession = Depends(get_db),
    _master: User = Depends(get_current_master),
) -> User:
    email = body.email.lower()
    existing = await db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=email,
        password_hash=hash_password(body.password),
        role=UserRole.USER,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=UserOut, operation_id="login")
async def login(
    body: AuthCredentials,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> User:
    email = body.email.lower()
    user = await db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    _set_session_cookie(response, user.id)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, operation_id="logout")
async def logout(response: Response) -> None:
    _clear_session_cookie(response)


@router.get("/me", response_model=UserOut, operation_id="me")
async def me(user: User = Depends(get_current_user)) -> User:
    return user
