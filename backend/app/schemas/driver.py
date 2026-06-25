from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from app.models.driver import DriverStatus

class DriverCreate(BaseModel):
    name: str
    phone: str

class DriverLocationUpdate(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)

class DriverAvailabilityUpdate(BaseModel):
    is_available: bool

class DriverResponse(BaseModel):
    id: int
    name: str
    phone: str
    status: DriverStatus
    current_lat: Optional[float] = None
    current_lng: Optional[float] = None
    rating: Optional[float] = 5.0
    is_available: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
