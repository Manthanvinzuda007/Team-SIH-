from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime

class IcebergResponse(BaseModel):
    id: int
    name: str
    lat: float
    lon: float
    size_length_nm: Optional[float]
    size_width_nm: Optional[float]
    source: str
    confidence: float
    status: str
    detected_time: Optional[datetime]
    speed_knots: Optional[float]
    heading_deg: Optional[float]
    risk_level: Optional[str] = None # Calculated by risk engine

    class Config:
        from_attributes = True

class TrajectoryPoint(BaseModel):
    lat: float
    lon: float
    timestamp: datetime

class IcebergTrajectoryResponse(BaseModel):
    iceberg_id: int
    historical_points: List[TrajectoryPoint]
    predicted_points: List[TrajectoryPoint]
    confidence_corridor_km: Optional[float]
    model_type: str
    metrics: Optional[Dict[str, float]]
