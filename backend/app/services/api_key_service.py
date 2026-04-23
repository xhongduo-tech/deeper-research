"""
ApiKey generation & management.

Policy per DESIGN.md §5:
  - Any logged-in user can create keys on their own (auto-approved).
  - Admin can list all keys, suspend, and adjust quotas.
  - We never store the raw key; only SHA-256.
  - The raw key is returned exactly once, at creation time.
"""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import ApiKey

RAW_KEY_PREFIX = "dr_"


@dataclass
class CreatedKey:
    api_key: ApiKey
    raw_key: str


def _generate_raw_key() -> str:
    # 32 bytes url-safe → ~43 chars after base64
    return RAW_KEY_PREFIX + secrets.token_urlsafe(32)


def _hash_raw(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def serialize_api_key(k: ApiKey) -> Dict[str, Any]:
    return {
        "id": k.id,
        "user_id": k.user_id,
        "name": k.name,
        "prefix": k.prefix,
        "masked_key": f"{k.prefix}{'•' * 12}",
        "status": k.status,
        "daily_request_limit": k.daily_request_limit,
        "monthly_token_limit": k.monthly_token_limit,
        "total_requests": k.total_requests,
        "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
        "created_at": k.created_at.isoformat() if k.created_at else None,
        "expires_at": k.expires_at.isoformat() if k.expires_at else None,
    }


class ApiKeyService:
    @staticmethod
    async def create_for_user(
        db: AsyncSession,
        *,
        user_id: int,
        name: str,
        daily_request_limit: Optional[int] = None,
        monthly_token_limit: Optional[int] = None,
        expires_at: Optional[datetime] = None,
    ) -> CreatedKey:
        raw = _generate_raw_key()
        hashed = _hash_raw(raw)
        prefix = raw[: len(RAW_KEY_PREFIX) + 6]  # dr_XXXXXX

        k = ApiKey(
            user_id=user_id,
            name=name.strip() or "未命名密钥",
            prefix=prefix,
            hashed_key=hashed,
            raw_key=raw,
            status="active",
            daily_request_limit=daily_request_limit,
            monthly_token_limit=monthly_token_limit,
            expires_at=expires_at,
        )
        db.add(k)
        await db.flush()
        await db.refresh(k)
        return CreatedKey(api_key=k, raw_key=raw)

    @staticmethod
    async def list_for_user(db: AsyncSession, user_id: int) -> List[ApiKey]:
        stmt = (
            select(ApiKey)
            .where(ApiKey.user_id == user_id)
            .order_by(ApiKey.created_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def list_all(db: AsyncSession) -> List[ApiKey]:
        stmt = select(ApiKey).order_by(ApiKey.created_at.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get(db: AsyncSession, key_id: int) -> Optional[ApiKey]:
        result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def set_status(db: AsyncSession, api_key: ApiKey, status: str) -> ApiKey:
        if status not in ("active", "suspended", "revoked"):
            raise ValueError(f"Invalid status: {status}")
        api_key.status = status
        await db.flush()
        return api_key

    @staticmethod
    async def update_quotas(
        db: AsyncSession,
        api_key: ApiKey,
        *,
        daily_request_limit: Optional[int] = None,
        monthly_token_limit: Optional[int] = None,
    ) -> ApiKey:
        api_key.daily_request_limit = daily_request_limit
        api_key.monthly_token_limit = monthly_token_limit
        await db.flush()
        return api_key

    @staticmethod
    async def delete(db: AsyncSession, api_key: ApiKey) -> None:
        await db.delete(api_key)
        await db.flush()
