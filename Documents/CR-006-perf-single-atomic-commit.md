# Change Record — CR-006

| Field | Detail |
|-------|--------|
| **Change ID** | CR-006 |
| **Date** | 2026-06-27 |
| **Type** | Performance Improvement |
| **Severity** | Medium |
| **Author** | Sreyash Baishkhiyar |
| **Status** | Applied |

---

## Description

Eliminated a redundant database commit in `create_delivery()` by using `flush()` instead of `commit()` after the initial order insert, allowing both the order row and its initial state transition to be persisted in a single atomic transaction.

## File Changed

`backend/app/services/delivery_service.py`

## Function / Location

`DeliveryService.create_delivery()` — lines 21–33

## Root Cause

`create_delivery()` performed two sequential `await db.commit()` calls:
1. **Commit 1** — to persist the `Order` row and obtain the auto-generated primary key (`db_order.id`)
2. **Commit 2** — to persist the initial `OrderStateTransition` row, which requires `db_order.id` as a foreign key

Each `commit()` is a full round-trip to PostgreSQL. The first commit existed only because `db_order.id` was needed before the transition could be constructed — but this can be accomplished without committing using SQLAlchemy's `flush()`.

## Change Made

```diff
  db.add(db_order)
- await db.commit()       # Commit 1 — only needed to get db_order.id
- await db.refresh(db_order)
+ # flush() sends the INSERT to Postgres within the current transaction,
+ # populating db_order.id without ending the transaction.
+ await db.flush()

  # Log initial state creation transition
  transition = OrderStateTransition(
      order_id=db_order.id,   # now available after flush
      from_status=OrderStatus.CREATED,
      to_status=OrderStatus.CREATED
  )
  db.add(transition)
- await db.commit()       # Commit 2
+ # Single commit — both the order and the transition persist atomically.
+ await db.commit()
+ await db.refresh(db_order)
```

## Impact

- **Performance:** Eliminates one full Postgres round-trip per order creation (saves ~1–5ms depending on network latency to DB).
- **Atomicity improvement:** Both the order and its initial transition now commit in one transaction. Previously, there was a brief window between Commit 1 and Commit 2 where an order could exist in the DB without a corresponding transition row.
- **Behavior:** Return value is identical — `db_order` is refreshed and returned as before.

## Risk Assessment

Low. `flush()` is a standard SQLAlchemy operation for exactly this use case. The transaction boundary is now moved to the single `commit()` call, which is semantically correct.

---
