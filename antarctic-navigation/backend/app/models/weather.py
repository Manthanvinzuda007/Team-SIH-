"""Weather observation model."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, func
from app.core.database import Base


class WeatherObservation(Base):
    __tablename__ = "weather_observations"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    source = Column(String(50), nullable=False)
    wind_speed_ms = Column(Float, nullable=True)
    wind_direction_deg = Column(Float, nullable=True)
    temperature_k = Column(Float, nullable=True)
    pressure_pa = Column(Float, nullable=True)
    wave_height_m = Column(Float, nullable=True)
    spatial_extent = Column(JSON, nullable=True)
    grid_data_path = Column(String(500), nullable=True)
    data_status = Column(String(20), default="HISTORICAL")
    created_at = Column(DateTime, default=func.now())
