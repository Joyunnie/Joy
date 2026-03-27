from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine
from app.routers import alerts, auth, drugs, inventory, narcotics, otc, predictions, receipt_ocr, shelf_layouts, sync, thresholds
from app.services.ocr_engine import init_ocr_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    allow_origins=["http://localhost:5173"],
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


@app.get("/health")
async def health():
    return {"status": "ok"}
