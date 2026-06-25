Phase 2 is where the platform stops feeling like a CRUD app and starts feeling like actual infrastructure. The core idea: drivers push location updates, and every subscribed client sees them instantly through WebSockets — with Redis Pub/Sub as the broadcast layer in between.

Two diagrams — first the overall architecture of how data flows, then the WebSocket fan-out mechanism specifically.The fan-out is the tricky part to get right. Here's how a single location update propagates from one driver to potentially thousands of connected clients:Here's everything to build, week by week.

**Week 1 — Redis setup + location publish pipeline**

Start by adding Redis to your Docker Compose alongside PostgreSQL. You'll use `aioredis` (or the `redis[asyncio]` package) for async pub/sub. The first thing to build is the publish side: when a driver hits `POST /drivers/location`, the endpoint does two things concurrently using `asyncio.gather` — writes the new geometry to PostgreSQL and publishes a JSON message to a Redis channel named `delivery:{delivery_id}`. The message shape is simple: `{"driver_id": "...", "lat": 12.34, "lng": 56.78, "timestamp": "..."}`.

The channel-per-delivery design is important. Don't use a single global channel — you want clients subscribed to only the specific delivery they care about, so the fan-out is scoped. This also makes Phase 3's per-delivery ETA recalculation natural to hook in later.

**Week 2 — WebSocket endpoints + connection manager**

Build a `ConnectionManager` class that holds a dict of `delivery_id → list[WebSocket]`. It needs three methods: `connect(delivery_id, websocket)`, `disconnect(delivery_id, websocket)`, and `broadcast(delivery_id, message)`. The broadcast iterates the connection list and sends to each — if a send fails (stale connection), remove it from the list silently.

Your two WebSocket endpoints are:

```
WS /track/{delivery_id}   → customer/merchant subscribes to one delivery
WS /fleet                 → ops dashboard, subscribes to all active deliveries
```

The `GET /track/{delivery_id}` endpoint accepts the WebSocket upgrade, registers the connection with the manager, then enters a loop waiting for the Redis subscriber to push messages. The subscriber itself runs as a background `asyncio.Task` that's started when the first client connects to a delivery and cancelled when the last one disconnects.

**Redis Streams — the event log**

Alongside Pub/Sub (which is ephemeral — messages are gone if no subscriber is listening), write every location update to a Redis Stream keyed `stream:locations`. Use `XADD` with a `*` ID so Redis auto-generates timestamps. This gives you a durable, replayable log of every location event — Phase 4 will consume it for analytics, and it's useful for debugging. Think of Pub/Sub as the live broadcast and Streams as the persistent record.

**The deliverable at the end of Phase 2:** open two browser tabs both connected to `WS /track/{delivery_id}`, fire a `POST /drivers/location` from a third terminal, and watch both tabs receive the update in under 100ms. That's the moment this stops feeling like a project and starts feeling like a platform.
