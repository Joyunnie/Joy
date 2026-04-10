"""Cross-pharmacy isolation tests.

Verifies that authenticated users can only access data belonging to their
own pharmacy_id. Tests endpoints beyond the OTC/narcotics isolation tests
that already exist.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.models.tables import (
    AlertLog,
    AtdpsCanister,
    Pharmacy,
    ShelfLayout,
    Todo,
    User,
    VisitPrediction,
)
from tests.conftest import seed_session_factory

pytestmark = pytest.mark.asyncio

# We'll seed data into a SECOND pharmacy and verify the test user (pharmacy 7)
# cannot see it.

_other_pharmacy_id: int | None = None
_other_user_id: int | None = None


async def _ensure_other_pharmacy() -> int:
    """Create or find a second pharmacy (+ user) for isolation testing."""
    global _other_pharmacy_id, _other_user_id
    if _other_pharmacy_id is not None:
        return _other_pharmacy_id

    async with seed_session_factory() as db:
        result = await db.execute(
            select(Pharmacy).where(Pharmacy.name == "격리테스트약국")
        )
        existing = result.scalar_one_or_none()
        if existing:
            _other_pharmacy_id = existing.id
        else:
            other = Pharmacy(
                name="격리테스트약국",
                patient_hash_salt="other-salt",
                patient_hash_algorithm="SHA-256",
                api_key_hash="other-api-key-hash",
                invite_code="OTHER-CODE",
            )
            db.add(other)
            await db.flush()
            _other_pharmacy_id = other.id

        # Ensure a user exists in the other pharmacy (needed for todo FK)
        user_result = await db.execute(
            select(User).where(User.pharmacy_id == _other_pharmacy_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            import bcrypt
            user = User(
                pharmacy_id=_other_pharmacy_id,
                username="otheruser",
                password_hash=bcrypt.hashpw(b"pass", bcrypt.gensalt()).decode(),
                role="PHARMACIST",
            )
            db.add(user)
            await db.flush()
        _other_user_id = user.id

        await db.commit()
        return _other_pharmacy_id


@pytest_asyncio.fixture(autouse=True)
async def cleanup_other(seed_data):
    """Clean data seeded into the other pharmacy."""
    other_pid = await _ensure_other_pharmacy()
    async with seed_session_factory() as db:
        await db.execute(AlertLog.__table__.delete().where(AlertLog.pharmacy_id == other_pid))
        await db.execute(VisitPrediction.__table__.delete().where(VisitPrediction.pharmacy_id == other_pid))
        await db.execute(AtdpsCanister.__table__.delete().where(AtdpsCanister.pharmacy_id == other_pid))
        await db.execute(ShelfLayout.__table__.delete().where(ShelfLayout.pharmacy_id == other_pid))
        await db.execute(Todo.__table__.delete().where(Todo.pharmacy_id == other_pid))
        # Also clean test pharmacy data
        pid = seed_data["pharmacy_id"]
        await db.execute(AlertLog.__table__.delete().where(AlertLog.pharmacy_id == pid))
        await db.execute(AtdpsCanister.__table__.delete().where(AtdpsCanister.pharmacy_id == pid))
        await db.execute(ShelfLayout.__table__.delete().where(ShelfLayout.pharmacy_id == pid))
        await db.execute(Todo.__table__.delete().where(Todo.pharmacy_id == pid))
        await db.commit()
    yield
    async with seed_session_factory() as db:
        await db.execute(AlertLog.__table__.delete().where(AlertLog.pharmacy_id == other_pid))
        await db.execute(VisitPrediction.__table__.delete().where(VisitPrediction.pharmacy_id == other_pid))
        await db.execute(AtdpsCanister.__table__.delete().where(AtdpsCanister.pharmacy_id == other_pid))
        await db.execute(ShelfLayout.__table__.delete().where(ShelfLayout.pharmacy_id == other_pid))
        await db.execute(Todo.__table__.delete().where(Todo.pharmacy_id == other_pid))
        await db.commit()


class TestAlertIsolation:
    async def test_other_pharmacy_alerts_not_visible(
        self, client: AsyncClient, auth_headers: dict, seed_data: dict,
    ):
        """Alerts from another pharmacy are not returned."""
        other_pid = await _ensure_other_pharmacy()
        async with seed_session_factory() as db:
            db.add(AlertLog(
                pharmacy_id=other_pid,
                alert_type="LOW_STOCK",
                message="Other pharmacy alert",
                sent_via="IN_APP",
            ))
            db.add(AlertLog(
                pharmacy_id=seed_data["pharmacy_id"],
                alert_type="LOW_STOCK",
                message="My pharmacy alert",
                sent_via="IN_APP",
            ))
            await db.commit()

        resp = await client.get("/api/v1/alerts", headers=auth_headers)
        assert resp.status_code == 200
        alerts = resp.json()["alerts"]
        assert len(alerts) == 1
        assert alerts[0]["message"] == "My pharmacy alert"


class TestCanisterIsolation:
    async def test_other_pharmacy_canisters_not_visible(
        self, client: AsyncClient, auth_headers: dict, seed_data: dict,
    ):
        """Canisters from another pharmacy are not listed."""
        other_pid = await _ensure_other_pharmacy()
        async with seed_session_factory() as db:
            db.add(AtdpsCanister(
                pharmacy_id=other_pid,
                canister_number=1,
                drug_code="OTHER001",
                drug_name="타약국약품",
            ))
            db.add(AtdpsCanister(
                pharmacy_id=seed_data["pharmacy_id"],
                canister_number=1,
                drug_code="MY001",
                drug_name="우리약국약품",
            ))
            await db.commit()

        resp = await client.get("/api/v1/canisters", headers=auth_headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["drug_name"] == "우리약국약품"


class TestShelfLayoutIsolation:
    async def test_other_pharmacy_layouts_not_visible(
        self, client: AsyncClient, auth_headers: dict, seed_data: dict,
    ):
        """Shelf layouts from another pharmacy are not listed."""
        other_pid = await _ensure_other_pharmacy()
        async with seed_session_factory() as db:
            db.add(ShelfLayout(
                pharmacy_id=other_pid,
                name="타약국선반",
                location_type="DISPLAY",
                position="front",
                rows=4,
                cols=6,
            ))
            await db.commit()

        resp = await client.get("/api/v1/shelf-layouts", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["items"] == []


class TestTodoIsolation:
    async def test_other_pharmacy_todos_not_visible(
        self, client: AsyncClient, auth_headers: dict, seed_data: dict,
    ):
        """Todos from another pharmacy are not listed."""
        other_pid = await _ensure_other_pharmacy()
        async with seed_session_factory() as db:
            db.add(Todo(
                pharmacy_id=other_pid,
                title="타약국 할일",
                priority=4,
                created_by=_other_user_id,
            ))
            await db.commit()

        # Create one in our pharmacy via API
        await client.post(
            "/api/v1/todos",
            json={"title": "우리 할일"},
            headers=auth_headers,
        )

        resp = await client.get("/api/v1/todos", headers=auth_headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["title"] == "우리 할일"

    async def test_cannot_access_other_pharmacy_todo_by_id(
        self, client: AsyncClient, auth_headers: dict,
    ):
        """Direct access to another pharmacy's todo by ID returns 404."""
        other_pid = await _ensure_other_pharmacy()
        async with seed_session_factory() as db:
            todo = Todo(pharmacy_id=other_pid, title="비밀 할일", priority=4, created_by=_other_user_id)
            db.add(todo)
            await db.flush()
            todo_id = todo.id
            await db.commit()

        resp = await client.get(f"/api/v1/todos/{todo_id}", headers=auth_headers)
        assert resp.status_code == 404
