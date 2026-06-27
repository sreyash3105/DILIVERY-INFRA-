# Changelog

**Author:** Sreyash Baishkhiyar

All notable changes to the Delivery Infrastructure Platform are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased] — 2026-06-27

### 🐛 Bug Fixes

- **`AssignmentService.assign_driver()`** — Fixed a `NameError` crash: `pub_payload` was referenced in the Redis `publish()` call but was never defined in the `assign_driver()` method body. The dict now exists before use. *(`backend/app/services/assignment_service.py`)*

- **`DeliveryService.update_status()`** — Removed a logically redundant and confusing compound condition that checked `DELIVERED` three times across nested `or`/`and` expressions. Simplified to a clean `in [DELIVERED, CANCELLED]` membership check. No behavior change. *(`backend/app/services/delivery_service.py`)*

- **`GET /{delivery_id}/eta` Redis cache collision** — The `/eta` endpoint was using `delivery:{id}:live_location` as its cache key — the same key as the `/live-location` endpoint. Changed to a dedicated `delivery:{id}:eta` key to prevent silent data corruption between the two endpoints. *(`backend/app/api/deliveries.py`)*

- **`RouteService.recalculate_eta()` cache write** — Closed the loop from the ETA cache fix above: `recalculate_eta()` now writes a clean ETA-only payload to `delivery:{id}:eta` (5-min TTL) in addition to the existing full telemetry write to `delivery:{id}:live_location`. Both keys remain independent. *(`backend/app/services/route_service.py`)*

---

### ⚡ Performance Improvements

- **`GET /deliveries` — Pagination added** — The list endpoint previously fetched every order for a tenant with no `LIMIT`. Added `limit` (default `50`) and `offset` (default `0`) query parameters. Fully backward-compatible — existing callers receive the 50 newest records. Prevents full table scans under production load. *(`backend/app/api/deliveries.py`)*

- **`georadius` → `geosearch`** — Replaced the deprecated `georadius` Redis command (removed in Redis 7.2+) with the modern `geosearch` equivalent. The result shape and parsing logic are identical; this is a forward-compatibility fix that prevents a silent crash on any Redis version upgrade. *(`backend/app/services/assignment_service.py`)*

- **`create_delivery()` — Single atomic commit** — `create_delivery()` previously executed two sequential `commit()` calls: one to generate the order PK, and one to insert the initial state transition. Replaced the first `commit()` + `refresh()` with `flush()`, which writes the `INSERT` and populates `db_order.id` within the current transaction. Both rows now commit together — eliminating one Postgres round-trip per order creation. *(`backend/app/services/delivery_service.py`)*

- **Frontend polling interval 5s → 10s** — The Fleet dashboard was polling `/deliveries` and `/analytics/observability/vitals` every 5 seconds. Increased to 10 seconds, halving the backend request rate per connected browser tab with no perceptible UX impact. Health check polling remains at 15 seconds. *(`frontend/src/pages/Fleet.tsx`)*

---

### 🔧 Refactoring & Code Quality

- **Moved `ghost_driver_cleanup_loop` to `app/tasks/cleanup.py`** — The background cleanup coroutine was defined as a top-level free function inside `main.py`, mixed into the app bootstrap code with locally-inlined imports and no docstrings. Extracted to `backend/app/tasks/cleanup.py` with a module docstring and function docstring. The `lifespan` wiring in `main.py` is unchanged. *(`backend/app/main.py`, `backend/app/tasks/cleanup.py` new)*

---

### 🎨 Frontend

- **System health badges now use real `/health` endpoint** — The Fleet dashboard's Redis, PostgreSQL, and Celery health indicators were derived from unrelated state (e.g., `isPostgresUp = deliveries ? true : false` — always true). Replaced with a dedicated `fetchHealth()` function that calls `GET /health` every 15 seconds and reads the actual service status strings (`"healthy"` / `"unhealthy: ..."`). Badges default to red until the first health response arrives. *(`frontend/src/pages/Fleet.tsx`)*

---

## Summary of Changes

| # | Category | File(s) | Impact |
|---|----------|---------|--------|
| 1 | 🐛 Bug Fix | `assignment_service.py` | Fixes runtime crash on manual driver assignment |
| 2 | 🐛 Bug Fix | `delivery_service.py` | Removes logically incorrect condition |
| 3 | 🐛 Bug Fix | `deliveries.py`, `route_service.py` | Fixes ETA Redis cache collision & write |
| 4 | ⚡ Perf | `deliveries.py` | Prevents full table scans at scale |
| 5 | ⚡ Perf | `assignment_service.py` | Redis 7.2+ compatibility |
| 6 | ⚡ Perf | `delivery_service.py` | -1 DB round-trip per order creation |
| 7 | ⚡ Perf | `Fleet.tsx` | -50% polling load per browser tab |
| 8 | 🔧 Refactor | `main.py`, `tasks/cleanup.py` | Cleanup task discoverability |
| 9 | 🎨 Frontend | `Fleet.tsx` | Accurate real-time service health indicators |
