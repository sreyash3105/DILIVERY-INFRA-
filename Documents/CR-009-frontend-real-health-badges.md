# Change Record — CR-009

| Field | Detail |
|-------|--------|
| **Change ID** | CR-009 |
| **Date** | 2026-06-27 |
| **Type** | Frontend Fix |
| **Severity** | Medium |
| **Author** | Sreyash Baishkhiyar |
| **Status** | Applied |

---

## Description

Fixed the system health status indicators in the Fleet dashboard to display accurate real-time service health by calling the actual `/health` API endpoint, replacing previous logic that derived health from unrelated state variables.

## File Changed

`frontend/src/pages/Fleet.tsx`

## Location

State declarations (~line 55), polling `useEffect` block (~lines 99–113), health badge derivations (~lines 259–263)

## Root Cause

The three service health booleans were derived from frontend state that had no meaningful relationship to actual service health:

```ts
// Previous — incorrect derivations
const isRedisUp    = systemVitals ? true : false;   // True if vitals loaded, not if Redis is up
const isPostgresUp = deliveries ? true : false;      // ALWAYS true — [] (empty array) is truthy in JS
const isCeleryUp   = systemVitals && systemVitals.queues ? true : false;
```

`isPostgresUp` was permanently `true` since an empty array `[]` is truthy in JavaScript, meaning the PostgreSQL badge would show green even if PostgreSQL was completely down and returning zero records.

The backend exposes a dedicated `/health` endpoint that performs actual ping checks against all three services and returns `"healthy"` or `"unhealthy: <reason>"` per service.

## Change Made

**Added state:**
```ts
const [healthStatus, setHealthStatus] = useState<{
  api: string; postgres: string; redis: string; celery: string;
} | null>(null);
```

**Added fetch function:**
```ts
const fetchHealth = async () => {
  try {
    const res = await fetch(`${serverUrl}/health`);
    if (res.ok || res.status === 503) {
      // 503 returned when partially unhealthy — body still contains per-service status
      const data = await res.json();
      setHealthStatus(data);
    }
  } catch (err) {}
};
```

**Polling integration:**
```ts
// Called immediately on mount and on a separate 15-second interval
// (slower than the 5s data poll — health status changes infrequently)
const healthInterval = setInterval(fetchHealth, 15000);
```

**Corrected badge derivations:**
```diff
- const isRedisUp    = systemVitals ? true : false;
- const isPostgresUp = deliveries ? true : false;
- const isCeleryUp   = systemVitals && systemVitals.queues ? true : false;
+ const isRedisUp    = healthStatus?.redis    === 'healthy';
+ const isPostgresUp = healthStatus?.postgres === 'healthy';
+ const isCeleryUp   = healthStatus?.celery   === 'healthy';
```

## Impact

- **Accuracy:** Health badges now reflect true service state from the backend's actual ping checks.
- **Fail-safe default:** Badges initialize to `false` (red) until the first `/health` response is received — the safe conservative default.
- **API key:** `/health` requires no authentication header — it is a public infrastructure endpoint.
- **503 handling:** The backend returns HTTP 503 when any service is unhealthy but still sends the full JSON body. The `fetchHealth` function correctly accepts 503 responses and parses the body.
- **Poll interval:** Health uses a 15-second interval, separate from the 10-second data poll, reducing unnecessary load.

## Risk Assessment

None. Health endpoint is read-only and public. Badge display is purely cosmetic. No write operations or data flow affected.

---
