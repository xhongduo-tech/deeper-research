"""
Unified authentication resolver.

Supports two credentials side by side:
  1. Session JWT issued by /api/v1/auth/login   (header: Authorization: Bearer <jwt>)
  2. User-issued API key                         (header: Authorization: Bearer dr_<...>)
                                                 (or      X-API-Key: dr_<...>)

Both resolve to a `User`. For API key auth we additionally expose the
originating `ApiKey` row so usage counters and rate limits can be updated.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.api_key import ApiKey
from app.models.user import User, UserRole


API_KEY_PREFIX = "dr_"


@dataclass
class AuthContext:
    user: User
    api_key: Optional[ApiKey] = None          # None when authenticated via JWT
    auth_method: str = "session"              # "session" | "api_key"


def _hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _extract_bearer(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return None


async def _resolve_api_key(
    raw_key: str, db: AsyncSession
) -> Optional[AuthContext]:
    hashed = _hash_api_key(raw_key)
    result = await db.execute(select(ApiKey).where(ApiKey.hashed_key == hashed))
    api_key = result.scalar_one_or_none()
    if not api_key or api_key.status != "active":
        return None
    if api_key.expires_at and api_key.expires_at < datetime.utcnow():
        return None

    user_result = await db.execute(select(User).where(User.id == api_key.user_id))
    user = user_result.scalar_one_or_none()
    if not user or not user.is_active:
        return None

    api_key.total_requests = (api_key.total_requests or 0) + 1
    api_key.last_used_at = datetime.utcnow()

    return AuthContext(user=user, api_key=api_key, auth_method="api_key")


async def _resolve_jwt(
    token: str, db: AsyncSession
) -> Optional[AuthContext]:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        username: Optional[str] = payload.get("sub")
        if not username:
            return None
    except JWTError:
        return None

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        return None
    return AuthContext(user=user, api_key=None, auth_method="session")


async def get_auth_context(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    """Resolve the caller — either JWT session user or API key user.

    Unauthorized callers get a 401.
    """
    # 1) Explicit X-API-Key header wins
    candidate = x_api_key
    if not candidate:
        candidate = _extract_bearer(authorization)

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Sniff: API keys start with "dr_", everything else treat as JWT.
    if candidate.startswith(API_KEY_PREFIX):
        ctx = await _resolve_api_key(candidate, db)
    else:
        ctx = await _resolve_jwt(candidate, db)

    if ctx is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return ctx


async def require_user(ctx: AuthContext = Depends(get_auth_context)) -> User:
    return ctx.user


async def require_admin(ctx: AuthContext = Depends(get_auth_context)) -> User:
    if ctx.user.role != UserRole.admin.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required"
        )
    return ctx.user
