# Change Record — CR-008

| Field | Detail |
|-------|--------|
| **Change ID** | CR-008 |
| **Date** | 2026-06-27 |
| **Type** | Refactoring |
| **Severity** | Low |
| **Author** | Sreyash Baishkhiyar |
| **Status** | Applied |

---

## Description

Extracted the `ghost_driver_cleanup_loop()` background coroutine from `main.py` into a dedicated module `backend/app/tasks/cleanup.py`.

## Files Changed

| File | Change |
|------|--------|
| `backend/app/tasks/cleanup.py` | **New file** — contains the extracted coroutine with proper docstrings and top-level imports |
| `backend/app/main.py` | Removed inline function definition; added `from app.tasks.cleanup import ghost_driver_cleanup_loop` |

## Root Cause

The `ghost_driver_cleanup_loop()` coroutine (37 lines) was defined as a top-level free function inside `main.py`, mixed between the application bootstrap code (`setup_logging()`, `lifespan()`, `create_app()`). This caused:

1. **Discoverability problem** — a developer looking for background tasks would not find it by looking in the `tasks/` module where other background tasks (`analytics.py`, `notifications.py`) are defined.
2. **Testability problem** — the function could not be independently imported and tested without loading the entire `main.py` module.
3. **Style inconsistency** — all other background tasks in the project are in `app/tasks/`. This was the only exception.
4. **Import hygiene** — all imports (`asyncio`, `datetime`, `sqlalchemy`, `logging`) were inlined inside the function body rather than declared at module level.

## Change Made

**`backend/app/tasks/cleanup.py` (new file):**

```python
"""
Background cleanup tasks that run inside the FastAPI process lifespan.
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
    """
    while True:
        ...  # (full implementation moved here)
```

**`backend/app/main.py`:**

```diff
  from app.core.logging_config import setup_logging
+ from app.tasks.cleanup import ghost_driver_cleanup_loop

  # Configure structured JSON logging on load
  setup_logging()

- async def ghost_driver_cleanup_loop():
-     import asyncio
-     ...  (37 lines removed)
```

## Impact

- **Behavior:** Zero change — `lifespan()` still calls `asyncio.create_task(ghost_driver_cleanup_loop())` and cancels it on shutdown exactly as before.
- **Testability:** `ghost_driver_cleanup_loop` can now be imported directly from `app.tasks.cleanup` for unit testing.
- **Consistency:** All background tasks are now co-located in `app/tasks/`.

## Risk Assessment

None. Pure structural reorganization. The function logic, timing (30s sleep, 90s cutoff), and integration point in `lifespan()` are unchanged.

---
