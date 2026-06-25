import pytest
import pytest_asyncio
import asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.models.tenant import Tenant

# Use in-memory SQLite database for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    
    # Import all models to register on Base metadata
    from app.models.tenant import Tenant
    from app.models.driver import Driver
    from app.models.order import Order
    from app.models.transition import OrderStateTransition
    from app.models.attempt import AssignmentAttempt
    from app.models.notification_log import NotificationLog
    from app.models.analytics import TripAnalytics, DriverAnalytics, TenantAnalytics, TenantUsageHourly
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    yield engine
    await engine.dispose()

@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    AsyncSessionLocal = async_sessionmaker(
        bind=test_engine, 
        class_=AsyncSession, 
        expire_on_commit=False
    )
    async with AsyncSessionLocal() as session:
        yield session
        # Clean up database tables between tests
        await session.rollback()
        # Delete entries to isolate tests
        from sqlalchemy import delete
        from app.models.transition import OrderStateTransition
        from app.models.order import Order
        from app.models.driver import Driver
        from app.models.tenant import Tenant
        from app.models.attempt import AssignmentAttempt
        from app.models.notification_log import NotificationLog
        from app.models.analytics import TripAnalytics, DriverAnalytics, TenantAnalytics, TenantUsageHourly
        
        await session.execute(delete(NotificationLog))
        await session.execute(delete(TripAnalytics))
        await session.execute(delete(DriverAnalytics))
        await session.execute(delete(TenantAnalytics))
        await session.execute(delete(TenantUsageHourly))
        await session.execute(delete(AssignmentAttempt))
        await session.execute(delete(OrderStateTransition))
        await session.execute(delete(Order))
        await session.execute(delete(Driver))
        await session.execute(delete(Tenant))
        await session.commit()

@pytest_asyncio.fixture
async def client(db_session) -> AsyncGenerator[AsyncClient, None]:
    # Override dependency
    async def override_get_db():
        yield db_session
        
    app.dependency_overrides[get_db] = override_get_db
    app.state.db = db_session
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
        
    app.dependency_overrides.clear()
    if hasattr(app.state, "db"):
        del app.state.db

@pytest_asyncio.fixture
async def test_tenant(db_session) -> Tenant:
    tenant = Tenant(name="Test Tenant", api_key="test_api_key_123")
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant

@pytest_asyncio.fixture(autouse=True)
async def cleanup_redis():
    yield
    from app.db.redis import redis_client
    try:
        await redis_client.aclose()
    except Exception:
        pass
