import json
import time
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional
from sqlmodel import Session, select

from app.core.config import settings
from app.core.database import engine
from app.models.base import Project, Scene

from app.api.ws import ws_manager
from app.workflow.state import CreatorState
from app.workflow.graph import (
    ingest_node,
    research_node,
    viral_strategy_node,
    script_writer_node,
    storyboard_node
)

# Active execution registry to support thread-safe task cancellation
class WorkflowRegistry:
    active_tasks: Dict[str, asyncio.Task] = {}
    active_subprocesses: Dict[str, List[asyncio.subprocess.Process]] = {}

    @classmethod
    def register_task(cls, project_id: str, task: asyncio.Task):
        cls.active_tasks[project_id] = task
        cls.active_subprocesses[project_id] = []

    @classmethod
    def deregister_task(cls, project_id: str):
        cls.active_tasks.pop(project_id, None)
        cls.active_subprocesses.pop(project_id, None)

    @classmethod
    def register_subprocess(cls, project_id: str, proc: asyncio.subprocess.Process):
        if project_id in cls.active_subprocesses:
            cls.active_subprocesses[project_id].append(proc)

    @classmethod
    async def cancel_project(cls, project_id: str) -> bool:
        task = cls.active_tasks.get(project_id)
        cancelled = False
        
        # Kill child subprocesses first
        procs = cls.active_subprocesses.get(project_id, [])
        for proc in procs:
            try:
                print(f"[Cancellation] Terminating subprocess PID {proc.pid} for project {project_id}")
                proc.kill()
                await proc.wait()
            except Exception as e:
                print(f"[Cancellation Error] Failed to kill process: {e}")

        if task:
            print(f"[Cancellation] Cancelling asyncio Task for project {project_id}")
            task.cancel()
            cancelled = True

        # Update database state to CANCELLED
        with Session(engine) as session:
            project = session.get(Project, project_id)
            if project:
                project.status = "CANCELLED"
                session.add(project)
                session.commit()
                
        cls.deregister_task(project_id)
        
        await ws_manager.send_to_project(project_id, {
            "type": "workflow.cancelled",
            "project_id": project_id,
            "message": "Generation stopped by user.",
            "timestamp": datetime.utcnow().isoformat()
        })
        return cancelled


