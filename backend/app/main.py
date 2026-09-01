import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import create_tables, init_db
from app.api.endpoints import router as api_router

# Import ALL models so SQLAlchemy creates them
from app.models import iceberg  # noqa: F401
from app.models import route    # noqa: F401

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("iavns")

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    create_tables()
    status = settings.validate_dataset_dir()
    if status.ok:
        logger.info("IAVNS backend started. Tables created. Dataset dir: %s", status.path)
    else:
        logger.warning(
            "IAVNS backend started with NO usable dataset directory: %s. "
            "Set IAVNS_DATA_DIR in backend/.env (see backend/.env.example). "
            "Data-dependent endpoints will return clear errors until this is fixed.",
            status.message,
        )
    yield

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "IAVNS Antarctic Navigation Decision Support System. "
        "ADVISORY ONLY — not a live operational navigation system. "
        "Data are historical static files."
    ),
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/")
def read_root():
    return {
        "message": "IAVNS API is running",
        "docs": "/docs",
        "health": "/api/health",
        "mode": "HISTORICAL_DEMO",
    }


@app.get("/api/health")
def health_shortcut():
    return {"status": "ok", "version": settings.APP_VERSION}
