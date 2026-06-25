import json
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional
from app.models.driver import Driver, DriverStatus
from app.models.order import Order, OrderStatus
from app.schemas.driver import DriverCreate, DriverLocationUpdate
from app.core.exceptions import DriverNotFoundError
from app.core.geo import calculate_haversine_distance
from app.db.redis import redis_client

class DriverService:
    @staticmethod
    async def create_driver(db: AsyncSession, driver_data: DriverCreate) -> Driver:
        driver = Driver(
            name=driver_data.name,
            phone=driver_data.phone,
            status=DriverStatus.OFFLINE,
            rating=5.0,
            is_available=True,
            last_seen_at=datetime.now(timezone.utc)
        )
        db.add(driver)
        await db.commit()
        await db.refresh(driver)
        return driver

    @staticmethod
    async def get_driver(db: AsyncSession, driver_id: int) -> Driver:
        result = await db.execute(select(Driver).where(Driver.id == driver_id))
        driver = result.scalars().first()
        if not driver:
            raise DriverNotFoundError()
        return driver

    @staticmethod
    async def update_location(db: AsyncSession, driver_id: int, location: DriverLocationUpdate) -> Driver:
        # 1. Fetch driver
        result = await db.execute(select(Driver).where(Driver.id == driver_id))
        driver = result.scalars().first()
        if not driver:
            raise DriverNotFoundError()

        current_time = datetime.now(timezone.utc)
        timestamp_str = current_time.isoformat()

        # Update last_seen_at heartbeat
        driver.last_seen_at = current_time

        # 2. Always publish to Redis Stream for analytics/replay
        location_data = {
            "driver_id": str(driver_id),
            "lat": str(location.latitude),
            "lng": str(location.longitude),
            "timestamp": timestamp_str
        }
        await redis_client.xadd("stream:locations", location_data, id="*")

        # 3. Fetch any active deliveries for this driver to publish to Redis Pub/Sub
        active_orders_result = await db.execute(
            select(Order).where(
                Order.driver_id == driver_id,
                Order.status.in_([OrderStatus.ASSIGNED, OrderStatus.PICKED_UP, OrderStatus.IN_TRANSIT])
            )
        )
        active_orders = active_orders_result.scalars().all()
        
        # Publish to Pub/Sub channels for all active deliveries and cache location in Redis
        from app.services.route_service import RouteService
        for order in active_orders:
            await RouteService.recalculate_eta(db, order.id, location.latitude, location.longitude)

        # Refresh driver from DB since nested commits in recalculate_eta might have expired it
        await db.refresh(driver)

        # Update Redis GEO spatial index for ONLINE & AVAILABLE drivers
        # Force ONLINE status if driver was OFFLINE during a ping
        resolved_status = driver.status
        if resolved_status == DriverStatus.OFFLINE:
            resolved_status = DriverStatus.ONLINE

        if resolved_status == DriverStatus.ONLINE and driver.is_available:
            # Add or update member in GEO index (x=longitude, y=latitude, member=driver_id)
            await redis_client.geoadd("drivers:active", (location.longitude, location.latitude, str(driver_id)))
        else:
            await redis_client.zrem("drivers:active", str(driver_id))

        # 4. Evaluate Optimized Database Persistence Rules
        should_persist = False
        
        if driver.status != resolved_status:
            driver.status = resolved_status
            should_persist = True

        # Rule B: Time Threshold (> 10 seconds elapsed)
        if driver.updated_at:
            time_elapsed = (current_time - driver.updated_at.replace(tzinfo=timezone.utc)).total_seconds()
            if time_elapsed > 10.0:
                should_persist = True
        else:
            should_persist = True

        # Rule C: Distance Threshold (> 20 meters moved)
        if driver.current_lat is not None and driver.current_lng is not None:
            distance_moved = calculate_haversine_distance(
                driver.current_lat, driver.current_lng,
                location.latitude, location.longitude
            )
            if distance_moved > 20.0:
                should_persist = True
        else:
            should_persist = True

        # 5. Persist to PostgreSQL only if criteria is met
        if should_persist:
            driver.current_lat = location.latitude
            driver.current_lng = location.longitude
            driver.updated_at = current_time
            await db.commit()
            await db.refresh(driver)
        else:
            # Still commit heartbeat update
            await db.commit()
            
        return driver

    @staticmethod
    async def update_availability(db: AsyncSession, driver_id: int, is_available: bool) -> Driver:
        result = await db.execute(select(Driver).where(Driver.id == driver_id))
        driver = result.scalars().first()
        if not driver:
            raise DriverNotFoundError()
            
        driver.is_available = is_available
        
        # Sync Redis GEO index
        if driver.status == DriverStatus.ONLINE and is_available and driver.current_lat is not None and driver.current_lng is not None:
            await redis_client.geoadd("drivers:active", (driver.current_lng, driver.current_lat, str(driver_id)))
        else:
            await redis_client.zrem("drivers:active", str(driver_id))
            
        await db.commit()
        await db.refresh(driver)
        return driver
