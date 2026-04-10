from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import verify_api_key
from app.models.tables import Pharmacy
from app.schemas.api import (
    SyncCassetteMappingRequest,
    SyncCassetteMappingResponse,
    SyncInventoryRequest,
    SyncInventoryResponse,
    SyncVisitsRequest,
    SyncVisitsResponse,
)
from app.schemas.drug_stock import SyncDrugStockRequest, SyncDrugStockResponse
from app.schemas.drug_sync import SyncDrugsRequest, SyncDrugsResponse
from app.services import sync_service

router = APIRouter()


@router.post("/inventory", response_model=SyncInventoryResponse)
async def sync_inventory(
    req: SyncInventoryRequest,
    pharmacy: Pharmacy = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    return await sync_service.sync_inventory(db, pharmacy.id, req)


@router.post("/cassette-mapping", response_model=SyncCassetteMappingResponse)
async def sync_cassette_mapping(
    req: SyncCassetteMappingRequest,
    pharmacy: Pharmacy = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    return await sync_service.sync_cassette_mapping(db, pharmacy.id, req)


@router.post("/visits", response_model=SyncVisitsResponse)
async def sync_visits(
    req: SyncVisitsRequest,
    pharmacy: Pharmacy = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    return await sync_service.sync_visits(db, pharmacy.id, req)


@router.post("/drugs", response_model=SyncDrugsResponse)
async def sync_drugs(
    req: SyncDrugsRequest,
    pharmacy: Pharmacy = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    return await sync_service.sync_drugs(db, pharmacy.id, req)


@router.post("/drug-stock", response_model=SyncDrugStockResponse)
async def sync_drug_stock(
    req: SyncDrugStockRequest,
    pharmacy: Pharmacy = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    return await sync_service.sync_drug_stock(db, pharmacy.id, req)
