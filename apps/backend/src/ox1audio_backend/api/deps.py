from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ox1audio_backend.auth.deps import get_current_master, get_current_user
from ox1audio_backend.db import get_db
from ox1audio_backend.models import User

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentMaster = Annotated[User, Depends(get_current_master)]
