# Phase 3 — Intelligent Dispatch & ETA Engine

Phase 3 is the most algorithmically interesting phase of the platform. This is where the system starts making decisions rather than simply storing or moving data.

Two difficult distributed-systems problems are introduced:

1. Efficiently finding the best available driver using geospatial indexing.
2. Ensuring concurrent assignment requests never assign the same driver to multiple deliveries.

A third subsystem is introduced after assignment:

3. Dynamic ETA calculation and live route updates.

---

# Order State Machine Extension

Phase 1 introduced:

```text
CREATED
ASSIGNED
PICKED_UP
IN_TRANSIT
DELIVERED
CANCELLED
```

Phase 3 extends this to support assignment workflows:

```text
CREATED
    ↓
DRIVER_PENDING
    ↓
ASSIGNED
    ↓
PICKED_UP
    ↓
IN_TRANSIT
    ↓
DELIVERED
```

Additional terminal state:

```text
NO_DRIVER_AVAILABLE
```

Used when all nearby drivers reject or timeout.

---

# Driver Lifecycle

Drivers now operate under a strict state machine:

```text
OFFLINE
    ↓
ONLINE
    ↓
BUSY
```

### OFFLINE

Driver cannot receive assignments.

Triggers:

* Explicit logout
* Heartbeat expiration
* Connectivity loss

### ONLINE

Driver is available for matching.

Requirements:

* Active heartbeat
* Recent location updates
* Not carrying a delivery

### BUSY

Driver currently owns an active delivery.

Cannot be selected by the assignment engine.

Transitions back to:

```text
ONLINE
```

after delivery completion.

---

# Assignment Attempt Tracking

Create a dedicated table:

```text
assignment_attempts
```

Schema:

```text
id
order_id
driver_id

status

OFFERED
ACCEPTED
REJECTED
TIMEOUT

created_at
updated_at
```

Purpose:

* Assignment audit trail
* Debugging
* Analytics
* Driver acceptance metrics

Every assignment offer must create a row.

---

# Week 1 — Redis GEO Index + Assignment Engine

Every driver location update from:

```text
POST /drivers/location
```

must also update a Redis GEO index.

Example:

```text
GEOADD drivers:active {lng} {lat} {driver_id}
```

Only ONLINE drivers should exist in the index.

OFFLINE and BUSY drivers are removed.

---

## Candidate Discovery

When a delivery enters:

```text
CREATED
```

the assignment engine executes:

```text
GEORADIUS drivers:active
```

using the pickup coordinates.

Example:

```text
GEORADIUS drivers:active
{lng}
{lat}
10 km
ASC
COUNT 10
```

Returns:

* Nearest drivers
* Sorted by distance
* Single Redis call

---

## Candidate Scoring

Candidate drivers are ranked.

Version 1 scoring:

```text
Distance  = 60%
Rating    = 30%
Workload  = 10%
```

Output:

```text
[Driver A]
[Driver B]
[Driver C]
```

ordered best-to-worst.

---

# Driver Offer Workflow

Assignment is not immediate.

The driver must explicitly accept.

Flow:

```text
CREATED
      ↓
Find Candidates
      ↓
Rank Candidates
      ↓
Offer To Driver A
      ↓
DRIVER_PENDING
```

Create:

```text
assignment_attempt
```

status:

```text
OFFERED
```

---

## Driver Accept

Driver clicks:

```text
Accept
```

Actions:

```text
assignment_attempt → ACCEPTED

order.status → ASSIGNED

driver.status → BUSY

assigned_driver_id → driver_id
```

---

## Driver Reject

Driver clicks:

```text
Reject
```

Actions:

```text
assignment_attempt → REJECTED
```

Add driver to:

```text
excluded_drivers
```

Run assignment engine again.

Offer next ranked driver.

---

# 30-Second Assignment Timeout

Every offer starts a timeout.

Example:

```text
Offer Driver A
      ↓
Start 30s Timer
```

If timer expires:

```text
assignment_attempt → TIMEOUT
```

