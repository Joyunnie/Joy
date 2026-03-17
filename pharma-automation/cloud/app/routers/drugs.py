from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.tables import User
from app.schemas.drug import DrugListResponse
from app.services import drug_service

router = APIRouter(prefix="/api/v1/drugs", tags=["app-dev"])


@router.get("", response_model=DrugListResponse)
async def list_drugs(
    user: User = Depends(get_current_user),
    search: str | None = Query(None),
    category: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    return await drug_service.list_drugs(
        db, search=search, category=category, limit=limit, offset=offset
    )
