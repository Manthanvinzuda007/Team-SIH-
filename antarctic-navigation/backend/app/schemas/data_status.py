from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime

class DataStatusItem(BaseModel):
    name: str
    type: str
    status: str
    last_updated: Optional[datetime]
    data_age_hours: Optional[float]
    resolution: Optional[str]
    provenance: Optional[Dict[str, Any]]

class DataStatusResponse(BaseModel):
    datasets: List[DataStatusItem]
