import asyncio
from app.db.session import AsyncSessionLocal, engine
from app.db.base import Base
from app.models.tenant import Tenant
from app.models.driver import Driver, DriverStatus
from app.models.order import Order
from app.models.transition import OrderStateTransition
from app.core.security import generate_api_key

async def seed():
    print("Initializing database (dropping existing tables)...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        
    async with AsyncSessionLocal() as db:
        # Check if Tenant A already exists
        from sqlalchemy.future import select
        result = await db.execute(select(Tenant).where(Tenant.name == "Tenant A"))
        existing_tenant = result.scalars().first()
        
        if existing_tenant:
            tenant_key = existing_tenant.api_key
            print(f"Tenant A already exists with API Key: {tenant_key}")
        else:
            tenant_key = generate_api_key()
            tenant = Tenant(name="Tenant A", api_key=tenant_key)
            db.add(tenant)
            await db.commit()
            print("Tenant A created.")

        # Seed Driver 1
        d1_res = await db.execute(select(Driver).where(Driver.name == "Driver 1"))
        if not d1_res.scalars().first():
            db.add(Driver(name="Driver 1", phone="+1111111111", status=DriverStatus.OFFLINE, rating=4.9, is_available=True))
            print("Driver 1 created.")

        # Seed Driver 2
        d2_res = await db.execute(select(Driver).where(Driver.name == "Driver 2"))
        if not d2_res.scalars().first():
            db.add(Driver(name="Driver 2", phone="+2222222222", status=DriverStatus.OFFLINE, rating=4.8, is_available=True))
            print("Driver 2 created.")

        # Seed Driver 3
        d3_res = await db.execute(select(Driver).where(Driver.name == "Driver 3"))
        if not d3_res.scalars().first():
            db.add(Driver(name="Driver 3", phone="+3333333333", status=DriverStatus.OFFLINE, rating=4.7, is_available=True))
            print("Driver 3 created.")

        await db.commit()
        print("Database seeded successfully!")
        print("--------------------------------------------------")
        print(f"Tenant A API Key: {tenant_key}")
        print("--------------------------------------------------")

if __name__ == "__main__":
    asyncio.run(seed())
