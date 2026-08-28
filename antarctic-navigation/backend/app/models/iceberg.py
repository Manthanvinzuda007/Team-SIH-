"""Iceberg and trajectory database models."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON, func
from app.core.database import Base


class Iceberg(Base):
    __tablename__ = "icebergs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, index=True)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    detected_time = Column(DateTime, nullable=True)
    size_length_nm = Column(Float, nullable=True)  # Major axis in nautical miles
    size_width_nm = Column(Float, nullable=True)   # Minor axis in nautical miles
    source = Column(String(50), nullable=False)     # SAR, BYU, NIC
    confidence = Column(Float, default=0.5)         # 0-1
    status = Column(String(20), default="HISTORICAL")  # CONFIRMED, CANDIDATE, HISTORICAL
    speed_knots = Column(Float, nullable=True)
    heading_deg = Column(Float, nullable=True)
    last_updated = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "lat": self.lat,
            "lon": self.lon,
            "detected_time": self.detected_time.isoformat() if self.detected_time else None,
            "size_length_nm": self.size_length_nm,
            "size_width_nm": self.size_width_nm,
            "source": self.source,
            "confidence": self.confidence,
            "status": self.status,
            "speed_knots": self.speed_knots,
            "heading_deg": self.heading_deg,
        }


class IcebergTrajectory(Base):
    __tablename__ = "iceberg_trajectories"

    id = Column(Integer, primary_key=True, index=True)
    iceberg_id = Column(Integer, ForeignKey("icebergs.id"), nullable=False, index=True)
    trajectory_type = Column(String(20), nullable=False)  # HISTORICAL, PREDICTED
    points = Column(JSON, nullable=False)  # [{lat, lon, timestamp}, ...]
    confidence_corridor_km = Column(Float, nullable=True)
    model_type = Column(String(30), default="PHYSICS")  # PHYSICS, LSTM, HYBRID
    metrics = Column(JSON, nullable=True)  # {ADE, FDE}
    created_at = Column(DateTime, default=func.now())