# Queue-isolation runner utilizing separate asyncio Tasks
class QueueRunner:
    @classmethod
    def get_project_state(cls, project_id: str, session: Session) -> dict:
        project = session.get(Project, project_id)
        if not project:
            raise ValueError("Project not found")

        scenes = session.exec(
            select(Scene).where(Scene.project_id == project_id).order_by(Scene.scene_index)
        ).all()

        hooks = []
        if project.viral_hooks:
            try:
                hooks = json.loads(project.viral_hooks)
            except Exception:
                hooks = [project.viral_hooks]

        return {
            "project_id": project.id,
            "source_type": project.source_type,
            "source_input": project.raw_content or "",
            "raw_text": project.raw_content or "",
            "summary": project.summary or "",
            "viral_hooks": hooks,
            "viral_cta": project.viral_cta or "",
            "script": project.script or "",
            "duration_target": project.duration_target or "30s",
            "scenes": [
                {
                    "index": s.scene_index,
                    "narration": s.narration_text,
                    "image_prompt": s.image_prompt,
                    "subtitle": s.subtitle_text,
                    "image_path_1": s.image_path_1,
                    "image_path_2": s.image_path_2,
                    "selected_image_index": s.selected_image_index,
                    "transition_style": s.transition_style,
                    "scene_duration": s.scene_duration
                } for s in scenes
            ],
            "current_step": project.current_stage,
            "errors": []
        }

    @classmethod
    async def run_stage_task(cls, project_id: str, target_stage: str, prompt_override: Optional[str] = None, tone_override: Optional[str] = None):
        """Runs a single workflow stage node as an event-driven task."""
        print(f"[QueueRunner] Launching stage: '{target_stage}' for project: {project_id}")
        start_time = time.time()
        
        # Broadcast stage started
        await ws_manager.send_to_project(project_id, {
            "type": "workflow.stage.started",
            "project_id": project_id,
            "stage": target_stage,
            "message": f"Starting {target_stage.replace('_', ' ').title()} stage...",
            "timestamp": datetime.utcnow().isoformat()
        })

        try:
            # 1. Fetch current state
            with Session(engine) as session:
                project = session.get(Project, project_id)
                if not project:
                    raise ValueError(f"Project {project_id} not found")
                
                # Lock mechanism: verify no other execution is running
                if project.status in ["RESEARCHING", "STRATEGIZING", "WRITING", "STORYBOARDING", "GENERATING", "RENDERING"]:
                    print(f"[QueueRunner Lock] Project is already active with status: {project.status}")
                    return

                # Update status
                status_map = {
                    "ingest": "EXTRACTING",
                    "research": "RESEARCHING",
                    "viral_strategy": "STRATEGIZING",
                    "script": "WRITING",
                    "storyboard": "STORYBOARDING"
                }
                project.status = status_map.get(target_stage, "PENDING")
                project.current_stage = target_stage
                session.add(project)
                session.commit()
                
                state = cls.get_project_state(project_id, session)

            # Store any overrides in state
            if prompt_override or tone_override:
                try:
                    meta = json.loads(project.stage_metadata or "{}")
                except Exception:
                    meta = {}
                if target_stage not in meta:
                    meta[target_stage] = {}
                if prompt_override:
                    meta[target_stage]["prompt_override"] = prompt_override
                if tone_override:
                    meta[target_stage]["tone_override"] = tone_override
                
                # Save override meta
                with Session(engine) as session:
                    p = session.get(Project, project_id)
                    p.stage_metadata = json.dumps(meta)
                    session.add(p)
                    session.commit()

            # 2. Invoke appropriate node function
            if target_stage == "ingest":
                state = await ingest_node(state)
                if state.get("errors"):
                    raise RuntimeError(state["errors"][-1])
                # Ingest completed successfully, auto-transition to research
                cls.schedule_stage(project_id, "research")
                return
            elif target_stage == "research":

                state = await research_node(state)
            elif target_stage == "viral_strategy":
                state = await viral_strategy_node(state)
            elif target_stage == "script":
                state = await script_writer_node(state)
            elif target_stage == "storyboard":
                state = await storyboard_node(state)
            else:
                raise ValueError(f"Unknown stage: {target_stage}")

            if state.get("errors"):
                raise RuntimeError(state["errors"][-1])

            # 3. Complete and save state
            duration_ms = int((time.time() - start_time) * 1000)
            
            with Session(engine) as session:
                project = session.get(Project, project_id)
                if not project:
                    return

                # Update stage metadata
                try:
                    meta = json.loads(project.stage_metadata or "{}")
                except Exception:
                    meta = {}

                # Create structured metadata for this stage
                stage_details = meta.get(target_stage, {})
                stage_details.update({
                    "status": "waiting_approval",
                    "started_at": datetime.fromtimestamp(start_time).isoformat(),
                    "completed_at": datetime.utcnow().isoformat(),
                    "duration_ms": duration_ms,
                    "tokens": len(json.dumps(state)) // 4, # rough estimation
                    "model": settings.OLLAMA_MODEL if target_stage != "ingest" else "python-sdk",
                    "reruns": stage_details.get("reruns", 0) + (1 if stage_details.get("status") else 0),
                    "reasoning_summary": f"Completed {target_stage} successfully using {settings.OLLAMA_MODEL} locally."
                })
                meta[target_stage] = stage_details
                
                project.stage_metadata = json.dumps(meta)
                # Set project status to pending approval
                project.status = "REVIEW_PENDING"
                project.current_stage = target_stage
                project.stage_approved = False
                
                session.add(project)
                session.commit()

            # Broadcast stage completed event
            await ws_manager.send_to_project(project_id, {
                "type": "workflow.stage.completed",
                "project_id": project_id,
                "stage": target_stage,
                "message": f"{target_stage.replace('_', ' ').title()} stage complete! Paused for approval.",
                "duration_ms": duration_ms,
                "timestamp": datetime.utcnow().isoformat()
            })

        except asyncio.CancelledError:
            print(f"[QueueRunner] Task cancelled for project {project_id} during stage {target_stage}")
            raise
        except Exception as e:
            print(f"[QueueRunner Error] Stage {target_stage} failed: {e}")
            duration_ms = int((time.time() - start_time) * 1000)
            with Session(engine) as session:
                project = session.get(Project, project_id)
                if project:
                    project.status = "FAILED"
                    # Log failure in stage metadata
                    try:
                        meta = json.loads(project.stage_metadata or "{}")
                    except Exception:
                        meta = {}
                    stage_details = meta.get(target_stage, {})
                    stage_details.update({
                        "status": "failed",
                        "error_message": str(e),
                        "completed_at": datetime.utcnow().isoformat()
                    })
                    meta[target_stage] = stage_details
                    project.stage_metadata = json.dumps(meta)
                    session.add(project)
                    session.commit()

            await ws_manager.send_to_project(project_id, {
                "type": "workflow.stage.failed",
                "project_id": project_id,
                "stage": target_stage,
                "message": f"Stage {target_stage} failed: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            })

    @classmethod
    def schedule_stage(cls, project_id: str, stage: str, prompt_override: Optional[str] = None, tone_override: Optional[str] = None):
        """Schedules a stage to run in a separate asyncio Task."""
        # Cancel any active running task for this project first
        if project_id in WorkflowRegistry.active_tasks:
            WorkflowRegistry.active_tasks[project_id].cancel()
            
        task = asyncio.create_task(
            cls.run_stage_task(project_id, stage, prompt_override, tone_override)
        )
        WorkflowRegistry.register_task(project_id, task)
        
        # Add callback to cleanup registry on completion
        def cleanup_callback(t):
            WorkflowRegistry.deregister_task(project_id)
            
        task.add_done_callback(cleanup_callback)
        return task
