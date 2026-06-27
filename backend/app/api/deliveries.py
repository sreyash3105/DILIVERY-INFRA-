from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from app.db.session import get_db
from app.models.tenant import Tenant
from app.models.order import Order, OrderStatus
from app.dependencies.auth import get_current_tenant
from app.schemas.delivery import DeliveryCreate, DeliveryStatusUpdate, ManualAssignment, DeliveryResponse, AutoAssignmentRequest
from app.services.delivery_service import DeliveryService
from app.services.assignment_service import AssignmentService

router = APIRouter()

@router.get("", response_model=List[DeliveryResponse])
@router.get("/", response_model=List[DeliveryResponse], include_in_schema=False)
async def list_deliveries(
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    limit: int = 50,
    offset: int = 0
):
    """
    Returns paginated deliveries for the authenticated tenant.
    - `limit`: max records to return (default 50, max sensibly capped by caller)
    - `offset`: number of records to skip (for page-based navigation)
    """
    result = await db.execute(
        select(Order)
        .where(Order.tenant_id == tenant.id)
        .order_by(Order.id.desc())
        .limit(limit)
        .offset(offset)
    )
    orders = result.scalars().all()
    return orders

@router.post("", response_model=DeliveryResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=DeliveryResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def create_delivery(
    delivery_data: DeliveryCreate,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant)
):
    order = await DeliveryService.create_delivery(db, tenant.id, delivery_data)
    return order

@router.get("/{delivery_id}", response_model=DeliveryResponse)
async def get_delivery(
    delivery_id: int,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant)
):
    order = await DeliveryService.get_delivery(db, tenant.id, delivery_id)
    return order

@router.get("/{delivery_id}/transitions")
async def get_delivery_transitions(
    delivery_id: int,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant)
):
    # Ensure the delivery exists and belongs to the tenant
    await DeliveryService.get_delivery(db, tenant.id, delivery_id)
    
    from app.models.transition import OrderStateTransition
    result = await db.execute(
        select(OrderStateTransition)
        .where(OrderStateTransition.order_id == delivery_id)
        .order_by(OrderStateTransition.created_at.asc())
    )
    transitions = result.scalars().all()
    return [
        {
            "id": t.id,
            "from_status": t.from_status,
            "to_status": t.to_status,
            "created_at": t.created_at.isoformat()
        }
        for t in transitions
    ]

@router.patch("/{delivery_id}/status", response_model=DeliveryResponse)
async def update_delivery_status(
    delivery_id: int,
    status_update: DeliveryStatusUpdate,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant)
):
    order = await DeliveryService.update_status(
        db, 
        tenant.id, 
        delivery_id, 
        status_update.status, 
        status_update.driver_id
    )
    return order

@router.post("/{delivery_id}/assign-driver", response_model=DeliveryResponse)
async def assign_driver(
    delivery_id: int,
    assignment: ManualAssignment,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant)
):
    order = await AssignmentService.assign_driver(
        db, 
        tenant.id, 
        delivery_id, 
        assignment.driver_id
    )
    return order

@router.get("/{delivery_id}/live-location")
async def get_live_location(
    delivery_id: int,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant)
):
    from app.db.redis import redis_client
    import json
    
    # 1. Try to fetch from Redis Cache
    cache_key = f"delivery:{delivery_id}:live_location"
    cached_data = await redis_client.get(cache_key)
    if cached_data:
        try:
            return json.loads(cached_data)
        except Exception:
            pass
            
    # 2. Fallback to PostgreSQL
    order = await DeliveryService.get_delivery(db, tenant.id, delivery_id)
    if not order or not order.driver_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="No active driver assigned to this delivery"
        )
        
    from app.services.driver_service import DriverService
    try:
        driver = await DriverService.get_driver(db, order.driver_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Driver not found"
        )
        
    if driver.current_lat is None or driver.current_lng is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="No location updates recorded for this driver yet"
        )
        
    return {
        "driver_id": driver.id,
        "delivery_id": order.id,
        "lat": driver.current_lat,
        "lng": driver.current_lng,
        "timestamp": driver.updated_at.isoformat()
    }

@router.post("/assign-driver", response_model=DeliveryResponse)
async def trigger_auto_assignment(
    req: AutoAssignmentRequest,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant)
):
    order = await AssignmentService.trigger_assignment(db, tenant.id, req.order_id)
    return order

@router.post("/{delivery_id}/accept", response_model=DeliveryResponse)
async def accept_delivery(
    delivery_id: int,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant)
):
    # 1. Fetch order
    order_result = await db.execute(select(Order).where(Order.id == delivery_id))
    order = order_result.scalars().first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.tenant_id != tenant.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
        
    if order.status != OrderStatus.DRIVER_PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Delivery is not in DRIVER_PENDING state")
        
    driver_id = order.driver_id
    if not driver_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No driver proposed for this delivery")
        
    # 2. Find the OFFERED assignment attempt
    from app.models.attempt import AssignmentAttempt, AttemptStatus
    from app.models.driver import Driver, DriverStatus
    from app.models.transition import OrderStateTransition
    import json
    
    attempt_result = await db.execute(
        select(AssignmentAttempt).where(
            AssignmentAttempt.order_id == delivery_id,
            AssignmentAttempt.driver_id == driver_id,
            AssignmentAttempt.status == AttemptStatus.OFFERED
        )
    )
    attempt = attempt_result.scalars().first()
    if attempt:
        attempt.status = AttemptStatus.ACCEPTED
        
    # 3. Update Order and Driver status
    old_status = order.status
    order.status = OrderStatus.ASSIGNED
    
    driver_result = await db.execute(select(Driver).where(Driver.id == driver_id))
    driver = driver_result.scalars().first()
    if driver:
        driver.status = DriverStatus.BUSY
        
    transition = OrderStateTransition(
        order_id=order.id,
        from_status=old_status,
        to_status=OrderStatus.ASSIGNED
    )
    db.add(transition)
    
    # Remove from active drivers geo index
    from app.db.redis import redis_client
    await redis_client.zrem("drivers:active", str(driver_id))
    
    await db.commit()
    await db.refresh(order)
    
    # Broadcast to websocket
    pub_payload = {
        "delivery_id": order.id,
        "status": order.status,
        "driver_id": order.driver_id
    }
    await redis_client.publish(f"delivery:{order.id}", json.dumps(pub_payload))
    
    from app.core.events import dispatch_event
    dispatch_event("ASSIGNED", order.id, order.tenant_id)
    
    return order

