from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional
from app.models.order import Order, OrderStatus
from app.models.transition import OrderStateTransition
from app.schemas.delivery import DeliveryCreate
from app.services.state_machine import OrderStateMachine
from app.core.exceptions import OrderNotFoundError, UnauthorizedTenantError

class DeliveryService:
    @staticmethod
    async def create_delivery(db: AsyncSession, tenant_id: int, delivery_data: DeliveryCreate) -> Order:
        db_order = Order(
            tenant_id=tenant_id,
            status=OrderStatus.CREATED,
            pickup_lat=delivery_data.pickup_lat,
            pickup_lng=delivery_data.pickup_lng,
            dropoff_lat=delivery_data.dropoff_lat,
            dropoff_lng=delivery_data.dropoff_lng
        )
        db.add(db_order)
        # flush() sends the INSERT to Postgres and populates db_order.id (auto-generated PK)
        # without committing the transaction — lets us create the transition in the same commit.
        await db.flush()

        # Log initial state creation transition
        transition = OrderStateTransition(
            order_id=db_order.id,
            from_status=OrderStatus.CREATED,
            to_status=OrderStatus.CREATED
        )
        db.add(transition)
        # Single commit — both the order and the transition persist atomically.
        await db.commit()
        await db.refresh(db_order)

        return db_order

    @staticmethod
    async def get_delivery(db: AsyncSession, tenant_id: int, delivery_id: int) -> Order:
        result = await db.execute(select(Order).where(Order.id == delivery_id))
        order = result.scalars().first()
        if not order:
            raise OrderNotFoundError()
        if order.tenant_id != tenant_id:
            raise UnauthorizedTenantError()
        return order

    @staticmethod
    async def update_status(
        db: AsyncSession, 
        tenant_id: int, 
        delivery_id: int, 
        new_status: OrderStatus, 
        driver_id: Optional[int] = None
    ) -> Order:
        # 1. Fetch order
        result = await db.execute(select(Order).where(Order.id == delivery_id))
        order = result.scalars().first()
        if not order:
            raise OrderNotFoundError()
        if order.tenant_id != tenant_id:
            raise UnauthorizedTenantError()
        
        # 2. Validate transition
        validated_status = OrderStateMachine.validate_transition(order.status, new_status)
        
        old_status = order.status
        
        # 3. Update order
        order.status = validated_status
        if driver_id is not None:
            order.driver_id = driver_id
            
        # 4. Create audit record
        transition = OrderStateTransition(
            order_id=order.id,
            from_status=old_status,
            to_status=validated_status
        )
        db.add(transition)

        # Auto-transition PICKED_UP -> IN_TRANSIT
        if validated_status == OrderStatus.PICKED_UP:
            old_status = OrderStatus.PICKED_UP
            order.status = OrderStatus.IN_TRANSIT
            transition_transit = OrderStateTransition(
                order_id=order.id,
                from_status=old_status,
                to_status=OrderStatus.IN_TRANSIT
            )
            db.add(transition_transit)
            
        # Reset driver status to ONLINE if order is DELIVERED or CANCELLED
        if validated_status in [OrderStatus.DELIVERED, OrderStatus.CANCELLED]:
            if order.driver_id:
                from app.models.driver import Driver, DriverStatus
                driver_result = await db.execute(select(Driver).where(Driver.id == order.driver_id))
                driver = driver_result.scalars().first()
                if driver:
                    driver.status = DriverStatus.ONLINE
                    driver.is_available = True
                    # Re-add to Redis active geo index
                    if driver.current_lat is not None and driver.current_lng is not None:
                        from app.db.redis import redis_client
                        await redis_client.geoadd("drivers:active", (driver.current_lng, driver.current_lat, str(driver.id)))
        
        # 5. Commit all changes atomically
        await db.commit()
        await db.refresh(order)

        # 6. Publish status updates to Redis Pub/Sub
        from app.db.redis import redis_client
        import json
        pub_payload = {
            "delivery_id": order.id,
            "status": order.status,
            "driver_id": order.driver_id
        }
        await redis_client.publish(f"delivery:{order.id}", json.dumps(pub_payload))

        # 7. Dispatch events to Celery pipeline after commit so workers read correct DB state
        from app.core.events import dispatch_event
        # If the original request was PICKED_UP, fire that event explicitly before the
        # auto-advanced IN_TRANSIT event so both notifications are delivered in order.
        if validated_status == OrderStatus.PICKED_UP:
            dispatch_event("PICKED_UP", order.id, order.tenant_id)
        dispatch_event(order.status.value, order.id, order.tenant_id)

        return order
