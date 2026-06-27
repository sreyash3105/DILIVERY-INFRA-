# Change Record — CR-004

| Field | Detail |
|-------|--------|
| **Change ID** | CR-004 |
| **Date** | 2026-06-27 |
| **Type** | Performance Improvement |
| **Severity** | High (at production scale) |
| **Author** | Sreyash Baishkhiyar |
| **Status** | Applied |

---

## Description

Added `limit` and `offset` pagination query parameters to `GET /deliveries` to prevent unbounded full-table scans.

## File Changed

`backend/app/api/deliveries.py`

## Function / Location

`list_deliveries()` — lines 15–23

## Root Cause

The endpoint fetched every order for a tenant with no `LIMIT` clause:

```python
result = await db.execute(
    select(Order).where(Order.tenant_id == tenant.id).order_by(Order.id.desc())
)
orders = result.scalars().all()
```

At scale (e.g., 10,000+ orders per tenant), every polling cycle from the frontend would:
- Execute a full sequential scan of the orders table
- Serialize and transmit potentially megabytes of JSON
- This ran every 10 seconds per connected browser tab

## Change Made

```diff
  async def list_deliveries(
      db: AsyncSession = Depends(get_db),
      tenant: Tenant = Depends(get_current_tenant),
+     limit: int = 50,
+     offset: int = 0
  ):
+     """
+     Returns paginated deliveries for the authenticated tenant.
+     - `limit`: max records to return (default 50)
+     - `offset`: number of records to skip
+     """
      result = await db.execute(
          select(Order)
          .where(Order.tenant_id == tenant.id)
          .order_by(Order.id.desc())
+         .limit(limit)
+         .offset(offset)
      )
```

## Impact

- **Default behavior:** Returns the 50 most recent orders (newest first).
- **Backward compatibility:** Fully backward-compatible — callers that do not pass `limit`/`offset` receive the default 50 records.
- **Frontend impact:** None — the frontend never specified a limit and 50 records is more than sufficient for the dashboard view.
- **DB impact:** Converts an unbounded sequential scan to a bounded index seek at scale.

## Risk Assessment

Low. Default `limit=50` covers all current use cases. Callers may pass larger values if needed. No existing API contracts broken.

---
