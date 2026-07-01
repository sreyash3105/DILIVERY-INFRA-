# Change Record — CR-003

| Field | Detail |
|-------|--------|
| **Change ID** | CR-003 |
| **Date** | 2026-06-27 |
| **Type** | Bug Fix |
| **Severity** | Medium |
| **Author** | Sreyash Baishkhiyar |
| **Status** | Applied |

---

## Description

Fixed a Redis cache key collision between the `/eta` and `/live-location` endpoints.

## Files Changed

1. `backend/app/api/deliveries.py` — changed the cache key read in `get_delivery_eta()`
2. `backend/app/services/route_service.py` — added a dedicated ETA cache write in `recalculate_eta()`

---

### Part A — `deliveries.py`

**Function:** `get_delivery_eta()` — line 285

**Root Cause:**
The `/eta` endpoint used `delivery:{id}:live_location` as its Redis cache key — the exact same key as the `/live-location` endpoint. This meant:
- If the cached value did not contain `eta_minutes`, the ETA endpoint silently fell through to a fresh compute (inefficient).
- Any future writer storing ETA data under the live-location key would corrupt location responses and vice versa.

**Change Made:**

```diff
- # Check cache first
- cache_key = f"delivery:{delivery_id}:live_location"
+ # Check cache first — use a dedicated ETA key, separate from live_location
+ cache_key = f"delivery:{delivery_id}:eta"
```

---

### Part B — `route_service.py`

**Function:** `RouteService.recalculate_eta()` — line 110

**Root Cause:**
`recalculate_eta()` was the only code path that wrote ETA data back to Redis. It was writing to `delivery:{id}:live_location`, meaning the new `delivery:{id}:eta` key (from Part A) would always be a cache miss and the ETA cache would never be populated.

**Change Made:**

```diff
  # Cache the full telemetry payload under live_location (unchanged)
  await redis_client.setex(f"delivery:{order.id}:live_location", 300, json.dumps(pub_payload))

+ # Cache a dedicated ETA snapshot under its own key (used by /eta endpoint)
+ eta_payload = {
+     "delivery_id": order.id,
+     "eta_minutes": route_data["eta_minutes"],
+     "distance_meters": route_data["distance_meters"],
+     "stage": stage
+ }
+ await redis_client.setex(f"delivery:{order.id}:eta", 300, json.dumps(eta_payload))
```

---

## Impact

- **Before:** `/eta` endpoint always missed its cache; `/live-location` and `/eta` shared a key and could corrupt each other.
- **After:** Each endpoint has its own isolated Redis key with a 5-minute TTL. Repeat `/eta` calls are served from cache (~1ms) instead of triggering a DB lookup + Haversine compute.

## Risk Assessment

Low. The `/live-location` endpoint and WebSocket consumers continue to read from `delivery:{id}:live_location` which is untouched. No existing callers are affected.

---
