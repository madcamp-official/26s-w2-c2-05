import jwt
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlmodel import Session

from ..auth import decode_access_token
from ..deps import get_db
from ..models import ProjectMember, User

router = APIRouter()


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, list[tuple[User, WebSocket]]] = {}

    async def connect(self, project_id: str, user: User, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(project_id, []).append((user, websocket))
        await self._broadcast(project_id)

    async def disconnect(self, project_id: str, websocket: WebSocket) -> None:
        conns = self._connections.get(project_id, [])
        self._connections[project_id] = [(u, ws) for u, ws in conns if ws is not websocket]
        await self._broadcast(project_id)

    async def _broadcast(self, project_id: str) -> None:
        online_users = [
            {"user_id": u.user_id, "username": u.username}
            for u, _ in self._connections.get(project_id, [])
        ]
        for _, ws in self._connections.get(project_id, []):
            await ws.send_json({"online_users": online_users})

    async def broadcast_content_updated(
        self, project_id: str, target: str, updated_by: str
    ) -> None:
        for _, ws in self._connections.get(project_id, []):
            await ws.send_json(
                {"type": "content_updated", "target": target, "updated_by": updated_by}
            )


manager = ConnectionManager()


@router.websocket("/ws/projects/{project_id}")
async def project_presence(
    websocket: WebSocket, project_id: str, token: str, db: Session = Depends(get_db)
) -> None:
    try:
        user_id = decode_access_token(token)
    except jwt.PyJWTError:
        await websocket.close(code=1008)
        return
    user = db.get(User, user_id)
    if user is None or db.get(ProjectMember, (project_id, user.user_id)) is None:
        await websocket.close(code=1008)
        return

    await manager.connect(project_id, user, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(project_id, websocket)
