import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import init_db
from app.api.router import api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB tables on startup
    init_db()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# CORS Configuration
# Enable Next.js dev server on port 3000 to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include core API routing
app.include_router(api_router, prefix=settings.API_V1_STR)

# Mount project media folder statically to serve images, audio wavs, and final mp4s
# This enables HTML5 video tags to stream compiled video clips with Range HTTP support
projects_media_dir = settings.STORAGE_DIR / "projects"
os.makedirs(projects_media_dir, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(projects_media_dir)), name="media")

@app.get("/")
def read_root():
    return {"message": "AI Creator API is running smoothly."}
