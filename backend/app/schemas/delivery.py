from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from app.models.order import OrderStatus

class DeliveryCreate(BaseModel):
    pickup_lat: float = Field(..., ge=-90, le=90)
    pickup_lng: float = Field(..., ge=-180, le=180)
    dropoff_lat: float = Field(..., ge=-90, le=90)
    dropoff_lng: float = Field(..., ge=-180, le=180)

class DeliveryStatusUpdate(BaseModel):
    status: OrderStatus
    driver_id: Optional[int] = None

class ManualAssignment(BaseModel):
    driver_id: int

class DeliveryResponse(BaseModel):
    id: int
    tenant_id: int
    driver_id: Optional[int] = None
    status: OrderStatus
    pickup_lat: float
    pickup_lng: float
    dropoff_lat: float
    dropoff_lng: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class AutoAssignmentRequest(BaseModel):
    order_id: int

