import logging
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from app.models import User
from app.utils.dependencies import get_current_user_ws
from app.ws.manager import notification_manager

logger = logging.getLogger(__name__)

ws_routes = APIRouter(tags=["websocket"])


@ws_routes.websocket("/ws/notifications")
async def ws_notifications(
    websocket: WebSocket,
    current_user: User = Depends(get_current_user_ws),
):
    await notification_manager.connect(websocket, current_user.id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await notification_manager.disconnect(websocket, current_user.id)
    except Exception as e:
        logger.error(f"WS erro user_id={current_user.id}: {e}")
        await notification_manager.disconnect(websocket, current_user.id)
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
