"""Dataset status model for data provenance tracking."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, func
from app.core.database import Base


class DatasetStatus(Base):
    __tablename__ = "dataset_status"

    id = Column(Integer, primary_key=True, index=True)
    dataset_name = Column(String(100), nullable=False, unique=True)
    dataset_type = Column(String(30), nullable=False)  # SENTINEL1, NSIDC, GLORYS, GEBCO, ERA5, BYU
    source_file = Column(String(500), nullable=True)
    last_updated = Column(DateTime, nullable=True)
    data_age_hours = Column(Float, nullable=True)
    status = Column(String(20), default="UNAVAILABLE")  # LIVE, RECENT, STALE, HISTORICAL, UNAVAILABLE, ERROR
    resolution = Column(String(50), nullable=True)
    spatial_extent = Column(JSON, nullable=True)
    variables = Column(JSON, nullable=True)
    provenance = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=func.now())
