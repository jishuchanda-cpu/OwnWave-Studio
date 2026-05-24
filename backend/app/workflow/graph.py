import json
from sqlmodel import Session, select
from langgraph.graph import StateGraph, END

from app.core.database import engine
from app.models.base import Project, Scene
from app.workflow.state import CreatorState
from app.services.document_service import DocumentService
from app.services.vector_service import VectorService
from app.services.ollama_service import OllamaService

# Initialize helper services
ollama_service = OllamaService()
vector_service = VectorService()

# ------------------------------------------------------------------------
# Node Functions
# ------------------------------------------------------------------------

async def ingest_node(state: CreatorState) -> CreatorState:
    """Ingests source content, clean/chunks text and writes to ChromaDB."""
    project_id = state["project_id"]
    source_type = state["source_type"]
    source_input = state["source_input"]
    
    # Update DB Status
    with Session(engine) as session:
        project = session.get(Project, project_id)
        if project:
            project.status = "EXTRACTING"
            session.add(project)
            session.commit()

    raw_text = ""
    if source_type == "TEXT":
        raw_text = DocumentService.extract_from_text(source_input)
    elif source_type == "PDF":
        raw_text = DocumentService.extract_from_pdf(source_input)
    elif source_type == "URL":
        raw_text = await DocumentService.extract_from_url(source_input)
        
    if not raw_text:
        state["errors"].append("No text could be extracted from the source.")
        return state

    # Chunk and index text into ChromaDB
    chunks = DocumentService.chunk_text(raw_text)
    if chunks:
        vector_service.add_chunks(project_id, chunks)

    # Save raw text to DB
    with Session(engine) as session:
        project = session.get(Project, project_id)
        if project:
            project.raw_content = raw_text
            project.status = "EXTRACTING_COMPLETE"
            session.add(project)
            session.commit()

    state["raw_text"] = raw_text
    state["current_step"] = "EXTRACTING_COMPLETE"
    return state


async def research_node(state: CreatorState) -> CreatorState:
    """Uses Ollama to summarize the extracted text and extract key metadata."""
    if state.get("errors"):
        return state
        
    project_id = state["project_id"]
    raw_text = state["raw_text"]
    
    # Update DB Status
    with Session(engine) as session:
        project = session.get(Project, project_id)
        if project:
            project.status = "RESEARCHING"
            session.add(project)
            session.commit()

    # Limit prompt input length to prevent local LLM context overflow (keep short for CPU inference)
    truncated_text = raw_text[:2000]
    
    system_prompt = (
        "You are an expert Content Research Agent. Your task is to analyze the source material and produce "
        "a concise summary and key insights. You must respond in valid JSON format only."
    )
    
    prompt = (
        f"Source Material:\n{truncated_text}\n\n"
        "Provide a high-quality summary (around 150 words) and a list of key insights.\n"
        "Your response MUST be JSON matching this schema:\n"
        "{\n"
        "  \"summary\": \"Concise overview of the material\",\n"
        "  \"insights\": [\"Insight 1\", \"Insight 2\"]\n"
        "}"
    )

    try:
        result = await ollama_service.generate_structured(prompt, system_prompt)
        summary = result.get("summary", "No summary generated.")
        
        # Save summary to DB
        with Session(engine) as session:
            project = session.get(Project, project_id)
            if project:
                project.summary = summary
                project.status = "RESEARCH_COMPLETE"
                session.add(project)
                session.commit()
                
        state["summary"] = summary
        state["current_step"] = "RESEARCH_COMPLETE"
    except Exception as e:
        state["errors"].append(f"Research failed: {str(e)}")
        with Session(engine) as session:
            project = session.get(Project, project_id)
            if project:
                project.status = "FAILED"
                session.add(project)
                session.commit()
                
    return state


