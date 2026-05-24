from fastapi import APIRouter
from app.api.endpoints import projects
from app.api import ws

api_router = APIRouter()

# Include REST routes
api_router.include_router(projects.router)

# Include WebSocket routes
api_router.include_router(ws.router)
