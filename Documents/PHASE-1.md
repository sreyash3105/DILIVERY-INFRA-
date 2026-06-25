Phase 1 is the most important phase to get right — everything else in the project sits on top of what you build here. The goal is a clean, runnable foundation: database schema, Docker environment, FastAPI skeleton, and a working order state machine — before a single line of WebSocket or Redis code is written.

**Week 1 — environment and schema**

Start by getting Docker Compose running with two services: your FastAPI app container and a PostgreSQL container with the PostGIS extension enabled. The `postgis/postgis:16-3.4` Docker image includes PostGIS out of the box, so no extra setup needed.

Your core tables for Phase 1 are: `tenants` (API key, name, created_at), `drivers` (tenant_id, name, phone, status, current_location as a PostGIS `GEOGRAPHY(POINT)` column), `orders` (tenant_id, status enum, pickup/dropoff as GEOGRAPHY(POINT) columns, timestamps), and `order_state_transitions` (order_id, from_status, to_status, created_at) for the audit trail. Add a GiST spatial index on the driver location column now — you'll need it in Phase 3.

Set up Alembic from the start, not as an afterthought. Every schema change should go through migrations so your dev, test, and prod environments stay in sync.

**Week 2 — endpoints and state machine**

Build the state machine as a pure Python class first, completely separate from FastAPI. Define an enum for the 5 states (`CREATED`, `ASSIGNED`, `PICKED_UP`, `IN_TRANSIT`, `DELIVERED`) plus `CANCELLED`, and a dict of valid transitions. The key rule: any attempt to move to an invalid state raises a `InvalidTransitionError` that your FastAPI exception handler catches and returns as a 422. Every valid transition writes a row to `order_state_transitions`.

Your Phase 1 endpoints are:

```
POST   /deliveries          → create order (CREATED state)
GET    /deliveries/{id}     → fetch order + current status
PATCH  /deliveries/{id}/status → trigger state transition
POST   /drivers             → register a driver
GET    /drivers/{id}        → fetch driver
POST   /drivers/{id}/location → update driver location (geometry write)
```

API key auth is a FastAPI `Depends()` function that reads the `X-API-Key` header, looks up the tenant, and injects the tenant object into the route. Keep it simple — no JWT, no OAuth. You can harden it later.

**The deliverable at the end of Phase 1** is: `docker compose up` gives you a running API where you can create an order, watch it move through the state machine via PATCH calls, and see every transition recorded in the audit log. Fully testable with `httpx` or Postman. No real-time, no Redis, no Celery — just solid synchronous plumbing that the rest of the project depends on.
