import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_search_drugs_by_name(
    client: AsyncClient, auth_headers: dict, seed_data: dict
):
    resp = await client.get(
        "/api/v1/drugs?search=타이레놀", headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1
    assert any(d["name"] == "타이레놀" for d in data["items"])


@pytest.mark.asyncio
async def test_filter_drugs_by_category(
    client: AsyncClient, auth_headers: dict, seed_data: dict
):
    resp = await client.get(
        "/api/v1/drugs?category=OTC", headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    for d in data["items"]:
        assert d["category"] == "OTC"

    # PRESCRIPTION 확인
    resp2 = await client.get(
        "/api/v1/drugs?category=PRESCRIPTION", headers=auth_headers
    )
    assert resp2.status_code == 200
    for d in resp2.json()["items"]:
        assert d["category"] == "PRESCRIPTION"


@pytest.mark.asyncio
async def test_search_drugs_empty_result(
    client: AsyncClient, auth_headers: dict, seed_data: dict
):
    resp = await client.get(
        "/api/v1/drugs?search=존재하지않는약품이름", headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0
