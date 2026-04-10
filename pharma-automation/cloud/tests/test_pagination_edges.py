"""Tests for pagination edge cases across multiple endpoints.

Covers: offset beyond total, last page partial results, limit=1,
empty result sets, total count accuracy.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.models.tables import AlertLog, Todo
from tests.conftest import seed_session_factory

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture(autouse=True)
async def cleanup(seed_data):
    pid = seed_data["pharmacy_id"]
    async with seed_session_factory() as db:
        await db.execute(AlertLog.__table__.delete().where(AlertLog.pharmacy_id == pid))
        await db.execute(Todo.__table__.delete().where(Todo.pharmacy_id == pid))
        await db.commit()
    yield
    async with seed_session_factory() as db:
        await db.execute(AlertLog.__table__.delete().where(AlertLog.pharmacy_id == pid))
        await db.execute(Todo.__table__.delete().where(Todo.pharmacy_id == pid))
        await db.commit()


async def _seed_alerts(pharmacy_id: int, count: int) -> None:
    async with seed_session_factory() as db:
        for i in range(count):
            db.add(AlertLog(
                pharmacy_id=pharmacy_id,
                alert_type="LOW_STOCK",
                ref_table="drug_stock",
                ref_id=i,
                message=f"Test alert {i}",
                sent_via="IN_APP",
            ))
        await db.commit()


async def _seed_todos(pharmacy_id: int, count: int, auth_headers: dict, client) -> None:
    """Create todos via API to properly set pharmacy_id."""
    for i in range(count):
        await client.post(
            "/api/v1/todos",
            json={"title": f"Todo {i}"},
            headers=auth_headers,
        )


class TestAlertsPagination:
    async def test_offset_beyond_total_returns_empty(
        self, client: AsyncClient, auth_headers: dict, seed_data: dict,
    ):
        await _seed_alerts(seed_data["pharmacy_id"], 3)

        resp = await client.get(
            "/api/v1/alerts", params={"offset": 100}, headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["alerts"] == []
        assert data["total"] == 3  # total still reflects full count

    async def test_offset_equals_total(
        self, client: AsyncClient, auth_headers: dict, seed_data: dict,
    ):
        await _seed_alerts(seed_data["pharmacy_id"], 5)

        resp = await client.get(
            "/api/v1/alerts", params={"offset": 5}, headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["alerts"] == []

    async def test_limit_one_returns_single(
        self, client: AsyncClient, auth_headers: dict, seed_data: dict,
    ):
        await _seed_alerts(seed_data["pharmacy_id"], 5)

        resp = await client.get(
            "/api/v1/alerts", params={"limit": 1}, headers=auth_headers,
        )
        data = resp.json()
        assert len(data["alerts"]) == 1
        assert data["total"] == 5

    async def test_last_page_partial_results(
        self, client: AsyncClient, auth_headers: dict, seed_data: dict,
    ):
        await _seed_alerts(seed_data["pharmacy_id"], 7)

        # Page size 3, offset 6 → 1 item left
        resp = await client.get(
            "/api/v1/alerts", params={"limit": 3, "offset": 6}, headers=auth_headers,
        )
        data = resp.json()
        assert len(data["alerts"]) == 1
        assert data["total"] == 7

    async def test_empty_result_with_filter(
        self, client: AsyncClient, auth_headers: dict, seed_data: dict,
    ):
        await _seed_alerts(seed_data["pharmacy_id"], 3)  # all LOW_STOCK

        resp = await client.get(
            "/api/v1/alerts",
            params={"alert_type": "VISIT_APPROACHING"},
            headers=auth_headers,
        )
        data = resp.json()
        assert data["alerts"] == []
        assert data["total"] == 0


class TestTodosPagination:
    async def test_offset_beyond_total(
        self, client: AsyncClient, auth_headers: dict,
    ):
        await _seed_todos(0, 3, auth_headers, client)

        resp = await client.get(
            "/api/v1/todos", params={"offset": 100}, headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 3

    async def test_limit_one(
        self, client: AsyncClient, auth_headers: dict,
    ):
        await _seed_todos(0, 5, auth_headers, client)

        resp = await client.get(
            "/api/v1/todos", params={"limit": 1}, headers=auth_headers,
        )
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["total"] == 5

    async def test_empty_filter_returns_zero_total(
        self, client: AsyncClient, auth_headers: dict,
    ):
        # No todos created
        resp = await client.get(
            "/api/v1/todos", params={"filter": "completed"}, headers=auth_headers,
        )
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0


class TestPredictionsPagination:
    async def test_empty_predictions(
        self, client: AsyncClient, auth_headers: dict,
    ):
        resp = await client.get(
            "/api/v1/predictions",
            params={"days_ahead": 7, "limit": 50, "offset": 0},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["predictions"] == []
        assert data["total"] == 0

    async def test_offset_beyond_total(
        self, client: AsyncClient, auth_headers: dict,
    ):
        resp = await client.get(
            "/api/v1/predictions",
            params={"days_ahead": 30, "offset": 9999},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["predictions"] == []
