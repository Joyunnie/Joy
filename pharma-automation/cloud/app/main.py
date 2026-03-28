from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine
from app.routers import alerts, auth, drugs, inventory, narcotics, otc, predictions, prescription_ocr, receipt_ocr, rpa_commands, shelf_layouts, sync, thresholds
from app.services.ocr_engine import init_ocr_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # JWT 시크릿 검증
    if not settings.jwt_secret_key or settings.jwt_secret_key == "CHANGE-ME-IN-PRODUCTION":
        raise ValueError(
            "PHARMA_JWT_SECRET_KEY must be set. "
            "Generate one with: openssl rand -hex 32"
        )
    # P32: OCR 엔진 초기화 (서버 시작 시)
    init_ocr_engine(settings.ocr_engine, settings.google_vision_api_key or None)
    yield
    await engine.dispose()


app = FastAPI(
    title="Pharmacy Automation Cloud API",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(sync.router, prefix="/api/v1/sync", tags=["sync"])
app.include_router(alerts.router, prefix="/api/v1/alerts", tags=["app-dev"])
app.include_router(inventory.router, prefix="/api/v1/inventory", tags=["app-dev"])
app.include_router(predictions.router, prefix="/api/v1/predictions", tags=["app-dev"])
app.include_router(otc.router)
app.include_router(narcotics.router)
app.include_router(drugs.router)
app.include_router(thresholds.router)
app.include_router(shelf_layouts.router)
app.include_router(receipt_ocr.router)
app.include_router(prescription_ocr.router)
app.include_router(rpa_commands.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
