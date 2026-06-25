from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from app.db.session import get_db
from app.schemas.driver import DriverCreate, DriverLocationUpdate, DriverAvailabilityUpdate, DriverResponse
from app.schemas.delivery import DeliveryResponse
from app.models.order import Order, OrderStatus
from app.services.driver_service import DriverService


router = APIRouter()

@router.post("", response_model=DriverResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=DriverResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def register_driver(
    driver_data: DriverCreate,
    db: AsyncSession = Depends(get_db)
):
    driver = await DriverService.create_driver(db, driver_data)
    return driver

@router.get("/{driver_id}", response_model=DriverResponse)
async def get_driver(
    driver_id: int,
    db: AsyncSession = Depends(get_db)
):
    driver = await DriverService.get_driver(db, driver_id)
    return driver

@router.post("/{driver_id}/location", response_model=DriverResponse)
async def update_driver_location(
    driver_id: int,
    location_data: DriverLocationUpdate,
    db: AsyncSession = Depends(get_db)
):
    driver = await DriverService.update_location(db, driver_id, location_data)
    return driver

@router.patch("/{driver_id}/availability", response_model=DriverResponse)
async def update_driver_availability(
    driver_id: int,
    availability_data: DriverAvailabilityUpdate,
    db: AsyncSession = Depends(get_db)
):
    driver = await DriverService.update_availability(db, driver_id, availability_data.is_available)
    return driver

@router.get("/{driver_id}/offers", response_model=Optional[DeliveryResponse])
async def get_active_offer(
    driver_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Order).where(
            Order.driver_id == driver_id,
            Order.status == OrderStatus.DRIVER_PENDING
        )
    )
    order = result.scalars().first()
    return order

