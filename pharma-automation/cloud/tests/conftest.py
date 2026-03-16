import asyncio
import hashlib
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import get_db
from app.main import app
from app.models.tables import Drug, Pharmacy

TEST_DATABASE_URL = "postgresql+asyncpg://pharma_user:pharma_pass@localhost:5432/pharma"
TEST_API_KEY = "test-api-key-12345"
TEST_API_KEY_HASH = hashlib.sha256(TEST_API_KEY.encode()).hexdigest()

# Separate engine for seeding (NullPool avoids connection sharing issues)
from sqlalchemy.pool import NullPool

seed_engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
seed_session_factory = async_sessionmaker(seed_engine, class_=AsyncSession, expire_on_commit=False)

# App engine — also NullPool for test isolation
app_engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
app_session_factory = async_sessionmaker(app_engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with app_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_db] = override_get_db

# Cached seed data so we only insert once
_seed_cache: dict | None = None


async def _ensure_seed():
    global _seed_cache
    if _seed_cache is not None:
        return _seed_cache

    async with seed_session_factory() as db:
        result = await db.execute(select(Pharmacy).where(Pharmacy.name == "테스트약국"))
        existing = result.scalar_one_or_none()
        if existing:
            _seed_cache = {"pharmacy_id": existing.id, "api_key": TEST_API_KEY}
            return _seed_cache

        pharmacy = Pharmacy(
            name="테스트약국",
            patient_hash_salt="test-salt",
            patient_hash_algorithm="SHA-256",
            api_key_hash=TEST_API_KEY_HASH,
            default_alert_days_before=3,
        )
        db.add(pharmacy)
        await db.flush()

        drug_result = await db.execute(select(Drug).where(Drug.standard_code == "KD12345"))
        if not drug_result.scalar_one_or_none():
            db.add(Drug(standard_code="KD12345", name="아모시실린", category="PRESCRIPTION"))
            db.add(Drug(standard_code="KD67890", name="타이레놀", category="OTC"))

        await db.commit()
        _seed_cache = {"pharmacy_id": pharmacy.id, "api_key": TEST_API_KEY}
        return _seed_cache


@pytest_asyncio.fixture
async def seed_data():
    return await _ensure_seed()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
