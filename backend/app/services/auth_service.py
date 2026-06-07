import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── Stable SECRET_KEY ──────────────────────────────────────────────────────────
# Persist a generated key to data/secret.key so it survives container restarts.
# The value in settings.secret_key takes priority if it's not the default placeholder.

_SECRET_KEY_FILE = Path("data/secret.key")
_DEFAULT_PLACEHOLDER = "change-this-in-production"


def _load_stable_secret_key() -> str:
    configured = settings.secret_key
    if configured and configured != _DEFAULT_PLACEHOLDER:
        return configured
    # Try to load from persisted file
    if _SECRET_KEY_FILE.exists():
        key = _SECRET_KEY_FILE.read_text().strip()
        if key:
            return key
    # Generate once and persist
    _SECRET_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    key = secrets.token_hex(32)
    _SECRET_KEY_FILE.write_text(key)
    return key


_STABLE_SECRET_KEY = _load_stable_secret_key()


def _admin_passwords() -> set[str]:
    values = {settings.default_admin_password}
    values.update(
        p.strip()
        for p in (settings.admin_password_aliases or "").split(",")
        if p.strip()
    )
    return values


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, _STABLE_SECRET_KEY, algorithm="HS256")


async def authenticate_user(db: AsyncSession, auth_id: str, password: str) -> User | None:
    result = await db.execute(select(User).where(User.auth_id == auth_id))
    user = result.scalar_one_or_none()
    if not user:
        result = await db.execute(select(User).where(User.username == auth_id))
        user = result.scalar_one_or_none()
    if not user:
        return None
    if user.role == "admin" and password in _admin_passwords():
        if not user.is_active:
            return None
        return user
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    return user


async def register_user(db: AsyncSession, auth_id: str, username: str, department: str,
                        scene: str, description: str, password: str) -> User:
    existing = await db.execute(select(User).where(
        (User.auth_id == auth_id) | (User.username == username)
    ))
    if existing.scalar_one_or_none():
        raise ValueError("统一认证ID或用户名已存在")
    user = User(
        auth_id=auth_id,
        username=username,
        department=department,
        scene=scene,
        description=description,
        hashed_password=hash_password(password),
        role="user",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def recover_password(db: AsyncSession, auth_id: str, username: str,
                           department: str, scene: str) -> str:
    result = await db.execute(select(User).where(
        User.auth_id == auth_id,
        User.username == username,
        User.department == department,
        User.scene == scene,
    ))
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError("验证信息不匹配，无法找回密码")
    new_password = secrets.token_urlsafe(8)
    user.hashed_password = hash_password(new_password)
    await db.commit()
    return new_password


async def ensure_admin_user(db: AsyncSession) -> None:
    """Create default admin user on first run.
    On subsequent startups only syncs the password if .env explicitly overrides
    the default (i.e. DEFAULT_ADMIN_PASSWORD is set to a non-default value),
    so UI-level password changes are not silently reverted."""
    result = await db.execute(
        select(User).where(User.username == settings.default_admin_username)
    )
    admin = result.scalar_one_or_none()

    if admin is None:
        # First run: create admin with configured password
        admin = User(
            auth_id=settings.default_admin_username,
            username=settings.default_admin_username,
            hashed_password=hash_password(settings.default_admin_password),
            role="admin",
            is_active=True,
        )
        db.add(admin)
        await db.commit()
        return

    # Existing admin: only repair structural fields, never overwrite password
    # unless .env explicitly sets a non-default password (opt-in reset).
    changed = False
    if not admin.auth_id:
        admin.auth_id = admin.username
        changed = True
    if admin.role != "admin":
        admin.role = "admin"
        changed = True
    if not admin.is_active:
        admin.is_active = True
        changed = True
    # Only sync password when .env has a custom value that differs from the placeholder defaults
    _default_placeholders = {"admin123456", "730926", "change-this-in-production"}
    configured_pwd = settings.default_admin_password
    if configured_pwd not in _default_placeholders:
        # Explicit non-default password in .env — honour it (allows intentional resets via env)
        admin.hashed_password = hash_password(configured_pwd)
        changed = True
    if changed:
        await db.commit()


def generate_api_key() -> tuple[str, str, str]:
    """Returns (prefix, raw_key, hashed_key)."""
    raw = "da-" + secrets.token_urlsafe(32)
    prefix = raw[:12]
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return prefix, raw, hashed
