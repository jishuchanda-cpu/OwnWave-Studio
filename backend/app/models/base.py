from typing import List, Optional
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship

class Project(SQLModel, table=True):
    __tablename__ = "projects"
    
    id: str = Field(primary_key=True)
    title: str
    status: str  # PENDING, EXTRACTING, STRATEGY, WRITING, STORYBOARDING, REVIEW_PENDING, GENERATING, RENDERING, COMPLETED, FAILED, CANCELLED
    source_type: str  # TEXT, PDF, URL
    raw_content: Optional[str] = None
    summary: Optional[str] = None
    viral_hooks: Optional[str] = None  # JSON string of hooks list
    viral_cta: Optional[str] = None
    script: Optional[str] = None
    aspect_ratio: str = Field(default="9:16")
    duration_target: str = Field(default="30s")  # "30s", "1m", "1m30s", "3m"
    voice_option: Optional[str] = Field(default="english_female")
    current_stage: str = Field(default="ingest")  # "ingest", "research", "viral_strategy", "script", "storyboard", "completed"
    stage_approved: bool = Field(default=False)
    stage_metadata: Optional[str] = Field(default="{}") # JSON string containing stage logs, reasoning, tokens, etc.
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Establish relation to child scenes with cascade delete
    scenes: List["Scene"] = Relationship(
        back_populates="project",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "lazy": "selectin"}
    )

class Scene(SQLModel, table=True):
    __tablename__ = "scenes"
    
    id: str = Field(primary_key=True)
    project_id: str = Field(foreign_key="projects.id")
    scene_index: int
    narration_text: str
    image_prompt: str
    subtitle_text: str
    image_path: Optional[str] = None
    image_path_1: Optional[str] = None
    image_path_2: Optional[str] = None
    selected_image_index: int = Field(default=0)
    transition_style: Optional[str] = Field(default="fade")
    scene_duration: Optional[float] = None
    audio_path: Optional[str] = None
    audio_duration: Optional[float] = None
    status: str = Field(default="PENDING")  # PENDING, GENERATING, COMPLETED, FAILED
    
    project: "Project" = Relationship(back_populates="scenes")
