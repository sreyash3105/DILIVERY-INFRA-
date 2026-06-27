"""
Background cleanup tasks that run inside the FastAPI process lifespan.

Kept separate from main.py so each task is independently testable
and easy to discover without reading the entire app bootstrap.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.driver import Driver, DriverStatus
from app.db.redis import redis_client

logger = logging.getLogger("GhostDriverCleanup")


async def ghost_driver_cleanup_loop() -> None:
    """
    Runs every 30 seconds. Marks any driver whose last_seen_at timestamp
    is more than 90 seconds old as OFFLINE and removes them from the
    Redis geo-index so they are not offered new deliveries.

    The loop exits cleanly when the task is cancelled (e.g. on server shutdown).
    """
    while True:
        try:
            await asyncio.sleep(30)
            async with AsyncSessionLocal() as db:
                cutoff = datetime.now(timezone.utc) - timedelta(seconds=90)
                # Find drivers who are ONLINE but haven't sent a ping in 90 seconds
                stmt = select(Driver).where(
                    Driver.status == DriverStatus.ONLINE,
                    Driver.last_seen_at < cutoff
                )
                result = await db.execute(stmt)
                ghosts = result.scalars().all()

                for driver in ghosts:
                    logger.info(
                        f"Ghost driver cleanup: Driver #{driver.id} marked OFFLINE due to inactivity."
                    )
                    driver.status = DriverStatus.OFFLINE
                    driver.is_available = False
                    # Remove from Redis Geo Index
                    await redis_client.zrem("drivers:active", str(driver.id))

                if ghosts:
                    await db.commit()

        except asyncio.CancelledError:
            # Graceful shutdown — propagate cancellation to exit the loop
            break
        except Exception as e:
            logger.error(f"Error in ghost_driver_cleanup_loop: {e}")
