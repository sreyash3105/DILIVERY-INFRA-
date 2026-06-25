from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Dict, Any
from app.db.session import get_db
from app.models.tenant import Tenant
from app.models.driver import Driver
from app.models.order import Order, OrderStatus
from app.models.analytics import TripAnalytics, DriverAnalytics, TenantAnalytics, TenantUsageHourly
from app.dependencies.auth import get_current_tenant
from app.db.redis import redis_client

router = APIRouter()

@router.get("/tenant")
async def get_tenant_analytics(
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant)
):
    """Returns aggregated SaaS metrics and usage data for the current tenant."""
    # 1. Fetch Tenant Aggregated Analytics
    analytics_result = await db.execute(
        select(TenantAnalytics).where(TenantAnalytics.tenant_id == tenant.id)
    )
    t_analytics = analytics_result.scalars().first()
    
    # 2. Fetch Hourly Aggregates (last 24 hours)
    hourly_result = await db.execute(
        select(TenantUsageHourly)
        .where(TenantUsageHourly.tenant_id == tenant.id)
        .order_by(TenantUsageHourly.hour.desc())
        .limit(24)
    )
    hourly_records = hourly_result.scalars().all()
    hourly_data = [
        {"hour": r.hour.isoformat(), "requests": r.request_count} for r in hourly_records
    ]

    # 3. Get Current Month Request Quota Status
    from datetime import datetime, timezone
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    monthly_usage_str = await redis_client.get(f"usage:{tenant.id}:monthly:{current_month}")
    monthly_usage = int(monthly_usage_str) if monthly_usage_str else 0

    return {
        "tenant_id": tenant.id,
        "tenant_name": tenant.name,
        "plan_name": tenant.plan_name,
        "rate_limit_per_minute": tenant.rate_limit_per_minute,
        "monthly_quota": tenant.monthly_quota,
        "monthly_usage": monthly_usage,
        "quota_exceeded_at": tenant.quota_exceeded_at.isoformat() if tenant.quota_exceeded_at else None,
        "metrics": {
            "total_deliveries": t_analytics.total_deliveries if t_analytics else 0,
            "avg_delivery_time": t_analytics.avg_delivery_time if t_analytics else 0.0,
            "avg_assignment_time": t_analytics.avg_assignment_time if t_analytics else 0.0,
            "notification_success_rate": t_analytics.notification_success_rate if t_analytics else 100.0,
            "driver_acceptance_rate": t_analytics.driver_acceptance_rate if t_analytics else 100.0,
        },
        "hourly_usage": hourly_data
    }

@router.get("/drivers/{driver_id}")
async def get_driver_analytics(
    driver_id: int,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant)
):
    """Returns analytics profile and acceptance statistics for a specific driver."""
    result = await db.execute(
        select(DriverAnalytics).where(DriverAnalytics.driver_id == driver_id)
    )
    d_analytics = result.scalars().first()
    if not d_analytics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analytics profile not found for this driver"
        )
    return {
        "driver_id": driver_id,
        "acceptance_rate": d_analytics.acceptance_rate,
        "rejection_rate": d_analytics.rejection_rate,
        "timeout_rate": d_analytics.timeout_rate,
        "avg_pickup_time": d_analytics.avg_pickup_time,
        "avg_delivery_time": d_analytics.avg_delivery_time,
        "eta_accuracy": d_analytics.eta_accuracy
    }

@router.get("/deliveries")
async def get_deliveries_analytics(
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant)
):
    """Returns detailed analytics stats for all completed deliveries."""
    # Query TripAnalytics joined on Order to restrict by Tenant
    result = await db.execute(
        select(TripAnalytics, Order)
        .join(Order, TripAnalytics.order_id == Order.id)
        .where(Order.tenant_id == tenant.id)
        .order_by(TripAnalytics.created_at.desc())
    )
    
    analytics_list = []
    for trip_an, order in result.all():
        analytics_list.append({
            "order_id": order.id,
            "actual_delivery_time": trip_an.actual_delivery_time,
            "eta_accuracy": trip_an.eta_accuracy,
            "distance_traveled": trip_an.distance_traveled,
            "pickup_delay": trip_an.pickup_delay,
            "driver_idle_time": trip_an.driver_idle_time,
            "assignment_time": trip_an.assignment_time,
            "created_at": trip_an.created_at.isoformat()
        })
    return analytics_list

