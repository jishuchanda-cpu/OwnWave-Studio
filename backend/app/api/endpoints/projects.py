import os
import json
from uuid import uuid4
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select

from app.core.database import get_db
from app.core.config import settings
from app.models.base import Project, Scene
from app.api.ws import ws_manager
from app.workflow.runner import QueueRunner, WorkflowRegistry

# Import media services
from app.services.comfyui_service import ComfyUIService
from app.services.tts_service import TTSService
from app.services.video_service import VideoService

router = APIRouter()

# Instantiate services
comfyui_service = ComfyUIService()
tts_service = TTSService()

# Helper function to avoid import loops
def get_engine_helper():
    from app.core.database import engine
    return engine

# ------------------------------------------------------------------------
# Pydantic Schemas for Requests
# ------------------------------------------------------------------------

class ProjectCreate(BaseModel):
    title: str
    source_type: str  # "TEXT", "PDF", "URL"
    source_input: str  # URL link or raw text (or path to uploaded pdf)
    aspect_ratio: str = "9:16"
    duration_target: str = "30s" # "30s", "1m", "1m30s", "3m"
    voice_option: Optional[str] = "english_female"

class SceneUpdate(BaseModel):
    id: str
    narration_text: str
    image_prompt: str
    subtitle_text: str
    image_path_1: Optional[str] = None
    image_path_2: Optional[str] = None
    selected_image_index: Optional[int] = 0
    transition_style: Optional[str] = "fade"
    scene_duration: Optional[float] = None

class ScenesBatchUpdate(BaseModel):
    scenes: List[SceneUpdate]

class StageEdit(BaseModel):
    content_text: Optional[str] = None
    prompt_override: Optional[str] = None
    tone_override: Optional[str] = None

# ------------------------------------------------------------------------
# Background Tasks
# ------------------------------------------------------------------------

