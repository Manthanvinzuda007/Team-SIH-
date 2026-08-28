"""Sea ice observation and forecast models."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON, func
from app.core.database import Base


class SeaIceObservation(Base):
    __tablename__ = "sea_ice_observations"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    source = Column(String(50), nullable=False)  # NSIDC, AMSR2, etc.
    grid_data_path = Column(String(500), nullable=True)  # Path to processed grid
    resolution_km = Column(Float, nullable=True)
    spatial_extent = Column(JSON, nullable=True)  # {n, s, e, w}
    data_status = Column(String(20), default="HISTORICAL")
    file_path = Column(String(500), nullable=True)  # Original source file
    provenance = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=func.now())


class SeaIceForecast(Base):
    __tablename__ = "sea_ice_forecasts"

    id = Column(Integer, primary_key=True, index=True)
    base_observation_id = Column(Integer, ForeignKey("sea_ice_observations.id"), nullable=True)
    forecast_hour = Column(Integer, nullable=False)  # 6, 12, 24
    model_type = Column(String(30), nullable=False, default="PERSISTENCE")  # PERSISTENCE, CONVLSTM, ADVECTION
    grid_data_path = Column(String(500), nullable=True)
    confidence = Column(Float, nullable=True)
    metrics = Column(JSON, nullable=True)  # {MAE, RMSE, SSIM, iou}
    created_at = Column(DateTime, default=func.now())
