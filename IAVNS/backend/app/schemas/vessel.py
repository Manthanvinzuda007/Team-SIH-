from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

class VesselBase(BaseModel):
    name: str
    imo_number: Optional[str] = None
    ice_class: str = "IC"
    draft_m: float = 8.0
    beam_m: Optional[float] = None
    length_m: Optional[float] = None
    fuel_capacity_tonnes: float = 5000.0
    speed_max_knots: float = 15.0
    speed_cruise_knots: float = 12.0
    max_wind_knots: float = 50.0
    max_wave_m: float = 6.0

class VesselCreate(VesselBase):
    pass

class VesselResponse(VesselBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
