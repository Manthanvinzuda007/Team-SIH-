"""SavedRoute database model for route persistence."""
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, func
from app.core.database import Base


class SavedRoute(Base):
    __tablename__ = "saved_routes"

    id = Column(Integer, primary_key=True, index=True)
    mode = Column(String(20), nullable=False)
    origin_lat = Column(Float, nullable=True)
    origin_lon = Column(Float, nullable=True)
    dest_lat = Column(Float, nullable=True)
    dest_lon = Column(Float, nullable=True)
    distance_nm = Column(Float, nullable=True)
    eta_hours = Column(Float, nullable=True)
    risk_score = Column(Float, nullable=True)
    path_points = Column(JSON, nullable=False, default=list)
    vessel_config = Column(JSON, nullable=True)
    data_snapshot = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "mode": self.mode,
            "origin": {"lat": self.origin_lat, "lon": self.origin_lon},
            "destination": {"lat": self.dest_lat, "lon": self.dest_lon},
            "distance_nm": self.distance_nm,
            "estimated_time_hours": self.eta_hours,
            "risk_score": self.risk_score,
            "path_points": self.path_points or [],
            "vessel_config": self.vessel_config,
            "data_snapshot": self.data_snapshot,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
