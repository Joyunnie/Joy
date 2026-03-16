from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.auth import (
    AccessTokenResponse,
    LogoutRequest,
    LogoutResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)
from app.services import auth_service

router = APIRouter()


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    return await auth_service.register_user(
        db, req.pharmacy_id, req.invite_code, req.username, req.password, req.role
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    return await auth_service.login(db, req.pharmacy_id, req.username, req.password)


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    return await auth_service.refresh_access_token(db, req.refresh_token)


@router.post("/logout", response_model=LogoutResponse)
async def logout_endpoint(req: LogoutRequest, db: AsyncSession = Depends(get_db)):
    return await auth_service.logout(db, req.refresh_token)
