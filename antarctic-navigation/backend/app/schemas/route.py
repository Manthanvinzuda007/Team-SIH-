"""Route request/response schemas.

Units:
  distance_nm   – nautical miles (haversine)
  time_hours    – decimal hours at base_speed_knots
  fuel_tonnes   – proxy estimate (not engine simulation)
  risk_score    – 0-100 composite
  safety_score  – 0-100 (= 100 - risk_score for A* routes)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class Point(BaseModel):
    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)


class VesselConfig(BaseModel):
    """Explicit vessel capability model.

    ice_class and icebreaking_capable are SEPARATE concepts.
    A PC1-class vessel is NOT automatically a dedicated icebreaker.
    """
    ice_class: Optional[str] = None          # e.g. PC1, PC2, PC3, IA, IB, IC
    icebreaking_capable: bool = False        # vessel has icebreaking capability
    dedicated_icebreaker: bool = False       # vessel is a dedicated icebreaker
    draft_m: float = Field(default=8.0, gt=0.0, le=30.0)
    max_speed_knots: float = Field(default=12.0, gt=0.0, le=40.0)
    # Legacy field — kept for backward compat but not used for routing logic
    icebreaker: Optional[bool] = None

    @model_validator(mode="after")
    def sync_legacy_icebreaker(self) -> "VesselConfig":
        """If legacy `icebreaker=True` was sent, treat as dedicated_icebreaker."""
        if self.icebreaker is True and not self.dedicated_icebreaker:
            object.__setattr__(self, "dedicated_icebreaker", True)
            object.__setattr__(self, "icebreaking_capable", True)
        return self


class RouteOptimizeRequest(BaseModel):
    origin: Point
    destination: Point
    vessel_id: Optional[int] = None
    vessel_config: Optional[VesselConfig] = None
    departure_time: Optional[datetime] = None   # now optional with default=now
    safety_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    fuel_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    mode: Optional[str] = None

    @model_validator(mode="after")
    def default_departure(self) -> "RouteOptimizeRequest":
        if self.departure_time is None:
            object.__setattr__(self, "departure_time", datetime.utcnow())
        return self


class RouteResponse(BaseModel):
    model_config = {"protected_namespaces": (), "from_attributes": True}

    id: Optional[int] = None
    mode: str
    path_points: List[Point]
    distance_nm: float
    estimated_time_hours: float
    base_speed_knots: float = 12.0
    fuel_tonnes: float
    fuel_model: str = "distance_proxy_0.13t_per_nm"
    safety_score: Optional[float] = None       # None for fallback routes
    risk_score: Optional[float] = None
    ice_encounters: int = 0
    explanation_text: str = ""
    weights: Dict[str, float] = {}
    constraints: Optional[Dict[str, Any]] = None
    fallback: bool = False
    fallback_reason: Optional[str] = None
    computed_at: datetime
    data_valid_time: str = "2026-08-08 (AMSR2 last frame)"
    provenance: Optional[Dict[str, Any]] = None


class RouteComparisonResponse(BaseModel):
    routes: List[RouteResponse]
    vessel_config: Optional[Dict[str, Any]] = None
    computed_at: Optional[str] = None
