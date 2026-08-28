import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import create_tables, init_db
from app.api.endpoints import router as api_router

# Import ALL models so SQLAlchemy creates them
from app.models import iceberg  # noqa: F401
from app.models import route    # noqa: F401

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("polaris")

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "POLARIS Antarctic Navigation Decision Support System. "
        "ADVISORY ONLY — not a live operational navigation system. "
        "Data are historical static files."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.on_event("startup")
def on_startup():
    init_db()
    create_tables()
    logger.info("POLARIS backend started. Tables created. Dataset path: %s",
                settings.DATASET_PATH)


@app.get("/")
def read_root():
    return {
        "message": "POLARIS API is running",
        "docs": "/docs",
        "health": "/api/health",
        "mode": "HISTORICAL_DEMO",
    }


@app.get("/api/health")
def health_shortcut():
    return {"status": "ok", "version": settings.APP_VERSION}
