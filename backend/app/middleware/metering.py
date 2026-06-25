import json
import logging
import time
from datetime import datetime, timezone
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.db.redis import redis_client
from app.db.session import AsyncSessionLocal
from app.models.tenant import Tenant
from sqlalchemy import select

logger = logging.getLogger("MeteringMiddleware")

class MeteringMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        api_key = request.headers.get("X-API-Key")
        if not api_key:
            # Skip metering if no tenant API key is supplied (e.g. public, driver, or health routes)
            return await call_next(request)

        # 1. Fetch Tenant details (Cache in Redis for 5 minutes to avoid PG bottleneck)
        cache_key = f"tenant:key:{api_key}"
        tenant_data = await redis_client.get(cache_key)
        
        db_session = getattr(request.app.state, "db", None)
        
        if tenant_data:
            tenant = json.loads(tenant_data)
        else:
            if db_session:
                result = await db_session.execute(select(Tenant).where(Tenant.api_key == api_key))
                tenant_db = result.scalars().first()
            else:
                async with AsyncSessionLocal() as db:
                    result = await db.execute(select(Tenant).where(Tenant.api_key == api_key))
                    tenant_db = result.scalars().first()
                    
            if not tenant_db:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid API Key"}
                )
            tenant = {
                "id": tenant_db.id,
                "name": tenant_db.name,
                "plan_name": tenant_db.plan_name,
                "rate_limit_per_minute": tenant_db.rate_limit_per_minute,
                "monthly_quota": tenant_db.monthly_quota,
                "quota_exceeded_at": tenant_db.quota_exceeded_at.isoformat() if tenant_db.quota_exceeded_at else None
            }
            # Cache for 300 seconds
            await redis_client.setex(cache_key, 300, json.dumps(tenant))

        tenant_id = tenant["id"]
        
        # Add tenant ID to request state for downstream endpoint handlers
        request.state.tenant_id = tenant_id

        # 2. Rate Limiting (Redis Window Counter)
        current_time = int(time.time())
        current_minute = current_time // 60
        rate_key = f"limit:{tenant_id}:{current_minute}"
        
        requests_this_minute = await redis_client.incr(rate_key)
        if requests_this_minute == 1:
            await redis_client.expire(rate_key, 60)
            
        if requests_this_minute > tenant["rate_limit_per_minute"]:
            retry_after = 60 - (current_time % 60)
            logger.warning(f"Rate limit exceeded for Tenant {tenant_id}. Blocked.")
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please try again later."},
                headers={"Retry-After": str(retry_after)}
            )

        # 3. Usage Metering (Daily Request Counter in Redis)
        date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        daily_usage_key = f"usage:{tenant_id}:{date_key}"
        await redis_client.incr(daily_usage_key)
        # Auto expire usage keys after 2 days
        await redis_client.expire(daily_usage_key, 172800)

        # 4. Quota Enforcement (Cumulative Monthly Usage Counter in Redis)
        current_month = datetime.now(timezone.utc).strftime("%Y-%m")
        monthly_usage_key = f"usage:{tenant_id}:monthly:{current_month}"
        
        monthly_usage = await redis_client.incr(monthly_usage_key)
        if monthly_usage == 1:
            # Set key to expire in 35 days (covers month transitions)
            await redis_client.expire(monthly_usage_key, 3024000)

        # 5. Check Quota Block for quota-consuming actions
        # Specifically: block creating new deliveries
        is_order_creation = request.method == "POST" and request.url.path.rstrip("/").endswith("/deliveries")
        
        if monthly_usage > tenant["monthly_quota"]:
            # Set quota_exceeded_at timestamp if not set already
            if not tenant["quota_exceeded_at"]:
                if db_session:
                    result = await db_session.execute(select(Tenant).where(Tenant.id == tenant_id))
                    t_db = result.scalars().first()
                    if t_db and not t_db.quota_exceeded_at:
                        t_db.quota_exceeded_at = datetime.now(timezone.utc)
                        await db_session.commit()
                else:
                    async with AsyncSessionLocal() as db:
                        result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
                        t_db = result.scalars().first()
                        if t_db and not t_db.quota_exceeded_at:
                            t_db.quota_exceeded_at = datetime.now(timezone.utc)
                            await db.commit()
                        
                # Invalidate Redis tenant cache
                await redis_client.delete(cache_key)
                        
            if is_order_creation:
                logger.error(f"Tenant {tenant_id} monthly quota exceeded. Blocked order creation.")
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Monthly delivery quota exceeded. Please upgrade your plan."}
                )

        return await call_next(request)
