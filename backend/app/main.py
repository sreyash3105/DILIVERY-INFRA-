from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from app.api import deliveries, drivers, websockets, analytics
from app.core.exceptions import register_exception_handlers
from app.db.base import Base
from app.db.session import engine
from app.core.logging_config import setup_logging
from app.tasks.cleanup import ghost_driver_cleanup_loop

# Configure structured JSON logging on load
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    # Dynamically import models to register them on Base
    from app.models import Tenant, Driver, Order, OrderStateTransition, AssignmentAttempt, NotificationLog, TripAnalytics, DriverAnalytics, TenantAnalytics, TenantUsageHourly
    
    # Create tables on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    # Auto-seed default tenant and drivers if database is empty
    from sqlalchemy import select
    from app.db.session import AsyncSessionLocal
    from app.models.tenant import Tenant
    from app.models.driver import Driver, DriverStatus

    async with AsyncSessionLocal() as db:
        tenant_res = await db.execute(select(Tenant).limit(1))
        if not tenant_res.scalars().first():
            # Seed default tenant with key 'test_api_key_123'
            default_tenant = Tenant(name="Default Tenant A", api_key="test_api_key_123")
            db.add(default_tenant)
            
            # Seed default drivers
            db.add(Driver(name="Driver 1", phone="+1111111111", status=DriverStatus.OFFLINE, rating=4.9, is_available=True))
            db.add(Driver(name="Driver 2", phone="+2222222222", status=DriverStatus.OFFLINE, rating=4.8, is_available=True))
            db.add(Driver(name="Driver 3", phone="+3333333333", status=DriverStatus.OFFLINE, rating=4.7, is_available=True))
            await db.commit()
            print("Auto-seeded default Tenant A (key: 'test_api_key_123') and 3 drivers.")
        
    # Start ghost driver cleanup task
    cleanup_task = asyncio.create_task(ghost_driver_cleanup_loop())
    
    yield
    
    # Cancel cleanup task on shutdown
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass


def create_app() -> FastAPI:
    app = FastAPI(
        title="Delivery Infrastructure Platform API",
        version="0.1.0",
        description="A Real-Time Logistics & Tracking Platform for Modern Applications",
        lifespan=lifespan
    )

    # Enable CORS (Cross-Origin Resource Sharing) so frontend can communicate with backend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Enable Multi-tenant SaaS Metering & Rate limiting middleware
    from app.middleware.metering import MeteringMiddleware
    app.add_middleware(MeteringMiddleware)

    # Enable Prometheus Metrics middleware
    from app.middleware.metrics import PrometheusMiddleware, register_metrics_route
    app.add_middleware(PrometheusMiddleware)
    register_metrics_route(app)

    # Register routers
    app.include_router(deliveries.router, prefix="/deliveries", tags=["Deliveries"])
    app.include_router(drivers.router, prefix="/drivers", tags=["Drivers"])
    app.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
    app.include_router(websockets.router, tags=["WebSockets"])

    # Register exception handlers
    register_exception_handlers(app)

    from fastapi.responses import JSONResponse
    
    @app.get("/health")
    async def health_check():
        api_status = "healthy"
        
        # Postgres check
        postgres_status = "unhealthy"
        try:
            from app.db.session import AsyncSessionLocal
            from sqlalchemy import text
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))
            postgres_status = "healthy"
        except Exception as e:
            postgres_status = f"unhealthy: {str(e)}"
            
        # Redis check
        redis_status = "unhealthy"
        try:
            from app.db.redis import redis_client
            await redis_client.ping()
            redis_status = "healthy"
        except Exception as e:
            redis_status = f"unhealthy: {str(e)}"
            
        # Celery check
        celery_status = "unhealthy"
        try:
            from app.core.celery_app import celery_app
            # Inspect ping returns a dict mapping worker names to ping responses
            inspector = celery_app.control.inspect(timeout=0.5)
            pings = inspector.ping()
            if pings:
                celery_status = "healthy"
            else:
                celery_status = "unhealthy: no active workers detected"
        except Exception as e:
            celery_status = f"unhealthy: {str(e)}"
            
        overall_healthy = (
            api_status == "healthy" and
            postgres_status == "healthy" and
            redis_status == "healthy" and
            celery_status == "healthy"
        )
        
        status_code = 200 if overall_healthy else 503
        
        return JSONResponse(
            status_code=status_code,
            content={
                "api": api_status,
                "postgres": postgres_status,
                "redis": redis_status,
                "celery": celery_status
            }
        )


    return app

app = create_app()
