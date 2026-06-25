from fastapi import Header, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.session import get_db
from app.models.tenant import Tenant
from app.core.exceptions import TenantNotFoundError
from app.core.config import settings

async def get_current_tenant(
    x_api_key: str = Header(..., alias=settings.API_KEY_HEADER_NAME),
    db: AsyncSession = Depends(get_db)
) -> Tenant:
    result = await db.execute(
        select(Tenant).where(Tenant.api_key == x_api_key)
    )
    tenant = result.scalars().first()
    if not tenant:
        raise TenantNotFoundError()
    return tenant
