import hashlib

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.tables import Pharmacy


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
