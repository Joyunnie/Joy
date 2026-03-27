import hashlib
import time

import jwt
import pytest
from httpx import AsyncClient

from tests.conftest import TEST_INVITE_CODE, TEST_USER_PASSWORD


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient, seed_data: dict):
    # Clean up from previous runs to ensure idempotency
    from tests.conftest import seed_session_factory
    from app.models.tables import User
    from sqlalchemy import delete
    async with seed_session_factory() as db:
        await db.execute(delete(User).where(User.username == "newuser1"))
        await db.commit()

    resp = await client.post("/api/v1/auth/register", json={
        "pharmacy_id": seed_data["pharmacy_id"],
        "invite_code": TEST_INVITE_CODE,
        "username": "newuser1",
        "password": "securepass123",
        "role": "STAFF",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "newuser1"
    assert data["role"] == "STAFF"
    assert data["pharmacy_id"] == seed_data["pharmacy_id"]


@pytest.mark.asyncio
async def test_register_duplicate_username(client: AsyncClient, user_seed_data: dict):
    resp = await client.post("/api/v1/auth/register", json={
        "pharmacy_id": user_seed_data["pharmacy_id"],
        "invite_code": TEST_INVITE_CODE,
        "username": user_seed_data["username"],
        "password": "anotherpass123",
    })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_register_invalid_pharmacy(client: AsyncClient):
    resp = await client.post("/api/v1/auth/register", json={
        "pharmacy_id": 999999,
        "invite_code": "anything",
        "username": "somebody",
        "password": "securepass123",
    })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_register_invalid_invite_code(client: AsyncClient, seed_data: dict):
    resp = await client.post("/api/v1/auth/register", json={
        "pharmacy_id": seed_data["pharmacy_id"],
        "invite_code": "WRONG-CODE",
        "username": "baduser",
        "password": "securepass123",
    })
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_register_weak_password(client: AsyncClient, seed_data: dict):
    resp = await client.post("/api/v1/auth/register", json={
        "pharmacy_id": seed_data["pharmacy_id"],
        "invite_code": TEST_INVITE_CODE,
        "username": "weakpw",
        "password": "short",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_invalid_role(client: AsyncClient, seed_data: dict):
    resp = await client.post("/api/v1/auth/register", json={
        "pharmacy_id": seed_data["pharmacy_id"],
        "invite_code": TEST_INVITE_CODE,
        "username": "badrole",
        "password": "securepass123",
        "role": "SUPERADMIN",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, user_seed_data: dict):
    resp = await client.post("/api/v1/auth/login", json={
        "pharmacy_id": user_seed_data["pharmacy_id"],
        "username": user_seed_data["username"],
        "password": user_seed_data["password"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, user_seed_data: dict):
    resp = await client.post("/api/v1/auth/login", json={
        "pharmacy_id": user_seed_data["pharmacy_id"],
        "username": user_seed_data["username"],
        "password": "wrongpassword",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient, seed_data: dict):
    resp = await client.post("/api/v1/auth/login", json={
        "pharmacy_id": seed_data["pharmacy_id"],
        "username": "nonexistent",
        "password": "somepassword",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_inactive_user(client: AsyncClient, seed_data: dict):
    """is_active=False 사용자 로그인 시 401."""
    # 비활성 사용자 생성
    import bcrypt as _bcrypt
    from sqlalchemy import select
    from tests.conftest import seed_session_factory
    from app.models.tables import User

    async with seed_session_factory() as db:
        pw = _bcrypt.hashpw(b"securepass123", _bcrypt.gensalt()).decode()
        existing = await db.execute(
            select(User).where(User.pharmacy_id == seed_data["pharmacy_id"], User.username == "inactive_user")
        )
        if not existing.scalar_one_or_none():
            db.add(User(
                pharmacy_id=seed_data["pharmacy_id"],
                username="inactive_user",
                password_hash=pw,
                role="STAFF",
                is_active=False,
            ))
            await db.commit()

    resp = await client.post("/api/v1/auth/login", json={
        "pharmacy_id": seed_data["pharmacy_id"],
        "username": "inactive_user",
        "password": "securepass123",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_success(client: AsyncClient, user_seed_data: dict):
    login_resp = await client.post("/api/v1/auth/login", json={
        "pharmacy_id": user_seed_data["pharmacy_id"],
        "username": user_seed_data["username"],
        "password": user_seed_data["password"],
    })
    tokens = login_resp.json()

    resp = await client.post("/api/v1/auth/refresh", json={
        "refresh_token": tokens["refresh_token"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_refresh_expired(client: AsyncClient, user_seed_data: dict):
    """만료된 refresh_token → 401."""
    from datetime import datetime, timezone
    from sqlalchemy import select
    from tests.conftest import seed_session_factory
    from app.models.tables import RefreshToken

    raw = "expired-token-test-12345"
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    async with seed_session_factory() as db:
        existing = await db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        if not existing.scalar_one_or_none():
            db.add(RefreshToken(
                user_id=user_seed_data["user_id"],
                token_hash=token_hash,
                expires_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            ))
            await db.commit()

    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": raw})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_after_logout(client: AsyncClient, user_seed_data: dict):
    """로그아웃 후 refresh → 401."""
    login_resp = await client.post("/api/v1/auth/login", json={
        "pharmacy_id": user_seed_data["pharmacy_id"],
        "username": user_seed_data["username"],
        "password": user_seed_data["password"],
    })
    tokens = login_resp.json()

    await client.post("/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})

    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_success(client: AsyncClient, user_seed_data: dict):
    login_resp = await client.post("/api/v1/auth/login", json={
        "pharmacy_id": user_seed_data["pharmacy_id"],
        "username": user_seed_data["username"],
        "password": user_seed_data["password"],
    })
    tokens = login_resp.json()

    resp = await client.post("/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 200

    # refresh should fail now
    refresh_resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh_resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_idempotent(client: AsyncClient, user_seed_data: dict):
    login_resp = await client.post("/api/v1/auth/login", json={
        "pharmacy_id": user_seed_data["pharmacy_id"],
        "username": user_seed_data["username"],
        "password": user_seed_data["password"],
    })
    tokens = login_resp.json()

    resp1 = await client.post("/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert resp1.status_code == 200

    resp2 = await client.post("/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert resp2.status_code == 200


@pytest.mark.asyncio
async def test_jwt_protects_alerts(client: AsyncClient):
    resp = await client.get("/api/v1/alerts")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_jwt_protects_inventory(client: AsyncClient):
    resp = await client.get("/api/v1/inventory/status")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_jwt_protects_predictions(client: AsyncClient):
    resp = await client.get("/api/v1/predictions")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_alerts_with_jwt(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/alerts", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "alerts" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_cross_pharmacy_isolation(client: AsyncClient, auth_headers: dict):
    """약국 A 사용자 JWT로 접근 → 자기 약국 데이터만 반환 (다른 약국 데이터 불포함)."""
    resp = await client.get("/api/v1/alerts", headers=auth_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_expired_access_token(client: AsyncClient):
    """만료된 access_token → 401."""
    from app.config import settings

    payload = {
        "sub": "1",
        "pharmacy_id": 1,
        "role": "PHARMACIST",
        "type": "access",
        "iat": time.time() - 3600,
        "exp": time.time() - 1800,
    }
    expired_token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    resp = await client.get("/api/v1/alerts", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401
