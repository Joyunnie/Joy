import hashlib
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import get_db
from app.main import app
from app.models.tables import Base, Drug, Pharmacy

# Use the same DB for testing (tables created by DDL init script)
TEST_DATABASE_URL = "postgresql+asyncpg://pharma_user:pharma_pass@localhost:5432/pharma"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

TEST_API_KEY = "test-api-key-12345"
TEST_API_KEY_HASH = hashlib.sha256(TEST_API_KEY.encode()).hexdigest()


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with test_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture
async def seed_data():
    """Insert test pharmacy and drugs."""
    async with test_session() as db:
        # Check if test pharmacy exists
        from sqlalchemy import select
        result = await db.execute(select(Pharmacy).where(Pharmacy.name == "테스트약국"))
        existing = result.scalar_one_or_none()
        if existing:
            yield {"pharmacy_id": existing.id, "api_key": TEST_API_KEY}
            return

        pharmacy = Pharmacy(
            name="테스트약국",
            patient_hash_salt="test-salt",
            patient_hash_algorithm="SHA-256",
            api_key_hash=TEST_API_KEY_HASH,
            default_alert_days_before=3,
        )
        db.add(pharmacy)
        await db.flush()

        drug1 = Drug(standard_code="KD12345", name="아모시실린", category="PRESCRIPTION")
        drug2 = Drug(standard_code="KD67890", name="타이레놀", category="OTC")
        db.add_all([drug1, drug2])
        await db.commit()

        yield {"pharmacy_id": pharmacy.id, "api_key": TEST_API_KEY}


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
