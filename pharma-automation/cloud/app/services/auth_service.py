import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import ServiceError
from app.models.tables import Pharmacy, RefreshToken, User
from app.schemas.auth import (
    AccessTokenResponse,
    LogoutResponse,
    RegisterResponse,
    TokenResponse,
)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_access_token(user_id: int, pharmacy_id: int, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "pharmacy_id": pharmacy_id,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


async def create_refresh_token(db: AsyncSession, user_id: int) -> str:
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)

    rt = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(rt)
    await db.flush()
    return raw_token


async def register_user(db: AsyncSession, pharmacy_id: int, invite_code: str,
                        username: str, password: str, role: str) -> RegisterResponse:
    # 1. 약국 존재 확인
    result = await db.execute(select(Pharmacy).where(Pharmacy.id == pharmacy_id))
    pharmacy = result.scalar_one_or_none()
    if pharmacy is None:
        raise ServiceError("Pharmacy not found", 404)

    # 2. invite_code 검증
    if pharmacy.invite_code != invite_code:
        raise ServiceError("Invalid invite code", 403)

    # 3. 중복 검사
    existing = await db.execute(
        select(User).where(User.pharmacy_id == pharmacy_id, User.username == username)
    )
    if existing.scalar_one_or_none() is not None:
        raise ServiceError("Username already exists", 409)

    # 4. 사용자 생성
    user = User(
        pharmacy_id=pharmacy_id,
        username=username,
        password_hash=hash_password(password),
        role=role,
    )
    db.add(user)
    await db.flush()

    return RegisterResponse(id=user.id, pharmacy_id=user.pharmacy_id, username=user.username, role=user.role)


async def login(db: AsyncSession, pharmacy_id: int, username: str, password: str) -> TokenResponse:
    result = await db.execute(
        select(User).where(User.pharmacy_id == pharmacy_id, User.username == username)
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(password, user.password_hash):
        raise ServiceError("Invalid credentials", 401)

    if not user.is_active:
        raise ServiceError("User is inactive", 401)

    access_token = create_access_token(user.id, user.pharmacy_id, user.role)
    refresh_token = await create_refresh_token(db, user.id)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


async def refresh_access_token(db: AsyncSession, refresh_token: str) -> AccessTokenResponse:
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    rt = result.scalar_one_or_none()

    if rt is None or rt.is_revoked:
        raise ServiceError("Invalid or revoked refresh token", 401)

    if rt.expires_at < datetime.now(timezone.utc):
        raise ServiceError("Refresh token expired", 401)

    # user 조회 + is_active 확인
    user_result = await db.execute(select(User).where(User.id == rt.user_id))
    user = user_result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise ServiceError("User not found or inactive", 401)

    access_token = create_access_token(user.id, user.pharmacy_id, user.role)
    return AccessTokenResponse(access_token=access_token)


async def logout(db: AsyncSession, refresh_token: str) -> LogoutResponse:
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    rt = result.scalar_one_or_none()

    if rt is not None and not rt.is_revoked:
        rt.is_revoked = True
        rt.revoked_at = datetime.now(timezone.utc)

    return LogoutResponse()