async def generate_project_media_task(project_id: str):
    """Generates ComfyUI images, Piper TTS voiceovers, compiles scenes, and merges them."""
    with Session(engine := get_engine_helper()) as session:
        project = session.get(Project, project_id)
        if not project:
            return
        
        project.status = "GENERATING"
        session.add(project)
        session.commit()
        
        aspect_ratio = project.aspect_ratio
        
        # Load scenes in order
        db_scenes = session.exec(
            select(Scene).where(Scene.project_id == project_id).order_by(Scene.scene_index)
        ).all()
        
        # Map scenes to dicts to avoid DetachedInstanceError
        scenes_data = []
        for s in db_scenes:
            scenes_data.append({
                "id": s.id,
                "scene_index": s.scene_index,
                "image_prompt": s.image_prompt,
                "narration_text": s.narration_text,
                "subtitle_text": s.subtitle_text,
                "selected_image_index": s.selected_image_index,
                "transition_style": s.transition_style,
                "scene_duration": s.scene_duration
            })
        
    num_scenes = len(scenes_data)
    if num_scenes == 0:
        await ws_manager.broadcast_status(project_id, "FAILED", 0.0, "No scenes found for this project.")
        return

    project_dir = settings.STORAGE_DIR / "projects" / project_id
    os.makedirs(project_dir, exist_ok=True)

    await ws_manager.broadcast_status(project_id, "GENERATING", 5.0, "Starting media generation...")

    compiled_mp4_paths = []
    
    for i, scene_data in enumerate(scenes_data):
        # Cancel safety check
        with Session(engine) as session:
            proj = session.get(Project, project_id)
            if proj and proj.status == "CANCELLED":
                print(f"[Media Gen] Cancel requested for project {project_id}")
                return

        idx = scene_data["scene_index"]
        scene_id = scene_data["id"]
        image_prompt = scene_data["image_prompt"]
        narration_text = scene_data["narration_text"]
        subtitle_text = scene_data["subtitle_text"]
        selected_img_idx = scene_data["selected_image_index"]
        transition_style = scene_data["transition_style"] or "fade"
        custom_scene_duration = scene_data["scene_duration"]
        
        await ws_manager.broadcast_status(
            project_id, "GENERATING", 
            10.0 + (i / num_scenes * 75.0), 
            f"Generating Scene {idx + 1} of {num_scenes} (2 images)..."
        )
        
        # Paths for files
        img_path_1 = str(project_dir / f"scene_{idx}_img1.png")
        img_path_2 = str(project_dir / f"scene_{idx}_img2.png")
        wav_path = str(project_dir / f"scene_{idx}.wav")
        scene_mp4_path = str(project_dir / f"scene_{idx}.mp4")

        # Update scene status
        with Session(engine) as session:
            db_scene = session.get(Scene, scene_id)
            if db_scene:
                db_scene.status = "GENERATING"
                session.add(db_scene)
                session.commit()

        # Step A: Image Generation (ComfyUI) with automated cinematic style suffix
        style_suffix = ", Ultra cinematic scene, emotional atmosphere, dramatic lighting, volumetric fog, ultra detailed, realistic textures, film grain, depth of field, moody shadows, cinematic composition, high contrast, realistic skin texture, epic environment, 8k, storytelling frame, emotional realism"
        full_image_prompt = image_prompt.strip()
        if not full_image_prompt.endswith("."):
            full_image_prompt += "."
        full_image_prompt += style_suffix

        # Generate image slot 1
        img1_success = await comfyui_service.generate_image(
            prompt=full_image_prompt,
            output_path=img_path_1,
            aspect_ratio=aspect_ratio
        )
        
        # Generate image slot 2
        img2_success = await comfyui_service.generate_image(
            prompt=full_image_prompt,
            output_path=img_path_2,
            aspect_ratio=aspect_ratio
        )
        
        # Step B: Voice Narration (Piper TTS)
        tts_success, audio_duration = await tts_service.generate_narration(
            text=narration_text,
            output_wav_path=wav_path,
            project_id=project_id
        )
        
        # Determine image slot to compile
        chosen_img_path = img_path_2 if (selected_img_idx == 1 and img2_success) else img_path_1
        if not os.path.exists(chosen_img_path):
            # Fallback to whatever exists
            chosen_img_path = img_path_1 if os.path.exists(img_path_1) else img_path_2

        scene_duration_to_use = custom_scene_duration if custom_scene_duration else audio_duration

        # Step C: Scene video compiling
        scene_compiled = False
        if os.path.exists(chosen_img_path) and tts_success:
            scene_compiled = await VideoService.compile_scene(
                image_path=chosen_img_path,
                audio_path=wav_path,
                duration=scene_duration_to_use,
                subtitle_text=subtitle_text,
                output_mp4_path=scene_mp4_path,
                aspect_ratio=aspect_ratio,
                scene_index=idx,
                project_id=project_id,
                transition_style=transition_style
            )

        with Session(engine) as session:
            db_scene = session.get(Scene, scene_id)
            if db_scene:
                if scene_compiled:
                    db_scene.status = "COMPLETED"
                    db_scene.image_path_1 = img_path_1
                    db_scene.image_path_2 = img_path_2
                    db_scene.image_path = chosen_img_path
                    db_scene.audio_path = wav_path
                    db_scene.audio_duration = audio_duration
                    compiled_mp4_paths.append(scene_mp4_path)
                else:
                    db_scene.status = "FAILED"
                session.add(db_scene)
                session.commit()

        if not scene_compiled:
            with Session(engine) as session:
                project = session.get(Project, project_id)
                if project and project.status != "CANCELLED":
                    project.status = "FAILED"
                    session.add(project)
                    session.commit()
            await ws_manager.broadcast_status(project_id, "FAILED", 0.0, f"Compilation failed at scene {idx + 1}")
            return

    # Step D: Concat scenes into final MP4
    await ws_manager.broadcast_status(project_id, "RENDERING", 90.0, "Concatenating scenes into final video...")
    final_output_path = str(project_dir / "final.mp4")
    
    concat_success = await VideoService.concatenate_scenes(compiled_mp4_paths, final_output_path, project_id=project_id)

    with Session(engine) as session:
        project = session.get(Project, project_id)
        if project:
            if project.status != "CANCELLED":
                if concat_success:
                    project.status = "COMPLETED"
                else:
                    project.status = "FAILED"
                session.add(project)
                session.commit()

    if concat_success:
        await ws_manager.broadcast_status(project_id, "COMPLETED", 100.0, "Video composition complete!")
    else:
        await ws_manager.broadcast_status(project_id, "FAILED", 0.0, "Concatenation failure during final render.")


