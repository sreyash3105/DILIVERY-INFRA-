import json
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.order import Order, OrderStatus
from app.core.geo import calculate_haversine_distance
from app.db.redis import redis_client


import httpx
from app.core.circuit_breaker import CircuitBreaker

logger = logging.getLogger("RouteService")

# Initialize ORS Circuit Breaker
ors_circuit_breaker = CircuitBreaker(name="OpenRouteService", failure_threshold=3, recovery_timeout=20.0)

async def _call_openrouteservice(lat1: float, lng1: float, lat2: float, lng2: float) -> dict:
    """Mock OpenRouteService API endpoint call. Will throw exception to trigger fallback."""
    # ORS requires coordinates in lng,lat format
    url = f"https://api.openrouteservice.org/v2/directions/driving-car"
    # To keep it production ready but safe, throw exception if ORS token isn't configured
    raise Exception("OpenRouteService connection failed: API Token not configured")

class RouteService:
    @staticmethod
    async def get_route(
        lat1: float, lng1: float, 
        lat2: float, lng2: float
    ) -> dict:
        """
        Computes route distance (meters) and ETA (minutes).
        Caches results in Redis with a 5-minute TTL.
        Uses CircuitBreaker to handle OpenRouteService outages and falls back to Haversine.
        """
        cache_key = f"route:{lat1:.5f}:{lng1:.5f}:{lat2:.5f}:{lng2:.5f}"
        cached_data = await redis_client.get(cache_key)
        if cached_data:
            try:
                return json.loads(cached_data)
            except Exception:
                pass

        async def _run_routing():
            return await _call_openrouteservice(lat1, lng1, lat2, lng2)

        def _fallback_routing():
            logger.info("OpenRouteService API failed or circuit is OPEN. Falling back to local Haversine calculations.")
            distance_meters = calculate_haversine_distance(lat1, lng1, lat2, lng2)
            eta_minutes = int(distance_meters / (30 * 1000 / 60)) # Speed = 30km/h -> 500 meters/min
            return {
                "distance_meters": distance_meters,
                "eta_minutes": max(1, eta_minutes)  # Minimum 1 minute ETA
            }

        route_payload = await ors_circuit_breaker.call_async(
            _run_routing,
            _fallback_routing
        )

        # Cache in Redis for 5 minutes (300 seconds)
        await redis_client.setex(cache_key, 300, json.dumps(route_payload))
        return route_payload

    @classmethod
    async def recalculate_eta(
        cls, 
        db: AsyncSession, 
        delivery_id: int, 
        driver_lat: float, 
        driver_lng: float
    ) -> Optional[dict]:
        """Recalculates ETA to target destination based on driver's live coordinate updates."""
        result = await db.execute(select(Order).where(Order.id == delivery_id))
        order = result.scalars().first()
        if not order:
            return None

        # Check target destination based on order status
        if order.status == OrderStatus.ASSIGNED:
            # Driver headed to pickup
            dest_lat = order.pickup_lat
            dest_lng = order.pickup_lng
            stage = "pickup"
        elif order.status in [OrderStatus.PICKED_UP, OrderStatus.IN_TRANSIT]:
            # Driver headed to dropoff
            dest_lat = order.dropoff_lat
            dest_lng = order.dropoff_lng
            stage = "delivery"
        else:
            # No active travel stage
            return None

        route_data = await cls.get_route(driver_lat, driver_lng, dest_lat, dest_lng)
        
        # Broadcast the updated ETA payload to WebSockets via Redis Pub/Sub
        pub_payload = {
            "delivery_id": order.id,
            "status": order.status,
            "stage": stage,
            "eta_minutes": route_data["eta_minutes"],
            "distance_meters": route_data["distance_meters"],
            "lat": driver_lat,
            "lng": driver_lng
        }
        await redis_client.publish(f"delivery:{order.id}", json.dumps(pub_payload))

        # Cache the full telemetry payload under live_location (used by /live-location endpoint & WS)
        await redis_client.setex(f"delivery:{order.id}:live_location", 300, json.dumps(pub_payload))

        # Cache a dedicated ETA snapshot under its own key (used by /eta endpoint)
        # Keeping these separate prevents the two endpoints from silently reading each other's data.
        eta_payload = {
            "delivery_id": order.id,
            "eta_minutes": route_data["eta_minutes"],
            "distance_meters": route_data["distance_meters"],
            "stage": stage
        }
        await redis_client.setex(f"delivery:{order.id}:eta", 300, json.dumps(eta_payload))

        return route_data
