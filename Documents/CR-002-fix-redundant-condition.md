# Change Record — CR-002

| Field | Detail |
|-------|--------|
| **Change ID** | CR-002 |
| **Date** | 2026-06-27 |
| **Type** | Bug Fix |
| **Severity** | Medium |
| **Author** | Sreyash Baishkhiyar |
| **Status** | Applied |

---

## Description

Removed a logically redundant and ambiguous compound condition in `DeliveryService.update_status()`.

## File Changed

`backend/app/services/delivery_service.py`

## Function / Location

`DeliveryService.update_status()` — line 94

## Root Cause

The condition controlling driver status reset on delivery completion was:

```python
if (validated_status == OrderStatus.DELIVERED or order.status == OrderStatus.IN_TRANSIT and validated_status == OrderStatus.DELIVERED) or validated_status in [OrderStatus.DELIVERED, OrderStatus.CANCELLED]:
```

Due to Python operator precedence (`and` binds tighter than `or`), the middle sub-expression `order.status == IN_TRANSIT and validated_status == DELIVERED` is entirely subsumed by the final `in [DELIVERED, CANCELLED]` check. The condition was equivalent to just the `in` check but appeared more complex, creating confusion and a maintenance risk.

## Change Made

```diff
- if (validated_status == OrderStatus.DELIVERED or order.status == OrderStatus.IN_TRANSIT and validated_status == OrderStatus.DELIVERED) or validated_status in [OrderStatus.DELIVERED, OrderStatus.CANCELLED]:
+ if validated_status in [OrderStatus.DELIVERED, OrderStatus.CANCELLED]:
```

## Impact

- **Behavior:** No change — the evaluated result is mathematically identical.
- **Readability:** Condition is now unambiguous and self-documenting.
- **Maintenance:** Eliminates future risk of misinterpreting the condition during modifications.

## Risk Assessment

None. Pure simplification with identical logical output, verified via operator precedence analysis.

---
