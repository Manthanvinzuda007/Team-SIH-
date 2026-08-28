"""Vessel database model."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, func
from app.core.database import Base


class Vessel(Base):
    __tablename__ = "vessels"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    imo_number = Column(String(20), unique=True, nullable=True)
    ice_class = Column(String(20), nullable=False, default="IC")  # PC1-PC7, IA_SUPER, IA, IB, IC
    draft_m = Column(Float, nullable=False, default=8.0)
    beam_m = Column(Float, nullable=True)
    length_m = Column(Float, nullable=True)
    fuel_capacity_tonnes = Column(Float, default=5000.0)
    speed_max_knots = Column(Float, default=15.0)
    speed_cruise_knots = Column(Float, default=12.0)
    max_wind_knots = Column(Float, default=50.0)
    max_wave_m = Column(Float, default=6.0)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "imo_number": self.imo_number,
            "ice_class": self.ice_class,
            "draft_m": self.draft_m,
            "beam_m": self.beam_m,
            "length_m": self.length_m,
            "fuel_capacity_tonnes": self.fuel_capacity_tonnes,
            "speed_max_knots": self.speed_max_knots,
            "speed_cruise_knots": self.speed_cruise_knots,
            "max_wind_knots": self.max_wind_knots,
            "max_wave_m": self.max_wave_m,
        }
