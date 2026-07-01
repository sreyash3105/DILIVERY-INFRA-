# Change Record — CR-011

| Field | Detail |
|-------|--------|
| **Change ID** | CR-011 |
| **Date** | 2026-07-01 |
| **Type** | Security Hardening |
| **Severity** | High |
| **Author** | Sreyash Baishkhiyar |
| **Status** | Applied |

---

## Description

Added an optional `X-Internal-Token` header guard to the driver registration endpoint (`POST /drivers`) and driver lookup (`GET /drivers/{id}`) to prevent anonymous actor abuse. Implemented via a new `require_internal_token` dependency that activates only when the `INTERNAL_API_TOKEN` environment variable is set — preserving zero-config behaviour for local and demo use.

## Files Changed

| File | Change |
|------|--------|
| `backend/app/dependencies/internal_auth.py` | **New file** — lightweight dependency that reads `INTERNAL_API_TOKEN` from environment and validates the `X-Internal-Token` request header |
| `backend/app/api/drivers.py` | Added `require_internal_token` dependency to `register_driver()` and `get_driver()` route handlers |
| `.env.example` | Added `INTERNAL_API_TOKEN=` entry with documentation comment |

## Function / Location

- `register_driver()` — `api/drivers.py`, line 14
- `get_driver()` — `api/drivers.py`, line 24

## Root Cause

`POST /drivers` and `GET /drivers/{id}` had no authentication whatsoever. Any anonymous HTTP client could:

1. **Register unlimited fake drivers** — floods the active driver pool and the Redis geo-index (`drivers:active`), causing the assignment engine to score and attempt to lock ghost drivers on every order.
2. **Look up driver phone numbers and metadata** — violates driver data privacy with a simple `GET /drivers/{id}` enumeration attack.

The delivery endpoints correctly required a `X-API-Key` tenant header, but the driver endpoints were intentionally left open during early development and never secured.

## Change Made

**New file — `backend/app/dependencies/internal_auth.py`:**

```python
import os
from fastapi import Header, HTTPException, status

_INTERNAL_TOKEN = os.getenv("INTERNAL_API_TOKEN")

async def require_internal_token(
    x_internal_token: str = Header(default=None, alias="X-Internal-Token")
) -> None:
    """
    Guards internal-only endpoints (e.g. driver registration).

    If INTERNAL_API_TOKEN is set in the environment, the request must supply
    a matching X-Internal-Token header. If the env var is not set (e.g. local
    demo run), the check is skipped so nothing breaks out of the box.
    """
    if _INTERNAL_TOKEN is None:
        return  # Open access — suitable for local / demo use

    if x_internal_token != _INTERNAL_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Internal-Token header."
        )
```

**Changes to `backend/app/api/drivers.py`:**

```diff
+ from app.dependencies.internal_auth import require_internal_token

  @router.post("")
  async def register_driver(
      driver_data: DriverCreate,
      db: AsyncSession = Depends(get_db),
+     _: None = Depends(require_internal_token)
  ):

  @router.get("/{driver_id}")
  async def get_driver(
      driver_id: int,
      db: AsyncSession = Depends(get_db),
+     _: None = Depends(require_internal_token)
  ):
```

**Addition to `.env.example`:**

```diff
+ # ----- Security: Internal Token (S-03) -----
+ # Guards POST /drivers and GET /drivers/{id}.
+ # If left blank, those endpoints are open — fine for local demo use.
+ # Set a strong random value (e.g. `openssl rand -hex 32`) for any
+ # shared or exposed deployment.
+ INTERNAL_API_TOKEN=
```

## Design Decisions

**Why an env-var toggle rather than always-on?**
This is a portfolio demo project. Requiring an internal token in all test environments and CI fixtures would force callers to set up an extra header everywhere. The toggle allows the demo to run with zero configuration while giving a real deployment a clear upgrade path.

**Why not reuse the tenant `X-API-Key` system?**
Driver registration is an infrastructure operation, not a tenant action. Reusing the tenant key would mean a tenant could register drivers (incorrect authorization model). A separate internal token keeps the two auth planes distinct.

**Why only `register_driver` and `get_driver`?**
- `POST /drivers/{id}/location` — used by the simulator and demo flow; locking it would break the demo.
- `PATCH /drivers/{id}/availability` — same reason.
- Those two are write-only operations with no sensitive data exposure; the main risks (driver pool flooding and data leakage) are addressed by guarding registration and lookup.

## Impact

- **Before:** `POST /drivers` and `GET /drivers/{id}` were fully open to anonymous callers.
- **After (no env var set):** Behaviour identical to before — guard is a no-op. Zero breaking change.
- **After (`INTERNAL_API_TOKEN` set):** Both endpoints require a matching `X-Internal-Token` header; unauthenticated requests receive `HTTP 401`.
- **Delivery flow:** Completely unaffected. Assignment engine, WebSockets, and tenant delivery endpoints are unchanged.
- **CI tests:** The existing test suite in `tests/test_api.py` calls `POST /drivers` without a token. Since `INTERNAL_API_TOKEN` is not set in the CI environment (`ci.yml` does not export it), tests continue to pass as-is.

## Risk Assessment

Low. The guard is explicitly opt-in via an environment variable. No existing functionality is broken by the change. The new dependency file is self-contained and has no side-effects when the env var is absent.

---