async def _get_oldest_task_age(queue_name: str) -> float:
    """
    Inspects the oldest task in the specified Redis list (Celery queue).
    Tries to retrieve the pushed_at timestamp.
    Returns the age of the task in seconds, or 0.0 if empty/unparseable.
    """
    import base64
    import json
    import time
    try:
        # The oldest element is at index -1 in Redis Celery queues
        task_data = await redis_client.lindex(queue_name, -1)
        if not task_data:
            return 0.0
            
        payload = json.loads(task_data)
        
        body_encoding = payload.get("properties", {}).get("body_encoding")
        body_str = payload.get("body", "")
        
        if body_encoding == "base64":
            decoded_body = base64.b64decode(body_str).decode("utf-8")
            body = json.loads(decoded_body)
        else:
            body = json.loads(body_str) if isinstance(body_str, str) else body_str

        # body: [args, kwargs, embed]
        args = body[0] if isinstance(body, list) and len(body) > 0 else []
        pushed_at = None
        
        if queue_name == "notifications" and len(args) >= 5:
            pushed_at = args[4]
        elif queue_name == "analytics" and len(args) >= 2:
            # process_delivery_analytics_task(order_id, pushed_at)
            pushed_at = args[1]
            
        kwargs = body[1] if isinstance(body, list) and len(body) > 1 else {}
        if not pushed_at and isinstance(kwargs, dict):
            pushed_at = kwargs.get("pushed_at")
            
        if pushed_at:
            return max(0.0, time.time() - float(pushed_at))
            
    except Exception as e:
        import logging
        logging.getLogger("QueueAgeHelper").error(f"Error parsing oldest task age for queue {queue_name}: {e}")
        
    return 0.0

@router.get("/observability/vitals")
async def get_observability_vitals(
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant)
):
    """Returns system operational metrics: Celery queue sizes, DLQ records, active load, and queue ages."""
    # Read queue lengths directly from Redis broker lists
    notifications_queue_size = await redis_client.llen("notifications")
    analytics_queue_size = await redis_client.llen("analytics")
    dlq_size = await redis_client.llen("notifications:dlq")
    
    oldest_notification_age = await _get_oldest_task_age("notifications")
    oldest_analytics_age = await _get_oldest_task_age("analytics")
    
    # Query database for active deliveries count (status is in matching cycle)
    active_deliveries_res = await db.execute(
        select(func.count(Order.id)).where(
            Order.tenant_id == tenant.id,
            Order.status.in_([OrderStatus.DRIVER_PENDING, OrderStatus.ASSIGNED, OrderStatus.PICKED_UP, OrderStatus.IN_TRANSIT])
        )
    )
    active_deliveries_count = active_deliveries_res.scalar() or 0
    
    # Query Notification Logs stats
    from app.models.notification_log import NotificationLog, NotificationStatus
    total_notifications_res = await db.execute(
        select(func.count(NotificationLog.id)).where(NotificationLog.tenant_id == tenant.id)
    )
    total_notifications = total_notifications_res.scalar() or 0
    
    failed_notifications_res = await db.execute(
        select(func.count(NotificationLog.id)).where(
            NotificationLog.tenant_id == tenant.id,
            NotificationLog.status == NotificationStatus.FAILED
        )
    )
    failed_notifications = failed_notifications_res.scalar() or 0
    
    return {
        "queues": {
            "notifications": notifications_queue_size,
            "analytics": analytics_queue_size,
            "dead_letter_queue": dlq_size,
            "oldest_notification_age": oldest_notification_age,
            "oldest_analytics_age": oldest_analytics_age
        },
        "system": {
            "active_deliveries": active_deliveries_count,
            "total_notifications_sent": total_notifications,
            "failed_notifications": failed_notifications
        }
    }


@router.post("/tenant/rotate-key")
async def rotate_tenant_api_key(
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant)
):
    """Regenerates a secure random API key for the authenticated tenant."""
    from app.core.security import generate_api_key
    
    old_key = tenant.api_key
    new_key = generate_api_key()
    tenant.api_key = new_key
    
    # Save changes to Postgres DB
    await db.commit()
    await db.refresh(tenant)
    
    # Remove old key cache from Redis to enforce invalidation
    await redis_client.delete(f"tenant:key:{old_key}")
    
    return {
        "detail": "API key successfully rotated",
        "api_key": new_key
    }

