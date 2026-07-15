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
        # 재연결 시 교체(replace-on-reconnect): 클라이언트의 이전 ws.close()는
        # 비동기라 서버가 연결 종료를 인지하기 전에 같은 유저의 새 연결이 먼저
        # 등록될 수 있다(React StrictMode 이중 마운트 등). 옛 연결의 disconnect를
        # 기다리지 않고 같은 user_id를 여기서 바로 정리해 "한 유저 = 한 연결"을
        # 서버가 직접 보장한다.
        conns = self._connections.setdefault(project_id, [])
        self._connections[project_id] = [
            (u, ws) for u, ws in conns if u.user_id != user.user_id
        ]
        self._connections[project_id].append((user, websocket))
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
        self, project_id: str, target: str, updated_by: str, exclude_user_id: int | None = None
    ) -> None:
        for u, ws in self._connections.get(project_id, []):
            if u.user_id == exclude_user_id:
                continue
            await ws.send_json(
                {"type": "content_updated", "target": target, "updated_by": updated_by}
            )

    async def broadcast_skill_changed(
        self,
        project_id: str,
        action: str,
        skill_id: str,
        updated_by: str,
        exclude_user_id: int | None = None,
    ) -> None:
        for u, ws in self._connections.get(project_id, []):
            if u.user_id == exclude_user_id:
                continue
            await ws.send_json(
                {
                    "type": "skill_changed",
                    "action": action,
                    "skill_id": skill_id,
                    "updated_by": updated_by,
                }
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