async def viral_strategy_node(state: CreatorState) -> CreatorState:
    """Viral Strategy Agent: designs high-retention hooks and custom CTAs."""
    if state.get("errors"):
        return state
        
    project_id = state["project_id"]
    summary = state["summary"]
    
    voice_option = "english_female"
    with Session(engine) as session:
        project = session.get(Project, project_id)
        if project:
            voice_option = project.voice_option or "english_female"
            project.status = "STRATEGIZING"
            session.add(project)
            session.commit()

    system_prompt = (
        "You are an elite YouTube Shorts and TikTok retention strategist. You analyze content summaries to generate "
        "extremely powerful, curiosity-inducing hook lines (open-loops) optimized for the first 3 seconds, and high-retention "
        "Calls to Action (CTAs) that invite organic interaction without sounding transactional or boring. Respond strictly in JSON."
    )
    if voice_option == "hindi_male":
        system_prompt += (
            "\n\nCRITICAL INSTRUCTIONS:\n"
            "Write in conversational Indian Hindi-Hinglish.\n"
            "Avoid pure Hindi.\n"
            "Use modern YouTube storytelling tone.\n"
            "Keep sentences short and emotional.\n"
            "Add natural pauses."
        )
    
    prompt = (
        f"Summary of Content:\n{summary}\n\n"
        "Generate 3 distinct click-worthy hooks (first 3 seconds attention-grabbers, highly emotional/curiosity driven) and a final CTA that asks a rhetorical question followed by an organic share/engagement prompt (retention-safe).\n"
        "Your response MUST be JSON matching this schema:\n"
        "{\n"
        "  \"hooks\": [\"Hook Option 1\", \"Hook Option 2\", \"Hook Option 3\"],\n"
        "  \"cta\": \"Action-oriented retention-safe CTA\"\n"
        "}"
    )

    try:
        result = await ollama_service.generate_structured(prompt, system_prompt)
        hooks = result.get("hooks", ["Check this out!"])
        cta = result.get("cta", "Follow for more!")

        # Clean up and normalize hooks to be a list of strings
        cleaned_hooks = []
        if isinstance(hooks, list):
            for h in hooks:
                if isinstance(h, dict):
                    txt = h.get("hook") or h.get("text") or h.get("sentence") or json.dumps(h)
                    cleaned_hooks.append(str(txt))
                elif h:
                    cleaned_hooks.append(str(h))
        else:
            cleaned_hooks = [str(hooks)]
        if not cleaned_hooks:
            cleaned_hooks = ["Check this out!"]

        # Clean up and normalize CTA to be a single string
        cleaned_cta = "Follow for more!"
        if isinstance(cta, dict):
            cleaned_cta = cta.get("text") or cta.get("cta") or cta.get("prompt") or json.dumps(cta)
        elif cta:
            cleaned_cta = str(cta)

        with Session(engine) as session:
            project = session.get(Project, project_id)
            if project:
                project.viral_hooks = json.dumps(cleaned_hooks)
                project.viral_cta = cleaned_cta
                project.status = "STRATEGY_COMPLETE"
                session.add(project)
                session.commit()

        state["viral_hooks"] = cleaned_hooks
        state["viral_cta"] = cleaned_cta
        state["current_step"] = "STRATEGY_COMPLETE"
    except Exception as e:
        state["errors"].append(f"Strategy node failed: {str(e)}")
        with Session(engine) as session:
            project = session.get(Project, project_id)
            if project:
                project.status = "FAILED"
                session.add(project)
                session.commit()
                
    return state


