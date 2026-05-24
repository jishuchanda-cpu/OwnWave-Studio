import os
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Creator Backend"
    API_V1_STR: str = "/api/v1"
    
    # Storage and database config
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    STORAGE_DIR: Path = BASE_DIR / "storage"
    DATABASE_URL: str = f"sqlite:///{STORAGE_DIR}/creator.db"
    
    # Local AI & Media Engine dependencies
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "llama3.2:3b"
    
    COMFYUI_HOST: str = "127.0.0.1:8188"
    COMFYUI_HTTP_URL: str = f"http://{COMFYUI_HOST}"
    COMFYUI_WS_URL: str = f"ws://{COMFYUI_HOST}/ws"
    
    # Standalone Piper settings
    PIPER_BIN_PATH: str = "piper"  # Assumes pre-installed or in backend container/path
    PIPER_VOICE_MODEL: str = "en_US-lessac-medium" # Standard voice
    
    class Config:
        case_sensitive = True

settings = Settings()

# Ensure storage directories exist
os.makedirs(settings.STORAGE_DIR, exist_ok=True)
os.makedirs(settings.STORAGE_DIR / "projects", exist_ok=True)
os.makedirs(settings.STORAGE_DIR / "voices", exist_ok=True)
os.makedirs(settings.STORAGE_DIR / "cache", exist_ok=True)