async def regenerate_single_scene_task(project_id: str, scene_id: str):
    """Regenerates files for one scene and rebuilds the final export."""
    with Session(engine := get_engine_helper()) as session:
        scene = session.get(Scene, scene_id)
        project = session.get(Project, project_id)
        if not scene or not project:
            return
            
        scene.status = "GENERATING"
        session.add(scene)
        session.commit()

        aspect_ratio = project.aspect_ratio
        idx = scene.scene_index
        image_prompt = scene.image_prompt
        narration_text = scene.narration_text
        subtitle_text = scene.subtitle_text
        selected_img_idx = scene.selected_image_index
        transition_style = scene.transition_style or "fade"
        custom_scene_duration = scene.scene_duration

    project_dir = settings.STORAGE_DIR / "projects" / project_id
    
    await ws_manager.broadcast_status(project_id, "GENERATING", 50.0, f"Regenerating Scene {idx + 1}...")

    img_path_1 = str(project_dir / f"scene_{idx}_img1.png")
    img_path_2 = str(project_dir / f"scene_{idx}_img2.png")
    wav_path = str(project_dir / f"scene_{idx}.wav")
    scene_mp4_path = str(project_dir / f"scene_{idx}.mp4")

    # Step A: Image with automated cinematic style suffix
    style_suffix = ", Ultra cinematic scene, emotional atmosphere, dramatic lighting, volumetric fog, ultra detailed, realistic textures, film grain, depth of field, moody shadows, cinematic composition, high contrast, realistic skin texture, epic environment, 8k, storytelling frame, emotional realism"
    full_image_prompt = image_prompt.strip()
    if not full_image_prompt.endswith("."):
        full_image_prompt += "."
    full_image_prompt += style_suffix

    img1_success = await comfyui_service.generate_image(
        prompt=full_image_prompt,
        output_path=img_path_1,
        aspect_ratio=aspect_ratio
    )
    img2_success = await comfyui_service.generate_image(
        prompt=full_image_prompt,
        output_path=img_path_2,
        aspect_ratio=aspect_ratio
    )
    
    # Step B: Voice
    tts_success, audio_duration = await tts_service.generate_narration(
        text=narration_text,
        output_wav_path=wav_path,
        project_id=project_id
    )
    
    chosen_img_path = img_path_2 if (selected_img_idx == 1 and img2_success) else img_path_1
    if not os.path.exists(chosen_img_path):
        chosen_img_path = img_path_1 if os.path.exists(img_path_1) else img_path_2

    scene_duration_to_use = custom_scene_duration if custom_scene_duration else audio_duration

    # Step C: Scene video compiling
    scene_compiled = False
    if os.path.exists(chosen_img_path) and tts_success:
        scene_compiled = await VideoService.compile_scene(
            image_path=chosen_img_path,
            audio_path=wav_path,
            duration=scene_duration_to_use,
            subtitle_text=subtitle_text,
            output_mp4_path=scene_mp4_path,
            aspect_ratio=aspect_ratio,
            scene_index=idx,
            project_id=project_id,
            transition_style=transition_style
        )

    with Session(engine) as session:
        db_scene = session.get(Scene, scene_id)
        if db_scene:
            if scene_compiled:
                db_scene.status = "COMPLETED"
                db_scene.image_path_1 = img_path_1
                db_scene.image_path_2 = img_path_2
                db_scene.image_path = chosen_img_path
                db_scene.audio_path = wav_path
                db_scene.audio_duration = audio_duration
            else:
                db_scene.status = "FAILED"
            session.add(db_scene)
            session.commit()

    if not scene_compiled:
        await ws_manager.broadcast_status(project_id, "FAILED", 0.0, f"Failed to compile Scene {idx + 1}")
        return

    # Step D: Re-concat final MP4
    await ws_manager.broadcast_status(project_id, "RENDERING", 80.0, "Re-rendering final video export...")
    
    # Reload scenes to fetch all valid completed paths
    with Session(engine) as session:
        scenes = session.exec(
            select(Scene).where(Scene.project_id == project_id).order_by(Scene.scene_index)
        ).all()
        
    compiled_mp4_paths = []
    for s in scenes:
        p = str(project_dir / f"scene_{s.scene_index}.mp4")
        if os.path.exists(p) and s.status == "COMPLETED":
            compiled_mp4_paths.append(p)

    final_output_path = str(project_dir / "final.mp4")
    concat_success = await VideoService.concatenate_scenes(compiled_mp4_paths, final_output_path, project_id=project_id)

    with Session(engine) as session:
        project = session.get(Project, project_id)
        if project:
            project.status = "COMPLETED" if concat_success else "FAILED"
            session.add(project)
            session.commit()

    if concat_success:
        await ws_manager.broadcast_status(project_id, "COMPLETED", 100.0, "Single-scene update successful!")
    else:
        await ws_manager.broadcast_status(project_id, "FAILED", 0.0, "Re-concat failed during single-scene update.")

