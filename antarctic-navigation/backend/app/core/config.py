"""Core configuration for POLARIS Antarctic Navigation System."""
import os
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "POLARIS Antarctic Navigation"
    APP_VERSION: str = "1.0.0"
    API_VERSION: str = "v1"
    DEBUG: bool = True
    SECRET_KEY: str = "dev-secret-key-change-in-production"

    # Database
    DATABASE_URL: str = "sqlite:///./polaris.db"
    
    # Celery/Redis
    REDIS_URL: str = "redis://localhost:6379/0" # Might fail without redis, will handle later

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"

    # Dataset — confirmed on this machine: D:\DHruvAI\DataSets is missing;
    # the 684-file bundle lives at D:\IAVNS\DataSets (same layout as inventory).
    DATASET_PATH: str = r"D:\IAVNS\DataSets"

    # Demo mode
    DEMO_MODE: bool = True

    # Analysis AOI (lat/lon, EPSG:4326). Full GEBCO/GLORYS span 50–75°S and 360°
    # longitude; a 5 km grid over that domain is millions of cells and is not
    # usable for interactive A*. This AOI covers the frontend demo OD pair
    # (Antarctic Peninsula, ~66°W) and the one Sentinel-1 scene (~15°W).
    ANALYSIS_LAT_MIN: float = -75.0
    ANALYSIS_LAT_MAX: float = -60.0
    ANALYSIS_LON_MIN: float = -80.0
    ANALYSIS_LON_MAX: float = -10.0

    # Shared routing/risk grid. Native AMSR2 in this bundle is 25 km (x/y step
    # 25000 m on EPSG:3412), GEBCO is ~15 arc-sec. 10 km is a runnable
    # compromise; it is a design choice, not a measured skill score.
    GRID_RESOLUTION_KM: float = 10.0

    DEFAULT_VESSEL_DRAFT_M: float = 8.0
    ICEBREAKER_CLASSES: str = "PC1,PC2,PC3,ICEBREAKER"

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000", "http://localhost:5174"]

    # Analysis
    ANALYSIS_CRS: str = "EPSG:3031"
    API_CRS: str = "EPSG:4326"

    # Safety constraints
    MAX_ICE_CONCENTRATION: float = 80.0  # percent, for non-icebreaker
    MIN_DEPTH_MARGIN_M: float = 10.0
    ICEBERG_EXCLUSION_ZONE_NM: float = 5.0

    # Risk weights (defaults)
    RISK_WEIGHT_ICE: float = 0.35
    RISK_WEIGHT_ICEBERG: float = 0.30
    RISK_WEIGHT_WEATHER: float = 0.20
    RISK_WEIGHT_BATHYMETRY: float = 0.15

    @property
    def dataset_dir(self) -> Path:
        return Path(self.DATASET_PATH)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Singleton
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        # Try to load .env from backend directory
        env_path = Path(__file__).parent.parent.parent / ".env"
        if env_path.exists():
            _settings = Settings(_env_file=str(env_path))
        else:
            _settings = Settings()
    return _settings
