from typing import List, Dict, Any, TypedDict
from pydantic import BaseModel, Field

class SceneState(BaseModel):
    index: int
    narration: str = Field(description="The spoken narration text for this scene.")
    image_prompt: str = Field(description="Visual detail description for ComfyUI.")
    subtitle: str = Field(description="Clean subtitle text matching the narration.")

class CreatorState(TypedDict):
    project_id: str
    source_type: str        # "TEXT", "PDF", "URL"
    source_input: str       # Either raw text, filepath, or URL
    raw_text: str
    summary: str
    viral_hooks: List[str]
    viral_cta: str
    script: str
    duration_target: str    # "30s", "1m", "1m30s", "3m"
    scenes: List[Dict[str, Any]]
    current_step: str
    errors: List[str]

