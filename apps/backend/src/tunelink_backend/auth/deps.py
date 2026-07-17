from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tunelink_backend.auth.tokens import parse_access_token
from tunelink_backend.config import get_settings
from tunelink_backend.db import get_db
from tunelink_backend.models import User


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        user_id: UUID = parse_access_token(token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def get_current_master(user: User = Depends(get_current_user)) -> User:
    if not user.is_master:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Master account required")
    return user
