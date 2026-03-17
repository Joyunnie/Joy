import hashlib
from collections.abc import AsyncGenerator

import bcrypt
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.database import get_db
from app.main import app
from app.models.tables import (
    AlertLog,
    Drug,
    DrugThreshold,
    InventoryAuditLog,
    NarcoticsInventory,
    NarcoticsTransaction,
    OtcInventory,
    Pharmacy,
    User,
)

TEST_DATABASE_URL = "postgresql+asyncpg://pharma_user:pharma_pass@localhost:5432/pharma"
TEST_API_KEY = "test-api-key-12345"
TEST_API_KEY_HASH = hashlib.sha256(TEST_API_KEY.encode()).hexdigest()
TEST_INVITE_CODE = "TEST-INVITE"
TEST_USER_PASSWORD = "testpass123"

seed_engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
seed_session_factory = async_sessionmaker(seed_engine, class_=AsyncSession, expire_on_commit=False)

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

_seed_cache: dict | None = None


async def _ensure_seed():
    global _seed_cache
    if _seed_cache is not None:
        return _seed_cache

    async with seed_session_factory() as db:
        result = await db.execute(select(Pharmacy).where(Pharmacy.name == "테스트약국"))
        existing = result.scalar_one_or_none()
        if existing:
            # invite_code가 없으면 설정
            if existing.invite_code != TEST_INVITE_CODE:
                existing.invite_code = TEST_INVITE_CODE
                await db.commit()
            _seed_cache = {"pharmacy_id": existing.id, "api_key": TEST_API_KEY}
            return _seed_cache

        pharmacy = Pharmacy(
            name="테스트약국",
            patient_hash_salt="test-salt",
            patient_hash_algorithm="SHA-256",
            api_key_hash=TEST_API_KEY_HASH,
            invite_code=TEST_INVITE_CODE,
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


_user_seed_cache: dict | None = None


async def _ensure_user_seed(pharmacy_id: int):
    global _user_seed_cache
    if _user_seed_cache is not None:
        return _user_seed_cache

    async with seed_session_factory() as db:
        result = await db.execute(
            select(User).where(User.pharmacy_id == pharmacy_id, User.username == "testuser")
        )
        existing = result.scalar_one_or_none()
        if existing:
            _user_seed_cache = {
                "user_id": existing.id,
                "pharmacy_id": existing.pharmacy_id,
                "username": existing.username,
                "password": TEST_USER_PASSWORD,
            }
            return _user_seed_cache

        pw_hash = bcrypt.hashpw(TEST_USER_PASSWORD.encode(), bcrypt.gensalt()).decode()
        user = User(
            pharmacy_id=pharmacy_id,
            username="testuser",
            password_hash=pw_hash,
            role="PHARMACIST",
        )
        db.add(user)
        await db.commit()

        _user_seed_cache = {
            "user_id": user.id,
            "pharmacy_id": user.pharmacy_id,
            "username": user.username,
            "password": TEST_USER_PASSWORD,
        }
        return _user_seed_cache


@pytest_asyncio.fixture
async def seed_data():
    return await _ensure_seed()


@pytest_asyncio.fixture
async def user_seed_data(seed_data):
    return await _ensure_user_seed(seed_data["pharmacy_id"])


@pytest_asyncio.fixture
async def auth_headers(client, user_seed_data):
    """로그인하여 Authorization 헤더 반환."""
    resp = await client.post("/api/v1/auth/login", json={
        "pharmacy_id": user_seed_data["pharmacy_id"],
        "username": user_seed_data["username"],
        "password": user_seed_data["password"],
    })
    tokens = resp.json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# --- OTC 테스트용 시드/헬퍼 ---

_otc_drug_cache: dict | None = None


async def _ensure_otc_drug_seed(pharmacy_id: int):
    """OTC 약품(타이레놀)의 drug_id 조회 + threshold 시드."""
    global _otc_drug_cache
    if _otc_drug_cache is not None:
        return _otc_drug_cache

    async with seed_session_factory() as db:
        result = await db.execute(select(Drug).where(Drug.standard_code == "KD67890"))
        drug = result.scalar_one_or_none()
        if not drug:
            drug = Drug(standard_code="KD67890", name="타이레놀", category="OTC")
            db.add(drug)
            await db.flush()

        # threshold 시드 (min_quantity=10)
        th_result = await db.execute(
            select(DrugThreshold).where(
                DrugThreshold.pharmacy_id == pharmacy_id,
                DrugThreshold.drug_id == drug.id,
            )
        )
        if not th_result.scalar_one_or_none():
            db.add(DrugThreshold(
                pharmacy_id=pharmacy_id,
                drug_id=drug.id,
                min_quantity=10,
                is_active=True,
            ))

        await db.commit()
        _otc_drug_cache = {"drug_id": drug.id, "drug_name": drug.name}
        return _otc_drug_cache


@pytest_asyncio.fixture
async def otc_drug_seed(seed_data):
    """OTC 약품 + threshold 시드. seed_data["pharmacy_id"] 기준."""
    return await _ensure_otc_drug_seed(seed_data["pharmacy_id"])


@pytest_asyncio.fixture(autouse=False)
async def cleanup_otc(seed_data):
    """OTC 테스트 전 기존 otc_inventory + 관련 audit/alert 정리."""
    async with seed_session_factory() as db:
        pharmacy_id = seed_data["pharmacy_id"]
        await db.execute(
            OtcInventory.__table__.delete().where(
                OtcInventory.pharmacy_id == pharmacy_id
            )
        )
        await db.execute(
            InventoryAuditLog.__table__.delete().where(
                InventoryAuditLog.pharmacy_id == pharmacy_id,
            )
        )
        await db.execute(
            AlertLog.__table__.delete().where(
                AlertLog.pharmacy_id == pharmacy_id,
            )
        )
        await db.commit()
    yield


# --- Narcotics 테스트용 시드/헬퍼 ---

_narcotic_drug_cache: dict | None = None


async def _ensure_narcotic_drug_seed(pharmacy_id: int):
    """마약류 약품 시드 + threshold (min_quantity=10)."""
    global _narcotic_drug_cache
    if _narcotic_drug_cache is not None:
        return _narcotic_drug_cache

    async with seed_session_factory() as db:
        result = await db.execute(select(Drug).where(Drug.standard_code == "NC00001"))
        drug = result.scalar_one_or_none()
        if not drug:
            drug = Drug(standard_code="NC00001", name="펜타닐패치", category="NARCOTIC")
            db.add(drug)
            await db.flush()

        th_result = await db.execute(
            select(DrugThreshold).where(
                DrugThreshold.pharmacy_id == pharmacy_id,
                DrugThreshold.drug_id == drug.id,
            )
        )
        if not th_result.scalar_one_or_none():
            db.add(DrugThreshold(
                pharmacy_id=pharmacy_id,
                drug_id=drug.id,
                min_quantity=10,
                is_active=True,
            ))

        await db.commit()
        _narcotic_drug_cache = {"drug_id": drug.id, "drug_name": drug.name}
        return _narcotic_drug_cache


@pytest_asyncio.fixture
async def narcotic_drug_seed(seed_data):
    """마약류 약품 + threshold 시드."""
    return await _ensure_narcotic_drug_seed(seed_data["pharmacy_id"])


@pytest_asyncio.fixture(autouse=False)
async def cleanup_narcotics(seed_data):
    """Narcotics 테스트 전 기존 narcotics 관련 데이터 정리."""
    async with seed_session_factory() as db:
        pharmacy_id = seed_data["pharmacy_id"]
        await db.execute(
            NarcoticsTransaction.__table__.delete().where(
                NarcoticsTransaction.pharmacy_id == pharmacy_id
            )
        )
        await db.execute(
            NarcoticsInventory.__table__.delete().where(
                NarcoticsInventory.pharmacy_id == pharmacy_id
            )
        )
        await db.execute(
            InventoryAuditLog.__table__.delete().where(
                InventoryAuditLog.pharmacy_id == pharmacy_id,
            )
        )
        await db.execute(
            AlertLog.__table__.delete().where(
                AlertLog.pharmacy_id == pharmacy_id,
            )
        )
        await db.commit()
    yield
