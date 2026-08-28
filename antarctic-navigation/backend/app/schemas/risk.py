from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime

class RiskComponents(BaseModel):
    ice_concentration_risk: float
    iceberg_proximity_risk: float
    weather_risk: float
    bathymetry_risk: float
    composite: float

class RiskCell(BaseModel):
    lat: float
    lon: float
    risk_score: float
    risk_level: str
    components: RiskComponents

class RiskMapResponse(BaseModel):
    grid: List[RiskCell]
    timestamp: datetime
    resolution_km: float
    provenance: Dict[str, Any]
