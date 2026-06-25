import asyncio
import json
import logging
from typing import Dict, List
from fastapi import WebSocket
from app.db.redis import redis_client

logger = logging.getLogger("ConnectionManager")

class ConnectionManager:
    def __init__(self):
        # Maps delivery_id -> list of WebSockets tracking it
        self.delivery_connections: Dict[int, List[WebSocket]] = {}
        # List of global fleet monitoring WebSockets
        self.fleet_connections: List[WebSocket] = []
        # Maps delivery_id -> asyncio.Task running the Redis pub/sub listener
        self.redis_tasks: Dict[int, asyncio.Task] = {}

    async def connect_track(self, delivery_id: int, websocket: WebSocket):
        await websocket.accept()
        if delivery_id not in self.delivery_connections:
            self.delivery_connections[delivery_id] = []
        self.delivery_connections[delivery_id].append(websocket)
        
        # Start Redis subscription listener if this is the first client connecting
        if len(self.delivery_connections[delivery_id]) == 1:
            self.redis_tasks[delivery_id] = asyncio.create_task(
                self._redis_subscription_listener(delivery_id)
            )
            logger.info(f"Started Redis subscriber for delivery {delivery_id}")

    async def disconnect_track(self, delivery_id: int, websocket: WebSocket):
        if delivery_id in self.delivery_connections:
            if websocket in self.delivery_connections[delivery_id]:
                self.delivery_connections[delivery_id].remove(websocket)
            
            # Clean up empty delivery lists and cancel Redis subscription task
            if not self.delivery_connections[delivery_id]:
                del self.delivery_connections[delivery_id]
                if delivery_id in self.redis_tasks:
                    self.redis_tasks[delivery_id].cancel()
                    del self.redis_tasks[delivery_id]
                    logger.info(f"Stopped Redis subscriber for delivery {delivery_id}")

    async def connect_fleet(self, websocket: WebSocket):
        await websocket.accept()
        self.fleet_connections.append(websocket)
        logger.info("New client connected to global fleet tracking")

    async def disconnect_fleet(self, websocket: WebSocket):
        if websocket in self.fleet_connections:
            self.fleet_connections.remove(websocket)
            logger.info("Client disconnected from global fleet tracking")

    async def broadcast_delivery(self, delivery_id: int, message_str: str):
        """Send message to all clients watching the delivery, and also to all fleet monitoring clients."""
        try:
            message_json = json.loads(message_str)
        except Exception:
            message_json = {"raw": message_str}

        # 1. Send to delivery-specific clients
        if delivery_id in self.delivery_connections:
            stale_websockets = []
            for ws in self.delivery_connections[delivery_id]:
                try:
                    await ws.send_json(message_json)
                except Exception:
                    stale_websockets.append(ws)
            
            # Clean up disconnected WS clients silently
            for ws in stale_websockets:
                await self.disconnect_track(delivery_id, ws)

        # 2. Send to global fleet ops clients
        stale_fleet = []
        for ws in self.fleet_connections:
            try:
                # Enrich message for fleet view to indicate which delivery it belongs to
                fleet_msg = {**message_json, "delivery_id": delivery_id}
                await ws.send_json(fleet_msg)
            except Exception:
                stale_fleet.append(ws)
                
        for ws in stale_fleet:
            await self.disconnect_fleet(ws)

    async def _redis_subscription_listener(self, delivery_id: int):
        """Background listener subscribing to a Redis channel and broadcasting updates to local WebSocket clients."""
        pubsub = redis_client.pubsub()
        channel_name = f"delivery:{delivery_id}"
        await pubsub.subscribe(channel_name)
        
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = message["data"]
                    await self.broadcast_delivery(delivery_id, data)
        except asyncio.CancelledError:
            logger.info(f"Redis listener for delivery {delivery_id} cancelled.")
        except Exception as e:
            logger.error(f"Error in Redis listener for delivery {delivery_id}: {e}")
        finally:
            await pubsub.unsubscribe(channel_name)
            await pubsub.close()

# Global connection manager instance
manager = ConnectionManager()
