# Change Record — CR-007

| Field | Detail |
|-------|--------|
| **Change ID** | CR-007 |
| **Date** | 2026-06-27 |
| **Type** | Performance Improvement |
| **Severity** | Medium |
| **Author** | Sreyash Baishkhiyar |
| **Status** | Applied |

---

## Description

Increased the Fleet dashboard's main data polling interval from 5 seconds to 10 seconds to reduce unnecessary backend request volume.

## File Changed

`frontend/src/pages/Fleet.tsx`

## Function / Location

`useEffect` polling block — line 106

## Root Cause

The Fleet dashboard polled two backend endpoints every 5 seconds unconditionally:
- `GET /deliveries`
- `GET /analytics/observability/vitals`

This generated **24 backend requests per minute per open browser tab**, regardless of whether any data had changed. With multiple simultaneous users, this creates significant unnecessary load on both the FastAPI application and the PostgreSQL database.

## Change Made

```diff
  const interval = setInterval(() => {
    fetchDeliveries();
    fetchVitals();
- }, 5000);
+ }, 10000); // 10s — halves backend load vs 5s with no visible UX impact
```

## Impact

- **Before:** 24 backend requests per minute per tab (12 × `/deliveries` + 12 × `/vitals`)
- **After:** 12 backend requests per minute per tab (6 × `/deliveries` + 6 × `/vitals`)
- **Reduction:** 50% fewer polling requests per client
- **UX impact:** None — delivery status updates visible within 10 seconds, which is imperceptible for fleet operations use
- **Health check polling:** Unchanged at 15-second interval (separate interval, not affected)

## Risk Assessment

None. The polling interval is an operational tuning parameter. 10 seconds is well within acceptable latency for a fleet management dashboard. Real-time driver location updates continue to flow via WebSockets independently of this polling.

---