Driver automatically added to:

```text
excluded_drivers
```

Assignment engine retries.

---

## Exhausted Candidate List

If all candidate drivers:

* Reject
* Timeout
* Become unavailable

Transition order to:

```text
NO_DRIVER_AVAILABLE
```

This state can later trigger:

* Notifications
* Retry workflows
* Manual intervention

---

# Distributed Locking

This is the most important concurrency control mechanism in the phase.

Problem:

```text
Order A
Order B
```

attempt assignment simultaneously.

Both identify:

```text
Driver X
```

as the nearest candidate.

Without locking:

```text
Driver X
assigned twice
```

---

## Redis Lock

Use:

```text
SET driver:{id}:lock 1 NX PX 5000
```

Where:

```text
NX
```

means:

```text
Only if key does not exist
```

and

```text
PX 5000
```

means:

```text
Auto-expire after 5 seconds
```

---

## Assignment Loop

```text
Try Driver A
```

Acquire lock.

### Lock Success

```text
Offer Driver A
```

Proceed.

### Lock Failure

```text
Try Driver B
```

Continue.

### All Locks Fail

Return:

```http
503 Service Unavailable
Retry-After: 5
```

---

## Lock Release

Always release:

```text
DEL driver:{id}:lock
```

inside:

```python
finally:
```

to avoid deadlocks.

---

# Driver Heartbeat System

Add:

```text
last_seen_at
```

to Driver.

Every location update refreshes:

```text
last_seen_at
```

---

## Ghost Driver Detection

If:

```text
current_time - last_seen_at > 90 seconds
```

then:

```text
driver.status = OFFLINE
```

and remove driver from:

```text
drivers:active
```

Redis GEO index.

This prevents assignment to dead clients.

---

# Week 2 — ETA Engine + Route Service

After assignment:

```text
ASSIGNED
```

the ETA subsystem activates.

---

## Route Provider

Use:

```text
OpenRouteService
```

API.

Compute:

### Driver → Pickup

Returns:

```text
pickup_eta
pickup_distance
```

### Pickup → Dropoff

Returns:

```text
delivery_eta
delivery_distance
```

---

## Route Caching

Store results in Redis:

```text
route:{origin}:{destination}
```

TTL:

```text
5 minutes
```

Reduces:

* External API calls
* Latency
* Cost

---

# Live ETA Recalculation

While order status:

```text
IN_TRANSIT
```

every driver location update triggers:

```text
Recalculate ETA
```

Process:

```text
Driver Moves
      ↓
Location Update
      ↓
ETA Recompute
      ↓
Redis Cache Check
      ↓
ORS Request (if needed)
      ↓
Broadcast New ETA
```

---

# WebSocket Integration

ETA changes should be published through:

```text
delivery:{id}
```

channel.

Connected clients instantly receive:

```json
{
  "delivery_id": 101,
  "eta_minutes": 7
}
```

without refreshing.

---

# New Phase 3 Endpoints

```http
POST /assign-driver
```

Trigger assignment engine.

---

```http
POST /deliveries/{id}/accept
```

Driver accepts assignment.

---

```http
POST /deliveries/{id}/reject
```

Driver rejects assignment.

---

```http
GET /deliveries/{id}/eta
```

Current ETA information.

---

```http
GET /deliveries/{id}/route
```

Route polyline and route metadata.

---

# Deliverable

At the end of Phase 3:

1. Create two deliveries near the same driver.
2. Trigger assignment simultaneously.
3. Verify distributed lock prevents double assignment.
4. Verify rejected drivers are skipped.
5. Verify timeout-based reassignment works.
6. Verify NO_DRIVER_AVAILABLE state works.
7. Verify heartbeat removes ghost drivers.
8. Verify ETA updates live through WebSockets.
9. Verify driver status transitions correctly between ONLINE, BUSY, and OFFLINE.

At that point the platform has evolved from a tracking system into a true logistics dispatching platform capable of making autonomous assignment decisions under concurrent load.
