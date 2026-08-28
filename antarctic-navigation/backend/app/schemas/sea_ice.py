from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime

class SeaIceCurrentResponse(BaseModel):
    timestamp: datetime
    source: str
    concentration_grid: Optional[List[List[float]]] = None # Or path/reference if large
    resolution_km: Optional[float] = None
    spatial_extent: Optional[Dict[str, float]] = None
    data_status: str
    provenance: Optional[Dict[str, Any]] = None

class SeaIceForecastRequest(BaseModel):
    forecast_hours: List[int] = [6, 12, 24]
    include_uncertainty: bool = False

class ForecastItem(BaseModel):
    forecast_hour: int
    data_grid: Optional[List[List[float]]] = None
    confidence: Optional[float] = None
    model_type: str
    metrics: Optional[Dict[str, float]] = None

class SeaIceForecastResponse(BaseModel):
    forecasts: List[ForecastItem]
