from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import logging
from app.services.connection_manager import manager
from app.middleware.metrics import WEBSOCKET_CONNECTIONS_ACTIVE

router = APIRouter()
logger = logging.getLogger("WebSocketRoutes")

@router.websocket("/track/{delivery_id}")
async def track_delivery(websocket: WebSocket, delivery_id: int):
    logger.info(f"WebSocket connecting to track delivery {delivery_id}")
    WEBSOCKET_CONNECTIONS_ACTIVE.labels(endpoint="/track").inc()
    await manager.connect_track(delivery_id, websocket)
    try:
        while True:
            # Keep connection open. We ignore messages sent by the client tracking page
            # since tracking is one-way (server to client) for customer tracking.
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected from tracking delivery {delivery_id}")
    except Exception as e:
        logger.error(f"WebSocket error in tracking delivery {delivery_id}: {e}")
    finally:
        await manager.disconnect_track(delivery_id, websocket)
        WEBSOCKET_CONNECTIONS_ACTIVE.labels(endpoint="/track").dec()

@router.websocket("/fleet")
async def track_fleet(websocket: WebSocket):
    logger.info("WebSocket connecting to fleet tracking")
    WEBSOCKET_CONNECTIONS_ACTIVE.labels(endpoint="/fleet").inc()
    await manager.connect_fleet(websocket)
    try:
        while True:
            # Keep connection open
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected from fleet tracking")
    except Exception as e:
        logger.error(f"WebSocket error in fleet tracking: {e}")
    finally:
        await manager.disconnect_fleet(websocket)
        WEBSOCKET_CONNECTIONS_ACTIVE.labels(endpoint="/fleet").dec()

