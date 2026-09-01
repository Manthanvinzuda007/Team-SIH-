"""Core configuration for POLARIS Antarctic Navigation System."""
import os
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "IAVNS Antarctic Navigation"
    APP_FULL_NAME: str = "Indian Antarctica Vessels Navigation System"
    APP_VERSION: str = "1.0.0"
    API_VERSION: str = "v1"
    DEBUG: bool = True
    SECRET_KEY: str = "dev-secret-key-change-in-production"

    # Database
    DATABASE_URL: str = "sqlite:///./polaris.db"


    # Dataset directory — configurable via IAVNS_DATA_DIR env var (or .env).
    # Machine-specific absolute paths (e.g. D:\IAVNS\DataSets) must never be
    # hard-coded here; every machine sets its own IAVNS_DATA_DIR.
    # Default is a relative path so the project runs out-of-the-box from the
    # repo root as long as a `DataSets/` folder (or symlink) exists there.
    IAVNS_DATA_DIR: str = "./DataSets"

    # Legacy alias — some older configs / scripts referenced DATASET_PATH.
    # If DATASET_PATH is explicitly set (env var or .env) it takes priority
    # over IAVNS_DATA_DIR for backward compatibility; otherwise it mirrors it.
    DATASET_PATH: Optional[str] = None

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

    # Risk weights (defaults). Sum to 1.0 so the composite stays in [0,100]
    # given each component is itself clipped to [0,100]. RISK_WEIGHT_ICEBERG
    # covers BOTH the current-position (BYU/SAR) proximity term and the
    # LSTM-predicted-position proximity term (Part 2 Phase 7/8) — see
    # risk_service.py for how the two are combined before this weight is
    # applied. RISK_WEIGHT_CURRENT is new in Part 2 (ocean-current hazard,
    # separate from the current-aware *routing* cost term in route_service.py,
    # which rewards/penalizes by direction rather than magnitude).
    RISK_WEIGHT_ICE: float = 0.30
    RISK_WEIGHT_ICEBERG: float = 0.25
    RISK_WEIGHT_WEATHER: float = 0.20
    RISK_WEIGHT_BATHYMETRY: float = 0.15
    RISK_WEIGHT_CURRENT: float = 0.10

    # Ocean-current risk reference: current speed (m/s) mapped to 100 risk.
    # Design choice (not a measured skill score) — GLORYS surface currents in
    # this bundle's domain are mostly sub-1 m/s; see route_service.py
    # CURRENT_REFERENCE_MS for the (different) routing-cost normalizer.
    CURRENT_RISK_REFERENCE_MS: float = 1.0

    # Iceberg trajectory forecast horizons supported end-to-end (hours).
    # Mirrors app.ml.iceberg_trajectory.HORIZONS_DAYS (1, 3, 7 days).
    ICEBERG_FORECAST_HORIZONS_H: str = "24,72,168"

    # Sea-ice nowcast horizon used to build the "future ice risk" advisory
    # layer fed into route-risk (Part 2 Phase 6). The 8-day AMSR2 corpus only
    # supports a ~24-48h honest horizon (see sea_ice_forecast.py).
    SEA_ICE_NOWCAST_RISK_HORIZON_H: float = 24.0

    # Routing cost-function tuning (design choices, not measured constants —
    # see route_service.py for how each is used).
    # Typical GLORYS surface current magnitude in this dataset's domain is a
    # few tenths of a m/s; used only to normalize the along-track current
    # cost term into a roughly 0-1 range, not as a physical claim.
    CURRENT_REFERENCE_MS: float = 0.5
    # Extra proportional speed reduction applied to icebreaking-capable
    # (non-dedicated-icebreaker) vessels when transiting higher ice
    # concentrations, on top of the generic ice speed penalty. Configurable
    # decision-support assumption, not a certified performance curve.
    ICEBREAKING_SPEED_PENALTY_FACTOR: float = 0.5

    @property
    def dataset_dir(self) -> Path:
        """Resolved dataset directory.

        DATASET_PATH (legacy) wins if explicitly set; otherwise IAVNS_DATA_DIR
        is used. Relative paths are resolved against the backend/ directory
        (the directory containing this package), not the process cwd, so the
        app behaves the same whether started from backend/ or the repo root.
        """
        raw = self.DATASET_PATH or self.IAVNS_DATA_DIR
        p = Path(raw)
        if not p.is_absolute():
            backend_root = Path(__file__).parent.parent.parent
            p = (backend_root / p).resolve()
        return p

    def validate_dataset_dir(self) -> "DatasetDirStatus":
        """Check that the configured dataset directory exists and is non-empty.

        Never raises — callers decide how to surface the result (log a
        warning at startup, return a clear API error, etc). Loaders already
        degrade gracefully (NaN fields) when files are missing, but we want
        an explicit, honest status rather than silently pretending data
        exists.
        """
        d = self.dataset_dir
        exists = d.exists()
        is_dir = d.is_dir() if exists else False
        has_files = False
        if is_dir:
            try:
                has_files = any(d.iterdir())
            except OSError:
                has_files = False
        ok = exists and is_dir and has_files
        if not exists:
            message = f"Dataset directory does not exist: {d}"
        elif not is_dir:
            message = f"Dataset path is not a directory: {d}"
        elif not has_files:
            message = f"Dataset directory is empty: {d}"
        else:
            message = f"Dataset directory OK: {d}"
        return DatasetDirStatus(
            path=str(d), exists=exists, is_dir=is_dir, has_files=has_files,
            ok=ok, message=message,
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


class DatasetDirStatus:
    """Plain result object for Settings.validate_dataset_dir()."""

    __slots__ = ("path", "exists", "is_dir", "has_files", "ok", "message")

    def __init__(self, path: str, exists: bool, is_dir: bool, has_files: bool,
                 ok: bool, message: str):
        self.path = path
        self.exists = exists
        self.is_dir = is_dir
        self.has_files = has_files
        self.ok = ok
        self.message = message

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "exists": self.exists,
            "is_dir": self.is_dir,
            "has_files": self.has_files,
            "ok": self.ok,
            "message": self.message,
        }


class DatasetNotConfiguredError(RuntimeError):
    """Raised when a route/data-dependent endpoint needs data that is missing."""

    def __init__(self, status: "DatasetDirStatus"):
        self.status = status
        super().__init__(status.message)


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


def reset_settings_cache() -> None:
    """Test/tooling helper — forces get_settings() to reload from env."""
    global _settings
    _settings = None
