import asyncio
import logging
from datetime import datetime, timezone, timedelta
from celery import shared_task
from app.core.celery_app import celery_app
from app.db.redis import redis_client
from app.core.geo import calculate_haversine_distance

logger = logging.getLogger("AnalyticsTask")

def run_async(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

async def _process_delivery_analytics(order_id: int):
    """
    Computes performance metrics (delivery times, ETA accuracy, stream distances)
    and persists them to Postgres analytics tables.
    """
    from app.db.session import AsyncSessionLocal
    from app.models.order import Order
    from app.models.transition import OrderStateTransition
    from app.models.analytics import TripAnalytics, DriverAnalytics, TenantAnalytics
    from app.models.attempt import AssignmentAttempt, AttemptStatus
    from sqlalchemy.future import select
    from sqlalchemy import func
    
    async with AsyncSessionLocal() as db:
        # 1. Fetch order
        order_result = await db.execute(select(Order).where(Order.id == order_id))
        order = order_result.scalars().first()
        if not order:
            logger.error(f"Order #{order_id} not found for analytics.")
            return

        # 2. Fetch all state transition audit logs for this order
        trans_res = await db.execute(
            select(OrderStateTransition).where(OrderStateTransition.order_id == order_id).order_by(OrderStateTransition.created_at.asc())
        )
        transitions = trans_res.scalars().all()
        
        timestamps = {t.to_status: t.created_at for t in transitions}
        
        created_at = order.created_at
        assigned_at = timestamps.get("ASSIGNED")
        picked_up_at = timestamps.get("PICKED_UP") or timestamps.get("IN_TRANSIT")
        delivered_at = timestamps.get("DELIVERED")

        if not delivered_at:
            logger.warning(f"Order #{order_id} not delivered yet. Skipping analytics.")
            return

        # Time metrics (in seconds)
        actual_delivery_time = (delivered_at - created_at).total_seconds()
        assignment_time = (assigned_at - created_at).total_seconds() if assigned_at else None
        pickup_delay = (picked_up_at - assigned_at).total_seconds() if (picked_up_at and assigned_at) else None

        # 3. Calculate distance traveled using the Redis locations stream
        # Fetch entries from stream:locations
        distance_traveled = 0.0
        if order.driver_id and assigned_at:
            try:
                # Retrieve all stream updates (XREAD or XRANGE)
                # For simplicity, fetch up to 1000 records of stream
                # In production we would query with start-end timestamp IDs
                start_id = int(assigned_at.timestamp() * 1000)
                end_id = int(delivered_at.timestamp() * 1000)
                
                stream_records = await redis_client.xrange("stream:locations", min=f"{start_id}-0", max=f"{end_id}-99")
                
                points = []
                for _, data in stream_records:
                    if int(data.get(b"driver_id", b"0")) == order.driver_id:
                        points.append((
                            float(data.get(b"lat")),
                            float(data.get(b"lng"))
                        ))
                
                # Sum consecutive points
                if len(points) > 1:
                    for i in range(len(points) - 1):
                        distance_traveled += calculate_haversine_distance(
                            points[i][0], points[i][1],
                            points[i+1][0], points[i+1][1]
                        )
                else:
                    # Fallback to straight-line distance if stream has insufficient points
                    distance_traveled = calculate_haversine_distance(
                        order.pickup_lat, order.pickup_lng,
                        order.dropoff_lat, order.dropoff_lng
                    )
            except Exception as stream_err:
                logger.error(f"Error calculating distance from stream: {stream_err}")
                distance_traveled = calculate_haversine_distance(
                    order.pickup_lat, order.pickup_lng,
                    order.dropoff_lat, order.dropoff_lng
                )

        # 4. Save Trip Analytics record
        trip_analytics = TripAnalytics(
            order_id=order_id,
            actual_delivery_time=actual_delivery_time,
            assignment_time=assignment_time,
            pickup_delay=pickup_delay,
            distance_traveled=distance_traveled,
            eta_accuracy=95.0 # Mock default accuracy, in production calculated against routes
        )
        db.add(trip_analytics)
        
        # 5. Update Driver Analytics aggregations
        if order.driver_id:
            # Calculate driver metrics
            total_attempts_res = await db.execute(
                select(func.count(AssignmentAttempt.id)).where(AssignmentAttempt.driver_id == order.driver_id)
            )
            total_attempts = total_attempts_res.scalar() or 1
            
            accepted_res = await db.execute(
                select(func.count(AssignmentAttempt.id)).where(
                    AssignmentAttempt.driver_id == order.driver_id,
                    AssignmentAttempt.status == AttemptStatus.ACCEPTED
                )
            )
            accepted_count = accepted_res.scalar() or 0
            
            rejected_res = await db.execute(
                select(func.count(AssignmentAttempt.id)).where(
                    AssignmentAttempt.driver_id == order.driver_id,
                    AssignmentAttempt.status == AttemptStatus.REJECTED
                )
            )
            rejected_count = rejected_res.scalar() or 0
            
            timeout_res = await db.execute(
                select(func.count(AssignmentAttempt.id)).where(
                    AssignmentAttempt.driver_id == order.driver_id,
                    AssignmentAttempt.status == AttemptStatus.TIMEOUT
                )
            )
            timeout_count = timeout_res.scalar() or 0

            d_analytics_res = await db.execute(select(DriverAnalytics).where(DriverAnalytics.driver_id == order.driver_id))
            d_analytics = d_analytics_res.scalars().first()
            if not d_analytics:
                d_analytics = DriverAnalytics(driver_id=order.driver_id)
                db.add(d_analytics)
                
            d_analytics.acceptance_rate = (accepted_count / total_attempts) * 100.0
            d_analytics.rejection_rate = (rejected_count / total_attempts) * 100.0
            d_analytics.timeout_rate = (timeout_count / total_attempts) * 100.0
            
        # 6. Update Tenant Analytics aggregations
        t_analytics_res = await db.execute(select(TenantAnalytics).where(TenantAnalytics.tenant_id == order.tenant_id))
        t_analytics = t_analytics_res.scalars().first()
        if not t_analytics:
            t_analytics = TenantAnalytics(tenant_id=order.tenant_id, total_deliveries=0)
            db.add(t_analytics)
            
        t_analytics.total_deliveries += 1
        
        await db.commit()
        logger.info(f"Analytics successfully populated for Order #{order_id}")

async def _hourly_usage_aggregation():
    """Reads usage counts from Redis and flushes aggregated metrics to Postgres."""
    from app.db.session import AsyncSessionLocal
    from app.models.tenant import Tenant
    from app.models.analytics import TenantUsageHourly
    from sqlalchemy.future import select
    
    current_time = datetime.now(timezone.utc)
    hour_floor = current_time.replace(minute=0, second=0, microsecond=0)
    date_key = hour_floor.strftime("%Y-%m-%d")
    
    async with AsyncSessionLocal() as db:
        tenants_res = await db.execute(select(Tenant))
        tenants = tenants_res.scalars().all()
        
        for tenant in tenants:
            redis_key = f"usage:{tenant.id}:{date_key}"
            count_str = await redis_client.get(redis_key)
            count = int(count_str) if count_str else 0
            
            if count > 0:
                # Log hourly aggregation
                usage_entry = TenantUsageHourly(
                    tenant_id=tenant.id,
                    hour=hour_floor,
                    request_count=count
                )
                db.add(usage_entry)
                logger.info(f"Hourly usage aggregate persisted for Tenant {tenant.id}: {count} requests.")
                
        await db.commit()

@celery_app.task(queue="analytics")
def process_delivery_analytics_task(order_id: int, pushed_at: float = None):
    """Processes performance metrics for a completed order."""
    logger.info(f"Processing delivery analytics task for Order #{order_id}, pushed_at={pushed_at}")
    run_async(_process_delivery_analytics(order_id))


@celery_app.task(queue="analytics")
def hourly_usage_aggregation_task():
    """Schedules cron aggregation of tenant daily request usage."""
    run_async(_hourly_usage_aggregation())