async def script_writer_node(state: CreatorState) -> CreatorState:
    """Script Writer Agent: drafts continuous scene narration script."""
    if state.get("errors"):
        return state
        
    project_id = state["project_id"]
    summary = state["summary"]
    hooks = state["viral_hooks"]
    cta = state["viral_cta"]
    duration_target = state.get("duration_target", "30s")
    
    voice_option = "english_female"
    with Session(engine) as session:
        project = session.get(Project, project_id)
        if project:
            voice_option = project.voice_option or "english_female"
            project.status = "WRITING"
            session.add(project)
            session.commit()

    selected_hook = hooks[0] if hooks else "Look at this."
    
    print(f"[script_writer_node] Starting for project {project_id} with duration {duration_target}")
    
    system_prompt = (
        "You are a world-class cinematic script writer, viral storyteller, and emotional retention expert. "
        "You write highly immersive video scripts with perfect emotional pacing, rhythm, and tension. Output JSON only."
    )
    if voice_option == "hindi_male":
        system_prompt += (
            "\n\nCRITICAL INSTRUCTIONS:\n"
            "Write in conversational Indian Hindi-Hinglish.\n"
            "Avoid pure Hindi.\n"
            "Use modern YouTube storytelling tone.\n"
            "Keep sentences short and emotional.\n"
            "Add natural pauses."
        )

    # Determine targets based on duration
    if duration_target == "1m":
        word_target = "110 to 130 words"
        duration_desc = "1-minute"
        structure_guide = "Start with the hook, develop a 3-part narrative arc (rising tension, central message/climax, CTA)."
    elif duration_target == "1m30s":
        word_target = "170 to 195 words"
        duration_desc = "1-minute 30-second"
        structure_guide = "Start with the hook, build a slow cinematic narrative progression with suspenseful details, and finish with a strong emotional CTA."
    elif duration_target == "3m":
        word_target = "340 to 390 words"
        duration_desc = "3-minute"
        structure_guide = "Write a long-form detailed epic story with an introductory hook, multiple thematic chapters/sections building character or conflict, a climax, and final CTA."
    else: # 30s default
        word_target = "50 to 65 words"
        duration_desc = "30-second"
        structure_guide = "Start with the hook, build a dramatic conflict/curiosity gap, deliver a high-impact resolution, and end with the CTA."

    # Read overrides from stage metadata if they exist
    prompt_override = None
    tone_override = None
    with Session(engine) as session:
        project = session.get(Project, project_id)
        if project and project.stage_metadata:
            try:
                meta = json.loads(project.stage_metadata)
                script_meta = meta.get("script", {})
                prompt_override = script_meta.get("prompt_override")
                tone_override = script_meta.get("tone_override")
            except Exception:
                pass

    if prompt_override:
        prompt = (
            f"Topic: {summary[:500]}\n"
            f"Selected Hook: {selected_hook}\n"
            f"CTA: {cta}\n"
            f"Custom Instructions: {prompt_override}\n\n"
            f"Write a {duration_desc} narration script. Target word count is around {word_target}. {structure_guide}\n"
            "Use active verbs, suspenseful pacing, and emotional words. Keep sentences short and punchy.\n"
            "Respond in JSON: {\"script_text\": \"your script here\"}"
        )
    else:
        prompt = (
            f"Topic: {summary[:500]}\n"
            f"Hook: {selected_hook}\n"
            f"CTA: {cta}\n\n"
            f"Write a highly engaging {duration_desc} narration script. Start with the hook. "
            f"Target word count is around {word_target}. {structure_guide}\n"
            "Use active verbs, suspenseful pacing, and emotional words. Keep sentences short and punchy.\n"
            "Respond in JSON: {\"script_text\": \"your script here\"}"
        )

    if tone_override:
        prompt += f"\nMaintain this specific tone/style: {tone_override}"

    try:
        result = await ollama_service.generate_structured(prompt, system_prompt)
        script = result.get("script_text", "")

        with Session(engine) as session:
            project = session.get(Project, project_id)
            if project:
                project.script = script
                project.status = "WRITING_COMPLETE"
                session.add(project)
                session.commit()

        state["script"] = script
        state["current_step"] = "WRITING_COMPLETE"
    except Exception as e:
        state["errors"].append(f"Script writing failed: {str(e)}")
        with Session(engine) as session:
            project = session.get(Project, project_id)
            if project:
                project.status = "FAILED"
                session.add(project)
                session.commit()
                
    return state


