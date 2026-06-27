import asyncio
import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional, List
from app.models.order import Order, OrderStatus
from app.models.driver import Driver, DriverStatus
from app.models.attempt import AssignmentAttempt, AttemptStatus
from app.models.transition import OrderStateTransition
from app.core.exceptions import OrderNotFoundError, DriverNotFoundError, UnauthorizedTenantError
from app.services.state_machine import OrderStateMachine
from app.db.redis import redis_client

logger = logging.getLogger("AssignmentService")

class AssignmentService:
    @classmethod
    async def assign_driver(cls, db: AsyncSession, tenant_id: int, order_id: int, driver_id: int) -> Order:
        """Manually assigns a driver to an order."""
        # 1. Fetch order
        order_result = await db.execute(select(Order).where(Order.id == order_id))
        order = order_result.scalars().first()
        if not order:
            raise OrderNotFoundError()
        if order.tenant_id != tenant_id:
            raise UnauthorizedTenantError()

        # 2. Fetch driver
        driver_result = await db.execute(select(Driver).where(Driver.id == driver_id))
        driver = driver_result.scalars().first()
        if not driver:
            raise DriverNotFoundError()

        # Validate transition using State Machine
        OrderStateMachine.validate_transition(order.status, OrderStatus.ASSIGNED)

        old_status = order.status
        order.status = OrderStatus.ASSIGNED
        order.driver_id = driver.id
        driver.status = DriverStatus.BUSY

        # Create audit record
        transition = OrderStateTransition(
            order_id=order.id,
            from_status=old_status,
            to_status=OrderStatus.ASSIGNED
        )
        db.add(transition)

        # Remove from active drivers geo index
        await redis_client.zrem("drivers:active", str(driver.id))

        await db.commit()
        await db.refresh(order)

        # Broadcast live status update via WebSocket
        pub_payload = {
            "delivery_id": order.id,
            "status": order.status,
            "driver_id": order.driver_id
        }
        await redis_client.publish(f"delivery:{order.id}", json.dumps(pub_payload))

        # Dispatch event to Celery pipeline
        from app.core.events import dispatch_event
        dispatch_event("ASSIGNED", order.id, order.tenant_id)

        return order

    @classmethod
    async def trigger_assignment(cls, db: AsyncSession, tenant_id: int, order_id: int) -> Order:
        """Runs the candidate discovery, scoring, and distributed lock assignment loop."""
        # 1. Fetch order
        order_result = await db.execute(select(Order).where(Order.id == order_id))
        order = order_result.scalars().first()
        if not order:
            raise OrderNotFoundError()
        if order.tenant_id != tenant_id:
            raise UnauthorizedTenantError()

        # Validate order state transition to DRIVER_PENDING
        OrderStateMachine.validate_transition(order.status, OrderStatus.DRIVER_PENDING)

        # 2. Get list of excluded driver IDs (those with REJECTED or TIMEOUT attempts)
        attempts_result = await db.execute(
            select(AssignmentAttempt.driver_id).where(
                AssignmentAttempt.order_id == order_id,
                AssignmentAttempt.status.in_([AttemptStatus.REJECTED, AttemptStatus.TIMEOUT])
            )
        )
        excluded_driver_ids = [row for row in attempts_result.scalars().all()]

        # 3. Discover nearby active online drivers using Redis GEOSEARCH
        # geosearch replaces the deprecated/removed georadius command (Redis 7.2+)
        # FROMLONLAT + BYRADIUS is the modern equivalent — result shape is identical.
        candidates = await redis_client.geosearch(
            "drivers:active",
            longitude=order.pickup_lng,
            latitude=order.pickup_lat,
            radius=10,
            unit="km",
            withdist=True,
            sort="ASC"
        )

        # Parse candidates
        valid_candidates = []
        for cand in candidates:
            driver_id_str, distance_km = cand[0], float(cand[1])
            driver_id = int(driver_id_str)
            if driver_id not in excluded_driver_ids:
                valid_candidates.append((driver_id, distance_km))

        # If no candidates found, mark order as NO_DRIVER_AVAILABLE
        if not valid_candidates:
            await cls._transition_to_no_driver(db, order)
            return order

        # 4. Score candidates: Distance (60%), Rating (30%), Workload (10%)
        # Fetch driver records from DB
        driver_ids = [c[0] for c in valid_candidates]
        drivers_db_result = await db.execute(select(Driver).where(Driver.id.in_(driver_ids)))
        drivers_db = {d.id: d for d in drivers_db_result.scalars().all()}

        scored_candidates = []
        for d_id, dist_km in valid_candidates:
            driver_record = drivers_db.get(d_id)
            if not driver_record:
                continue
            
            # Normalize components
            rating_val = driver_record.rating or 5.0
            rating_penalty = (5.0 - rating_val) * 1000
            
            # Workload penalty based on active deliveries count (since drivers are platform owned)
            # Fetch active deliveries count if available
            workload_val = getattr(driver_record, 'active_deliveries', 0)
            workload_penalty = workload_val * 1000
            
            # Score = (0.6 * distance_in_meters) + (0.3 * rating_penalty) + (0.1 * workload_penalty)
            dist_meters = dist_km * 1000.0
            score = (0.6 * dist_meters) + (0.3 * rating_penalty) + (0.1 * workload_penalty)
            scored_candidates.append((driver_record, score))

        # Sort best to worst (ascending score)
        scored_candidates.sort(key=lambda x: x[1])

        # 5. Assignment loop with distributed locking
        assigned_driver = None
        for driver_record, score in scored_candidates:
            lock_key = f"driver:{driver_record.id}:lock"
            
            # Acquire lock (SET NX PX 5000)
            lock_acquired = await redis_client.set(lock_key, "1", nx=True, px=5000)
            if not lock_acquired:
                logger.info(f"Lock failed for driver {driver_record.id}, trying next...")
                continue

            try:
                # Double-check driver availability status
                if driver_record.status == DriverStatus.ONLINE and driver_record.is_available:
                    assigned_driver = driver_record
                    break
            finally:
                # Release lock
                await redis_client.delete(lock_key)

        if not assigned_driver:
            # All candidate locks failed or became unavailable
            await cls._transition_to_no_driver(db, order)
            return order

        # 6. Offer order to selected driver
        old_status = order.status
        order.status = OrderStatus.DRIVER_PENDING
        order.driver_id = assigned_driver.id

        # Log state transition
        transition = OrderStateTransition(
            order_id=order.id,
            from_status=old_status,
            to_status=OrderStatus.DRIVER_PENDING
        )
        db.add(transition)

        # Create OFFERED assignment attempt row
        attempt = AssignmentAttempt(
            order_id=order.id,
            driver_id=assigned_driver.id,
            status=AttemptStatus.OFFERED
        )
        db.add(attempt)

        await db.commit()
        await db.refresh(order)

        # Broadcast live status update via WebSocket
        pub_payload = {
            "delivery_id": order.id,
            "status": order.status,
            "driver_id": order.driver_id
        }
        await redis_client.publish(f"delivery:{order.id}", json.dumps(pub_payload))

        # 7. Start 30-second background timeout task
        asyncio.create_task(cls._run_assignment_timeout(order.id, assigned_driver.id))

        # Dispatch event to Celery pipeline
        from app.core.events import dispatch_event
        dispatch_event("DRIVER_PENDING", order.id, order.tenant_id)

        return order

    @classmethod
    async def _transition_to_no_driver(cls, db: AsyncSession, order: Order) -> None:
        """Transitions order status to NO_DRIVER_AVAILABLE."""
        old_status = order.status
        order.status = OrderStatus.NO_DRIVER_AVAILABLE
        order.driver_id = None
        
        transition = OrderStateTransition(
            order_id=order.id,
            from_status=old_status,
            to_status=OrderStatus.NO_DRIVER_AVAILABLE
        )
        db.add(transition)
        await db.commit()
        await db.refresh(order)

        # Broadcast update
        pub_payload = {
            "delivery_id": order.id,
            "status": order.status,
            "driver_id": None
        }
        await redis_client.publish(f"delivery:{order.id}", json.dumps(pub_payload))

        # Dispatch event to Celery pipeline
        from app.core.events import dispatch_event
        dispatch_event("NO_DRIVER_AVAILABLE", order.id, order.tenant_id)

    @classmethod
    async def _run_assignment_timeout(cls, order_id: int, driver_id: int) -> None:
        """Asynchronously waits 30 seconds, then checks if the driver accepted. If not, retries."""
        await asyncio.sleep(30.0)
        from app.db.session import AsyncSessionLocal
        
        async with AsyncSessionLocal() as db:
            # Fetch order
            order_result = await db.execute(select(Order).where(Order.id == order_id))
            order = order_result.scalars().first()
            
            if order and order.status == OrderStatus.DRIVER_PENDING and order.driver_id == driver_id:
                logger.info(f"Assignment offer timed out for Order #{order_id} and Driver #{driver_id}")
                
                # Fetch offered attempt
                attempt_result = await db.execute(
                    select(AssignmentAttempt).where(
                        AssignmentAttempt.order_id == order_id,
                        AssignmentAttempt.driver_id == driver_id,
                        AssignmentAttempt.status == AttemptStatus.OFFERED
                    )
                )
                attempt = attempt_result.scalars().first()
                if attempt:
                    attempt.status = AttemptStatus.TIMEOUT
                
                # Commit timeout status transition
                await db.commit()

                # Re-trigger assignment (this will automatically exclude this driver)
                await cls.trigger_assignment(db, order.tenant_id, order_id)
