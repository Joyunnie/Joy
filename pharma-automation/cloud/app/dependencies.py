import hashlib

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.tables import Pharmacy, User

_bearer_scheme = HTTPBearer()


def decode_jwt_payload(token: str) -> dict:
    """Decode and return JWT payload. Raises jwt exceptions on failure."""
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


async def verify_api_key(
    x_api_key: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> Pharmacy:
    """
    1. X-API-Key 헤더에서 API key 추출
    2. SHA-256 해시 계산
    3. pharmacies 테이블에서 api_key_hash와 매칭
    4. 매칭되는 약국 반환 (없으면 401)
    """
    key_hash = hashlib.new(settings.api_key_hash_algorithm, x_api_key.encode()).hexdigest()
    result = await db.execute(
        select(Pharmacy).where(Pharmacy.api_key_hash == key_hash)
    )
    pharmacy = result.scalar_one_or_none()
    if pharmacy is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return pharmacy


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    JWT에서 user_id를 추출하고 DB에서 사용자를 조회한다.
    P13 트레이드오프: 매 요청 DB 조회 (is_active 실시간 검증 필요).
    JWT payload만으로 pharmacy_id/role 확인 가능하나, 비활성화된 사용자 차단을 위해 DB 조회 유지.
    성능 병목 발생 시 Phase 2C에서 Redis 캐시(user_id → is_active) 도입 검토.
    """
    token = credentials.credentials
    try:
        payload = decode_jwt_payload(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    user_id = int(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    return user