async def storyboard_node(state: CreatorState) -> CreatorState:
    """Storyboard Agent: splits script into individual storyboard scenes."""
    if state.get("errors"):
        return state
        
    project_id = state["project_id"]
    script = state["script"]
    duration_target = state.get("duration_target", "30s")
    
    voice_option = "english_female"
    with Session(engine) as session:
        project = session.get(Project, project_id)
        if project:
            voice_option = project.voice_option or "english_female"
            project.status = "STORYBOARDING"
            session.add(project)
            session.commit()

    print(f"[storyboard_node] Starting for project {project_id} with duration {duration_target}")
    
    system_prompt = (
        "You are an expert Storyboard Director. You translate written scripts into distinct, visually stunning, "
        "and emotionally charged cinematic scene segments. Output JSON only."
    )
    if voice_option == "hindi_male":
        system_prompt += (
            "\n\nCRITICAL INSTRUCTIONS:\n"
            "Write in conversational Indian Hindi-Hinglish.\n"
            "Avoid pure Hindi.\n"
            "Use modern YouTube storytelling tone.\n"
            "Keep sentences short and emotional.\n"
            "Add natural pauses."
        )

    # Determine scenes count based on duration
    if duration_target == "1m":
        scene_count = 9
    elif duration_target == "1m30s":
        scene_count = 13
    elif duration_target == "3m":
        scene_count = 20
    else: # 30s default
        scene_count = 5

    # Check for overrides
    prompt_override = None
    with Session(engine) as session:
        project = session.get(Project, project_id)
        if project and project.stage_metadata:
            try:
                meta = json.loads(project.stage_metadata)
                story_meta = meta.get("storyboard", {})
                prompt_override = story_meta.get("prompt_override")
            except Exception:
                pass

    if prompt_override:
        prompt = (
            f"Script: {script}\n"
            f"Custom Instructions: {prompt_override}\n\n"
            f"Split the script into exactly {scene_count} sequential cinematic scenes. For each scene, specify:\n"
            f"- index (0 to {scene_count - 1})\n"
            "- narration: the specific chunk of the script spoken in this scene\n"
            "- subtitle: short, punchy sentence-case subtitles (max 4-5 words per scene segment, uppercase for key words)\n"
            "- image_prompt: a short, simple description of the visual scene (max 10-15 words, e.g., 'A warrior king standing on top of a mountain, sunset') (avoid style keywords, metadata, text, or watermarks).\n"
            "JSON format: {\"scenes\": [{\"index\": 0, \"narration\": \"...\", \"subtitle\": \"...\", \"image_prompt\": \"...\"}]}"
        )
    else:
        prompt = (
            f"Script: {script}\n\n"
            f"Split the script into exactly {scene_count} sequential cinematic scenes. For each scene, specify:\n"
            f"- index (0 to {scene_count - 1})\n"
            "- narration: the specific chunk of the script spoken in this scene\n"
            "- subtitle: short, punchy sentence-case subtitles (max 4-5 words per scene segment, uppercase for key words)\n"
            "- image_prompt: a short, simple description of the visual scene (max 10-15 words, e.g., 'A warrior king standing on top of a mountain, sunset') (avoid style keywords, metadata, text, or watermarks).\n"
            "JSON format: {\"scenes\": [{\"index\": 0, \"narration\": \"...\", \"subtitle\": \"...\", \"image_prompt\": \"...\"}]}"
        )

    try:
        result = await ollama_service.generate_structured(prompt, system_prompt)
        scenes_data = result.get("scenes", [])
        
        import re
        
        # Helper to build a scene dict from an LLM item
        def normalize_scene(index, item):
            return {
                "index": index,
                "narration": item.get("narration", "") if isinstance(item, dict) else str(item),
                "subtitle": item.get("subtitle", item.get("narration", "")) if isinstance(item, dict) else str(item),
                "image_prompt": item.get("image_prompt", "Photorealistic visual matching narration") if isinstance(item, dict) else "Cinematic scene"
            }
        
        final_scenes = []
        
        if isinstance(scenes_data, list) and len(scenes_data) > 0:
            # Use LLM data — trim or pad to match scene_count
            if len(scenes_data) >= scene_count:
                # Trim to exact count
                for index in range(scene_count):
                    final_scenes.append(normalize_scene(index, scenes_data[index]))
            else:
                # Use what we have, then pad by repeating the last scene's style
                print(f"[storyboard_node] LLM returned {len(scenes_data)} scenes (wanted {scene_count}). Using LLM data + padding.")
                for index, item in enumerate(scenes_data):
                    final_scenes.append(normalize_scene(index, item))
                # Pad remaining
                last = scenes_data[-1]
                for index in range(len(scenes_data), scene_count):
                    padded = normalize_scene(index, last)
                    padded["narration"] = f"[Continuation scene {index + 1}]"
                    padded["subtitle"] = f"SCENE {index + 1}"
                    final_scenes.append(padded)
        else:
            # LLM returned nothing useful — sentence-split the script
            print(f"[storyboard_node Fallback] LLM returned 0 scenes. Performing sentence-split fallback.")
            sentences = [s.strip() for s in re.split(r'[.!?\u2014]+', script) if s.strip()]
            if not sentences:
                sentences = [script]
                
            n = len(sentences)
            segments = []
            if n >= scene_count:
                step = n / scene_count
                for i in range(scene_count):
                    start = int(i * step)
                    end = int((i + 1) * step) if i < scene_count - 1 else n
                    segments.append(" ".join(sentences[start:end]) + ".")
            else:
                for i in range(scene_count):
                    segments.append(sentences[min(i, n - 1)] + ".")
                    
            for index in range(scene_count):
                narration = segments[index]
                words = narration.split()
                sub = " ".join(words[:4]).upper()
                img_p = f"Cinematic scene showing: {' '.join(words[:12])}"
                final_scenes.append({
                    "index": index,
                    "narration": narration,
                    "subtitle": sub,
                    "image_prompt": img_p
                })
        
        # Save generated scenes to database
        with Session(engine) as session:
            # Delete any existing scenes for clean re-generations
            existing_scenes = session.exec(select(Scene).where(Scene.project_id == project_id)).all()
            for s in existing_scenes:
                session.delete(s)
            
            for index, item in enumerate(final_scenes):
                scene = Scene(
                    id=f"{project_id}_scene_{index}",
                    project_id=project_id,
                    scene_index=index,
                    narration_text=item.get("narration", ""),
                    image_prompt=item.get("image_prompt", "Photorealistic visual matching narration"),
                    subtitle_text=item.get("subtitle", item.get("narration", "")),
                    status="PENDING",
                    transition_style="fade",
                    selected_image_index=0
                )
                session.add(scene)
                
            project = session.get(Project, project_id)
            if project:
                project.status = "REVIEW_PENDING"
                session.add(project)
                
            session.commit()

        state["scenes"] = final_scenes
        state["current_step"] = "REVIEW_PENDING"
    except Exception as e:
        state["errors"].append(f"Storyboarding failed: {str(e)}")
        with Session(engine) as session:
            project = session.get(Project, project_id)
            if project:
                project.status = "FAILED"
                session.add(project)
                session.commit()
                
    return state


# ------------------------------------------------------------------------
# LangGraph Workflow compilation
# ------------------------------------------------------------------------

workflow = StateGraph(CreatorState)

# Add Nodes
workflow.add_node("ingest", ingest_node)
workflow.add_node("research", research_node)
workflow.add_node("viral_strategy", viral_strategy_node)
workflow.add_node("script_writer", script_writer_node)
workflow.add_node("storyboard", storyboard_node)

# Set Entry and Sequential Edges
workflow.set_entry_point("ingest")
workflow.add_edge("ingest", "research")
workflow.add_edge("research", "viral_strategy")
workflow.add_edge("viral_strategy", "script_writer")
workflow.add_edge("script_writer", "storyboard")
workflow.add_edge("storyboard", END)

# Compile
compiled_graph = workflow.compile()
