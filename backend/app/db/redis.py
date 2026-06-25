import redis.asyncio as aioredis
from app.core.config import settings

# Initialize Redis client with SSL options if using secure scheme (rediss://)
if settings.REDIS_URL.startswith("rediss://"):
    redis_client = aioredis.from_url(
        settings.REDIS_URL, 
        encoding="utf-8", 
        decode_responses=True,
        ssl_cert_reqs=None
    )
else:
    redis_client = aioredis.from_url(
        settings.REDIS_URL, 
        encoding="utf-8", 
        decode_responses=True
    )

async def get_redis() -> aioredis.Redis:
    return redis_client
