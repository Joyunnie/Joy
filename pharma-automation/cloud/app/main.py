import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from app.config import settings
from app.database import engine
from app.exceptions import ServiceError
from app.rate_limit import limiter
from app.routers import alerts, auth, canisters, drugs, inventory, narcotics, otc, predictions, receipt_ocr, shelf_layouts, sync, thresholds, todos
from app.services.ocr_engine import init_ocr_engine

logger = logging.getLogger(__name__)


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

# --- Rate limiting ---
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please try again later."},
    )


@app.exception_handler(ServiceError)
async def service_error_handler(request, exc: ServiceError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://220.71.178.7",
        "http://220.71.178.7:80",
        "http://localhost:3000",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
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
app.include_router(todos.router, prefix="/api/v1/todos", tags=["todos"])
app.include_router(canisters.router, prefix="/api/v1/canisters", tags=["canisters"])


@app.get("/health")
async def health():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "detail": "Database unreachable"},
        )