# ------------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------------

@router.post("/projects", response_model=Project)
async def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    project_id = str(uuid4())
    project = Project(
        id=project_id,
        title=payload.title,
        status="PENDING",
        source_type=payload.source_type,
        aspect_ratio=payload.aspect_ratio,
        duration_target=payload.duration_target,
        voice_option=payload.voice_option,
        current_stage="ingest",
        stage_approved=False,
        stage_metadata="{}",
        raw_content=payload.source_input
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/projects", response_model=List[Project])
async def list_projects(db: Session = Depends(get_db)):
    statement = select(Project).order_by(Project.created_at.desc())
    return db.exec(statement).all()


@router.get("/projects/{project_id}")
async def get_project(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Load scenes explicitly (needed since SQLModel may not auto-serialize relationships)
    scenes_list = db.exec(
        select(Scene).where(Scene.project_id == project_id).order_by(Scene.scene_index)
    ).all()
    
    project_dict = {
        "id": project.id,
        "title": project.title,
        "status": project.status,
        "source_type": project.source_type,
        "raw_content": project.raw_content,
        "summary": project.summary,
        "viral_hooks": project.viral_hooks,
        "viral_cta": project.viral_cta,
        "script": project.script,
        "aspect_ratio": project.aspect_ratio,
        "duration_target": project.duration_target,
        "voice_option": project.voice_option,
        "current_stage": project.current_stage,
        "stage_approved": project.stage_approved,
        "stage_metadata": project.stage_metadata,
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
        "scenes": [
            {
                "id": s.id,
                "project_id": s.project_id,
                "scene_index": s.scene_index,
                "narration_text": s.narration_text,
                "image_prompt": s.image_prompt,
                "subtitle_text": s.subtitle_text,
                "image_path": s.image_path,
                "image_path_1": s.image_path_1,
                "image_path_2": s.image_path_2,
                "selected_image_index": s.selected_image_index,
                "transition_style": s.transition_style,
                "scene_duration": s.scene_duration,
                "audio_path": s.audio_path,
                "audio_duration": s.audio_duration,
                "status": s.status,
            }
            for s in scenes_list
        ]
    }
    return project_dict


@router.get("/projects/{project_id}/scenes", response_model=List[Scene])
async def get_project_scenes(project_id: str, db: Session = Depends(get_db)):
    """Returns all scenes for a project ordered by scene_index."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    scenes = db.exec(
        select(Scene).where(Scene.project_id == project_id).order_by(Scene.scene_index)
    ).all()
    return scenes


@router.post("/projects/{project_id}/generate-storyboard")
async def generate_storyboard(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Reset status
    project.status = "PENDING"
    project.current_stage = "ingest"
    project.stage_approved = False
    db.add(project)
    db.commit()
    
    QueueRunner.schedule_stage(project_id, "ingest")
    return {"message": "Workflow ingestion started in background"}



@router.post("/projects/{project_id}/approve-stage")
async def approve_stage(project_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    current = project.current_stage
    
    if current == "research":
        next_stage = "viral_strategy"
    elif current == "viral_strategy":
        next_stage = "script"
    elif current == "script":
        next_stage = "storyboard"
    elif current == "storyboard":
        background_tasks.add_task(generate_project_media_task, project_id=project.id)
        return {"message": "Storyboard approved. Media generation started."}
    else:
        raise HTTPException(status_code=400, detail=f"Cannot approve stage in current state: {current}")
        
    project.status = "PENDING"
    project.current_stage = next_stage
    project.stage_approved = True
    db.add(project)
    db.commit()
    
    QueueRunner.schedule_stage(project_id, next_stage)
    return {"message": f"Stage {current} approved. Starting {next_stage}."}


@router.post("/projects/{project_id}/rerun-stage")
async def rerun_stage(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    current = project.current_stage
    if not current:
        raise HTTPException(status_code=400, detail="No active stage to rerun")
        
    project.status = "PENDING"
    project.stage_approved = False
    db.add(project)
    db.commit()
    
    QueueRunner.schedule_stage(project_id, current)
    return {"message": f"Re-running stage: {current}"}


@router.post("/projects/{project_id}/edit-stage")
async def edit_stage(project_id: str, payload: StageEdit, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    current = project.current_stage
    
    # Update stage metadata
    try:
        meta = json.loads(project.stage_metadata or "{}")
    except Exception:
        meta = {}
        
    if current not in meta:
        meta[current] = {}
        
    if payload.prompt_override is not None:
        meta[current]["prompt_override"] = payload.prompt_override
    if payload.tone_override is not None:
        meta[current]["tone_override"] = payload.tone_override
        
    project.stage_metadata = json.dumps(meta)
    
    # Save text modifications if provided
    if payload.content_text is not None:
        if current == "research":
            project.summary = payload.content_text
        elif current == "viral_strategy":
            try:
                # Validate JSON hooks format
                json.loads(payload.content_text)
                project.viral_hooks = payload.content_text
            except Exception:
                project.viral_hooks = json.dumps([payload.content_text])
        elif current == "script":
            project.script = payload.content_text
            
    db.add(project)
    db.commit()
    
    # If LLM prompts were edited, we must re-generate using Ollama
    if payload.prompt_override or payload.tone_override:
        project.status = "PENDING"
        project.stage_approved = False
        db.add(project)
        db.commit()
        
        QueueRunner.schedule_stage(project_id, current, payload.prompt_override, payload.tone_override)
        return {"message": f"Stage {current} parameters updated. Regenerating..."}
    else:
        # Otherwise, directly save and approve/advance
        if current == "research":
            next_stage = "viral_strategy"
        elif current == "viral_strategy":
            next_stage = "script"
        elif current == "script":
            next_stage = "storyboard"
        elif current == "storyboard":
            project.status = "GENERATING"
            project.stage_approved = True
            db.add(project)
            db.commit()
            background_tasks.add_task(generate_project_media_task, project_id=project.id)
            return {"message": "Storyboard edits saved. Media generation started."}
            
        project.status = "PENDING"
        project.current_stage = next_stage
        project.stage_approved = True
        db.add(project)
        db.commit()
        
        QueueRunner.schedule_stage(project_id, next_stage)
        return {"message": f"Stage {current} changes saved. Starting {next_stage}."}


@router.post("/projects/{project_id}/cancel")
async def cancel_project(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    cancelled = await WorkflowRegistry.cancel_project(project_id)
    return {"message": "Project cancellation request processed.", "cancelled": cancelled}


@router.put("/projects/{project_id}/scenes")
async def update_scenes(project_id: str, payload: ScenesBatchUpdate, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    for item in payload.scenes:
        scene = db.get(Scene, item.id)
        if scene and scene.project_id == project_id:
            scene.narration_text = item.narration_text
            scene.image_prompt = item.image_prompt
            scene.subtitle_text = item.subtitle_text
            if item.image_path_1 is not None:
                scene.image_path_1 = item.image_path_1
            if item.image_path_2 is not None:
                scene.image_path_2 = item.image_path_2
            if item.selected_image_index is not None:
                scene.selected_image_index = item.selected_image_index
            if item.transition_style is not None:
                scene.transition_style = item.transition_style
            if item.scene_duration is not None:
                scene.scene_duration = item.scene_duration
            db.add(scene)
            
    db.commit()
    return {"message": "Storyboard scenes updated successfully"}


@router.post("/projects/{project_id}/approve")
async def approve_and_generate(project_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    background_tasks.add_task(generate_project_media_task, project_id=project.id)
    return {"message": "Generation pipeline approved and started in background"}


@router.post("/projects/{project_id}/regenerate-scene/{scene_id}")
async def regenerate_single_scene(project_id: str, scene_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    scene = db.get(Scene, scene_id)
    if not scene or scene.project_id != project_id:
        raise HTTPException(status_code=404, detail="Scene not found")
        
    background_tasks.add_task(regenerate_single_scene_task, project_id=project.id, scene_id=scene.id)
    return {"message": f"Regeneration task for scene {scene.scene_index + 1} started in background"}


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Delete storage assets physically
    project_dir = settings.STORAGE_DIR / "projects" / project_id
    if project_dir.exists():
        import shutil
        shutil.rmtree(project_dir, ignore_errors=True)
        
    db.delete(project)
    db.commit()
    return {"message": "Project and all associated media deleted"}
