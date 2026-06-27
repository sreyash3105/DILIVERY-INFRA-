# Change Record — CR-001

| Field | Detail |
|-------|--------|
| **Change ID** | CR-001 |
| **Date** | 2026-06-27 |
| **Type** | Bug Fix |
| **Severity** | Critical |
| **Author** | Sreyash Baishkhiyar |
| **Status** | Applied |

---

## Description

Fixed a `NameError` runtime crash in `AssignmentService.assign_driver()`.

## File Changed

`backend/app/services/assignment_service.py`

## Function / Location

`AssignmentService.assign_driver()` — approximately lines 54–63

## Root Cause

`redis_client.publish(f"delivery:{order.id}", json.dumps(pub_payload))` was called, but `pub_payload` was never defined anywhere in the `assign_driver()` method. The variable existed only in the separate `trigger_assignment()` method. This caused a `NameError` exception at runtime on every call to `POST /deliveries/{id}/assign-driver`.

## Change Made

Defined `pub_payload` as a dictionary directly before the `publish()` call:

```diff
  await db.commit()
  await db.refresh(order)

+ # Broadcast live status update via WebSocket
+ pub_payload = {
+     "delivery_id": order.id,
+     "status": order.status,
+     "driver_id": order.driver_id
+ }
  await redis_client.publish(f"delivery:{order.id}", json.dumps(pub_payload))
```

## Impact

- **Before:** Every manual driver assignment via `POST /deliveries/{id}/assign-driver` crashed with `NameError: name 'pub_payload' is not defined`.
- **After:** Manual assignments complete successfully and broadcast the WebSocket event as intended.

## Risk Assessment

Low. The fix adds the missing variable definition. No logic altered.

---
