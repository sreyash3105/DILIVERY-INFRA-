# Change Record — CR-005

| Field | Detail |
|-------|--------|
| **Change ID** | CR-005 |
| **Date** | 2026-06-27 |
| **Type** | Performance Improvement / Compatibility Fix |
| **Severity** | Critical (forward compatibility) |
| **Author** | Sreyash Baishkhiyar |
| **Status** | Applied |

---

## Description

Replaced the deprecated Redis `georadius` command with the modern `geosearch` equivalent to ensure compatibility with Redis 7.2+.

## File Changed

`backend/app/services/assignment_service.py`

## Function / Location

`AssignmentService.trigger_assignment()` — line 96

## Root Cause

The `georadius` command was deprecated in Redis 7.0 and **fully removed in Redis 7.2**. The project's Docker Compose uses `redis:7-alpine`, which may resolve to Redis 7.0.x currently. Any image update pulling Redis 7.2+ would silently crash every auto-assignment request with a Redis `UNKNOWN_COMMAND` error.

## Change Made

```diff
- # 3. Discover nearby active online drivers using Redis GEORADIUS
- # Search radius of 10km, ASC sorted
- candidates = await redis_client.georadius(
-     "drivers:active",
-     order.pickup_lng,
-     order.pickup_lat,
-     10,
-     unit="km",
-     withdist=True,
-     sort="ASC"
- )
+ # 3. Discover nearby active online drivers using Redis GEOSEARCH
+ # geosearch replaces the deprecated/removed georadius command (Redis 7.2+)
+ # FROMLONLAT + BYRADIUS is the modern equivalent — result shape is identical.
+ candidates = await redis_client.geosearch(
+     "drivers:active",
+     longitude=order.pickup_lng,
+     latitude=order.pickup_lat,
+     radius=10,
+     unit="km",
+     withdist=True,
+     sort="ASC"
+ )
```

## Impact

- **Result shape:** Identical — the candidate parsing loop below the call is **unchanged**.
- **Behavior:** No change to driver discovery logic, radius, scoring, or assignment flow.
- **Compatibility:** Now safe on Redis 7.0, 7.2, and all future versions.

## Risk Assessment

Very low. `geosearch` is a drop-in replacement with an identical return format. Validated against the `redis-py` library documentation.

---