@router.post("/{delivery_id}/reject", response_model=DeliveryResponse)
async def reject_delivery(
    delivery_id: int,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant)
):
    # 1. Fetch order
    order_result = await db.execute(select(Order).where(Order.id == delivery_id))
    order = order_result.scalars().first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.tenant_id != tenant.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
        
    if order.status != OrderStatus.DRIVER_PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Delivery is not in DRIVER_PENDING state")
        
    driver_id = order.driver_id
    if not driver_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No driver proposed for this delivery")
        
    # 2. Find the OFFERED assignment attempt
    from app.models.attempt import AssignmentAttempt, AttemptStatus
    
    attempt_result = await db.execute(
        select(AssignmentAttempt).where(
            AssignmentAttempt.order_id == delivery_id,
            AssignmentAttempt.driver_id == driver_id,
            AssignmentAttempt.status == AttemptStatus.OFFERED
        )
    )
    attempt = attempt_result.scalars().first()
    if attempt:
        attempt.status = AttemptStatus.REJECTED
        
    # 3. Commit the rejection state
    await db.commit()
    
    # 4. Trigger re-assignment
    order = await AssignmentService.trigger_assignment(db, tenant.id, delivery_id)
    return order

@router.get("/{delivery_id}/eta")
async def get_delivery_eta(
    delivery_id: int,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant)
):
    from app.db.redis import redis_client
    import json
    
    # Check cache first — use a dedicated ETA key, separate from live_location
    cache_key = f"delivery:{delivery_id}:eta"
    cached_data = await redis_client.get(cache_key)
    if cached_data:
        try:
            data = json.loads(cached_data)
            if "eta_minutes" in data:
                return {
                    "delivery_id": delivery_id,
                    "eta_minutes": data["eta_minutes"],
                    "distance_meters": data.get("distance_meters"),
                    "stage": data.get("stage")
                }
        except Exception:
            pass
            
    # Compute fresh if cache miss
    order = await DeliveryService.get_delivery(db, tenant.id, delivery_id)
    if not order or not order.driver_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No driver assigned to this delivery")
        
    from app.services.driver_service import DriverService
    driver = await DriverService.get_driver(db, order.driver_id)
    if driver.current_lat is None or driver.current_lng is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Driver location unknown")
        
    from app.services.route_service import RouteService
    route_info = await RouteService.recalculate_eta(db, delivery_id, driver.current_lat, driver.current_lng)
    if not route_info:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not calculate ETA for current delivery status")
        
    return {
        "delivery_id": delivery_id,
        "eta_minutes": route_info["eta_minutes"],
        "distance_meters": route_info["distance_meters"]
    }

@router.get("/{delivery_id}/route")
async def get_delivery_route(
    delivery_id: int,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant)
):
    order = await DeliveryService.get_delivery(db, tenant.id, delivery_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        
    from app.services.route_service import RouteService
    from app.services.driver_service import DriverService
    
    # Default origin / destination
    origin_lat, origin_lng = order.pickup_lat, order.pickup_lng
    dest_lat, dest_lng = order.dropoff_lat, order.dropoff_lng
    
    if order.status == OrderStatus.ASSIGNED and order.driver_id:
        try:
            driver = await DriverService.get_driver(db, order.driver_id)
            if driver.current_lat is not None and driver.current_lng is not None:
                origin_lat, origin_lng = driver.current_lat, driver.current_lng
                dest_lat, dest_lng = order.pickup_lat, order.pickup_lng
        except Exception:
            pass
    elif order.status in [OrderStatus.PICKED_UP, OrderStatus.IN_TRANSIT] and order.driver_id:
        try:
            driver = await DriverService.get_driver(db, order.driver_id)
            if driver.current_lat is not None and driver.current_lng is not None:
                origin_lat, origin_lng = driver.current_lat, driver.current_lng
                dest_lat, dest_lng = order.dropoff_lat, order.dropoff_lng
        except Exception:
            pass
            
    route_details = await RouteService.get_route(origin_lat, origin_lng, dest_lat, dest_lng)
    
    geometry = [
        [origin_lat, origin_lng],
        [dest_lat, dest_lng]
    ]
    
    return {
        "delivery_id": delivery_id,
        "origin": {"lat": origin_lat, "lng": origin_lng},
        "destination": {"lat": dest_lat, "lng": dest_lng},
        "distance_meters": route_details["distance_meters"],
        "eta_minutes": route_details["eta_minutes"],
        "geometry": geometry
    }

