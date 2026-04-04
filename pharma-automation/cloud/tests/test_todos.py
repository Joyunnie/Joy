from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import Todo
from tests.conftest import seed_session_factory


@pytest_asyncio.fixture(autouse=True)
async def cleanup_todos(seed_data):
    """Todo 테스트 전 기존 todos 정리."""
    async with seed_session_factory() as db:
        pharmacy_id = seed_data["pharmacy_id"]
        await db.execute(
            Todo.__table__.delete().where(Todo.pharmacy_id == pharmacy_id)
        )
        await db.commit()
    yield


@pytest.mark.asyncio
async def test_create_todo(client: AsyncClient, auth_headers: dict, seed_data: dict):
    resp = await client.post(
        "/api/v1/todos",
        json={"title": "약품 발주", "priority": 2},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "약품 발주"
    assert data["priority"] == 2
    assert data["is_completed"] is False
    assert data["pharmacy_id"] == seed_data["pharmacy_id"]


@pytest.mark.asyncio
async def test_list_todos(client: AsyncClient, auth_headers: dict):
    # Create 2 todos
    await client.post(
        "/api/v1/todos",
        json={"title": "할일 1"},
        headers=auth_headers,
    )
    await client.post(
        "/api/v1/todos",
        json={"title": "할일 2"},
        headers=auth_headers,
    )

    resp = await client.get("/api/v1/todos", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_get_todo(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post(
        "/api/v1/todos",
        json={"title": "테스트"},
        headers=auth_headers,
    )
    todo_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/todos/{todo_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["title"] == "테스트"


@pytest.mark.asyncio
async def test_update_todo(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post(
        "/api/v1/todos",
        json={"title": "원래 제목", "priority": 4},
        headers=auth_headers,
    )
    todo_id = create_resp.json()["id"]

    resp = await client.put(
        f"/api/v1/todos/{todo_id}",
        json={"title": "수정된 제목", "priority": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "수정된 제목"
    assert data["priority"] == 1


@pytest.mark.asyncio
async def test_delete_todo(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post(
        "/api/v1/todos",
        json={"title": "삭제할 것"},
        headers=auth_headers,
    )
    todo_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/v1/todos/{todo_id}", headers=auth_headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/todos/{todo_id}", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_toggle_complete(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post(
        "/api/v1/todos",
        json={"title": "완료 토글"},
        headers=auth_headers,
    )
    todo_id = create_resp.json()["id"]

    # Complete
    resp = await client.patch(
        f"/api/v1/todos/{todo_id}/complete", headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_completed"] is True
    assert data["completed_at"] is not None
    assert data["completed_by"] is not None

    # Uncomplete
    resp = await client.patch(
        f"/api/v1/todos/{todo_id}/complete", headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_completed"] is False
    assert data["completed_at"] is None
    assert data["completed_by"] is None


@pytest.mark.asyncio
async def test_reschedule(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post(
        "/api/v1/todos",
        json={"title": "미루기", "due_date": "2026-04-05T09:00:00+09:00"},
        headers=auth_headers,
    )
    todo_id = create_resp.json()["id"]

    new_date = "2026-04-10T15:00:00+09:00"
    resp = await client.patch(
        f"/api/v1/todos/{todo_id}/reschedule",
        json={"due_date": new_date},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert "2026-04-10" in resp.json()["due_date"]


@pytest.mark.asyncio
async def test_filter_today(client: AsyncClient, auth_headers: dict):
    """오늘 due_date가 있는 항목만 필터링."""
    now = datetime.now(timezone(timedelta(hours=9)))
    today_str = now.strftime("%Y-%m-%dT12:00:00+09:00")
    tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%dT12:00:00+09:00")

    await client.post(
        "/api/v1/todos",
        json={"title": "오늘 할일", "due_date": today_str},
        headers=auth_headers,
    )
    await client.post(
        "/api/v1/todos",
        json={"title": "내일 할일", "due_date": tomorrow_str},
        headers=auth_headers,
    )

    resp = await client.get(
        "/api/v1/todos", params={"filter": "today"}, headers=auth_headers
    )
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "오늘 할일"


@pytest.mark.asyncio
async def test_filter_overdue(client: AsyncClient, auth_headers: dict):
    """기한 지난 항목 필터링."""
    yesterday = (
        datetime.now(timezone(timedelta(hours=9))) - timedelta(days=1)
    ).strftime("%Y-%m-%dT12:00:00+09:00")

    await client.post(
        "/api/v1/todos",
        json={"title": "지난 할일", "due_date": yesterday},
        headers=auth_headers,
    )

    resp = await client.get(
        "/api/v1/todos", params={"filter": "overdue"}, headers=auth_headers
    )
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "지난 할일"


@pytest.mark.asyncio
async def test_filter_no_date(client: AsyncClient, auth_headers: dict):
    """날짜 없는 항목 필터링."""
    await client.post(
        "/api/v1/todos",
        json={"title": "날짜없음"},
        headers=auth_headers,
    )
    await client.post(
        "/api/v1/todos",
        json={"title": "날짜있음", "due_date": "2026-05-01T12:00:00+09:00"},
        headers=auth_headers,
    )

    resp = await client.get(
        "/api/v1/todos", params={"filter": "no_date"}, headers=auth_headers
    )
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "날짜없음"


@pytest.mark.asyncio
async def test_not_found(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/todos/999999", headers=auth_headers)
    assert resp.status_code == 404
