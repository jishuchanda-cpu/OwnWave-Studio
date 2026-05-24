from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List, Dict
import json

class ConnectionManager:
    def __init__(self):
        # Maps project ID to list of websockets listening to it
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, project_id: str, websocket: WebSocket):
        await websocket.accept()
        if project_id not in self.active_connections:
            self.active_connections[project_id] = []
        self.active_connections[project_id].append(websocket)
        print(f"WS Client connected to project: {project_id}")

    def disconnect(self, project_id: str, websocket: WebSocket):
        if project_id in self.active_connections:
            if websocket in self.active_connections[project_id]:
                self.active_connections[project_id].remove(websocket)
            if not self.active_connections[project_id]:
                del self.active_connections[project_id]
        print(f"WS Client disconnected from project: {project_id}")

    async def send_to_project(self, project_id: str, message: dict):
        """Sends JSON message to all clients listening to a specific project."""
        if project_id in self.active_connections:
            # Create a copy of the list to avoid mutations during iteration
            for connection in list(self.active_connections[project_id]):
                try:
                    await connection.send_json(message)
                except Exception:
                    # Connection might be closed, clean up dynamically
                    if connection in self.active_connections[project_id]:
                        self.active_connections[project_id].remove(connection)

    async def broadcast_status(self, project_id: str, status: str, progress: float = 0.0, step_message: str = ""):
        """Broadcasts structured progress message."""
        payload = {
            "project_id": project_id,
            "status": status,
            "progress": progress,
            "message": step_message
        }
        await self.send_to_project(project_id, payload)


# Instantiate global manager
ws_manager = ConnectionManager()

# Router definition
router = APIRouter()

@router.websocket("/ws/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    await ws_manager.connect(project_id, websocket)
    try:
        # Keep connection open, listen for client keepalives/replies if any
        while True:
            data = await websocket.receive_text()
            # Echo or process if needed, else ignore
    except WebSocketDisconnect:
        ws_manager.disconnect(project_id, websocket)
    except Exception as e:
        print(f"WebSocket error on project {project_id}: {e}")
        ws_manager.disconnect(project_id, websocket)
