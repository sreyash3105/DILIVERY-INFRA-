from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings

# Create async engine. For sqlite, disable check_same_thread.
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
else:
    # Disable statement cache for PgBouncer/Supabase transaction pooling compatibility
    connect_args = {"statement_cache_size": 0}

db_url = settings.DATABASE_URL
# Defensive programming: Strip pgbouncer parameter to prevent asyncpg crash
if "pgbouncer=" in db_url:
    from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
    parsed = urlparse(db_url)
    qsl = [(k, v) for k, v in parse_qsl(parsed.query) if k != "pgbouncer"]
    db_url = urlunparse(parsed._replace(query=urlencode(qsl)))

engine = create_async_engine(
    db_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine, 
    class_=AsyncSession, 
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

async def get_db():
    async with AsyncSessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()
