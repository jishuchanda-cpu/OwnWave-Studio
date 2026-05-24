import os
import textwrap
import asyncio
from typing import List
from app.core.config import settings

class VideoService:
    @staticmethod
    def wrap_subtitle_text(text: str, width: int = 35) -> str:
        """Wraps text into multiple lines to fit on screen, escaping for FFmpeg drawtext."""
        wrapped = textwrap.fill(text, width=width)
        # Escape characters that break the drawtext filter: single quotes and colons
        escaped = wrapped.replace("'", "'\\''").replace(":", "\\:")
        return escaped

    @classmethod
    async def compile_scene(
        cls, 
        image_path: str, 
        audio_path: str, 
        duration: float, 
        subtitle_text: str, 
        output_mp4_path: str,
        aspect_ratio: str = "9:16",
        scene_index: int = 0,
        project_id: str = "",
        transition_style: str = "fade"
    ) -> bool:
        """Compiles a single image, audio track, and subtitle text into a scene video chunk with dynamic camera motion."""
        # 1. Resolve scale resolution
        resolution = "1080:1920"
        y_position = "h-350"  # Placement from bottom for vertical layout
        fontsize = "48"
        
        if aspect_ratio == "16:9":
            resolution = "1920:1080"
            y_position = "h-150"
            fontsize = "38"
        elif aspect_ratio == "1:1":
            resolution = "1080:1080"
            y_position = "h-200"
            fontsize = "42"

        # High-res pre-scaling width/height before zoompan to preserve quality
        scale_w, scale_h = 2160, 3840
        if aspect_ratio == "16:9":
            scale_w, scale_h = 3840, 2160
        elif aspect_ratio == "1:1":
            scale_w, scale_h = 2160, 2160

        fps = 25
        total_frames = int(fps * duration)
        res_x = resolution.replace(":", "x")

        # Select dynamic cinematic camera movement depending on the scene index
        motion_mode = scene_index % 4
        if motion_mode == 0:
            # Slow push-in zoom
            zoompan_filter = (
                f"zoompan=z='min(zoom+0.001,1.3)':"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"d={total_frames}:s={res_x}:fps={fps}"
            )
        elif motion_mode == 1:
            # Slow pan left-to-right (requires a small constant zoom to have room to pan)
            zoompan_filter = (
                f"zoompan=z=1.25:"
                f"x='(iw-(iw/zoom))*(on/{total_frames})':y='ih/2-(ih/zoom/2)':"
                f"d={total_frames}:s={res_x}:fps={fps}"
            )
        elif motion_mode == 2:
            # Slow zoom-out (starts zoomed and goes out)
            zoompan_filter = (
                f"zoompan=z='max(1.3-0.001*on,1.0)':"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"d={total_frames}:s={res_x}:fps={fps}"
            )
        else:
            # Slow pan right-to-left
            zoompan_filter = (
                f"zoompan=z=1.25:"
                f"x='(iw-(iw/zoom))*(1-on/{total_frames})':y='ih/2-(ih/zoom/2)':"
                f"d={total_frames}:s={res_x}:fps={fps}"
            )

        # 2. Escape text and prepare drawtext filter as a fallback
        wrapped_text = cls.wrap_subtitle_text(subtitle_text)
        
        # Use Windows-standard font Arial if it exists, otherwise omit to let FFmpeg use default
        font_path = "C\\\\:/Windows/Fonts/arial.ttf"
        if not os.path.exists("C:/Windows/Fonts/arial.ttf"):
            font_option = ""
        else:
            font_option = f"fontfile='{font_path}':"

        # Generate ASS subtitle file for word-by-word gold highlight
        ass_path = output_mp4_path.rsplit(".", 1)[0] + ".ass"
        cls.generate_ass_file(subtitle_text, duration, ass_path, aspect_ratio)
        clean_ass_path = ass_path.replace("\\", "/").replace(":", "\\:")

        # 3. Try multiple FFmpeg executable paths and command configurations
        executables_to_try = ["ffmpeg", "C:/Users/user/.gemini/antigravity/bin/ffmpeg.exe"]
        
        for ffmpeg_path in executables_to_try:
            attempts = []
            
            # Attempt 1: ASS word-by-word karaoke style (high priority)
            attempts.append({
                "name": "ASS karaoke subtitles",
                "use_ass": True,
                "font_opt": ""
            })
            
            # Attempt 2: Full drawtext option (with fontfile if it exists)
            attempts.append({
                "name": "drawtext full options",
                "use_ass": False,
                "font_opt": font_option
            })
            
            # Attempt 3: Fallback (without fontfile option)
            if font_option:
                attempts.append({
                    "name": "drawtext no fontfile option",
                    "use_ass": False,
                    "font_opt": ""
                })
                
            for attempt in attempts:
                # Build transition filters if requested
                transition_filter = ""
                if transition_style == "fade" and duration > 1.0:
                    transition_filter = f",fade=in:st=0:d=0.5,fade=out:st={duration-0.5}:d=0.5"

                if attempt["use_ass"]:
                    # Burn in the word-by-word ASS subtitles
                    filter_complex = f"scale={scale_w}:{scale_h},{zoompan_filter},format=yuv420p{transition_filter},subtitles='{clean_ass_path}'"
                else:
                    font_opt = attempt["font_opt"]
                    drawtext_filter = (
                        f"drawtext={font_opt}text='{wrapped_text}':"
                        f"x=(w-text_w)/2:y={y_position}:fontsize={fontsize}:"
                        f"fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=15"
                    )
                    # Build filtergraph: scale up, apply zoompan motion, convert pixel format, burn subtitles
                    filter_complex = f"scale={scale_w}:{scale_h},{zoompan_filter},format=yuv420p{transition_filter},{drawtext_filter}"
                
                cmd = [
                    ffmpeg_path, "-y",
                    "-loop", "1", "-i", image_path,
                    "-i", audio_path,
                    "-vf", filter_complex,
                ]

                # Apply audio fade if transition requested
                if transition_style == "fade" and duration > 1.0:
                    cmd.extend(["-af", f"afade=in:st=0:d=0.5,afade=out:st={duration-0.5}:d=0.5"])

                cmd.extend([
                    "-c:v", "libx264",
                    "-tune", "stillimage",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-pix_fmt", "yuv420p",
                    "-t", str(duration),
                    output_mp4_path
                ])
                
                print(f"Executing FFmpeg compile ({attempt['name']}) using path '{ffmpeg_path}': {' '.join(cmd)}")
                
                try:
                    proc = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    
                    # Register subprocess for cancellation
                    from app.workflow.runner import WorkflowRegistry
                    if project_id:
                        WorkflowRegistry.register_subprocess(project_id, proc)

                    stdout, stderr = await proc.communicate()
                    
                    if proc.returncode == 0:
                        print(f"FFmpeg compile succeeded using '{attempt['name']}'!")
                        return True
                    else:
                        print(f"FFmpeg compile failed using '{attempt['name']}': {stderr.decode('utf-8', errors='ignore')}")
                except FileNotFoundError:
                    print(f"FFmpeg path '{ffmpeg_path}' not found. Trying next candidate.")
                    break  # Break out of attempts for this path and move to next executable path
                except Exception as e:
                    print(f"Error executing FFmpeg command '{ffmpeg_path}' with '{attempt['name']}': {e}")
                    
        return False

    @classmethod
    async def concatenate_scenes(cls, scene_mp4_paths: List[str], output_final_path: str, project_id: str = "") -> bool:
        """Concatenates multiple video chunks into a single MP4 file."""
        if not scene_mp4_paths:
            return False
            
        os.makedirs(os.path.dirname(output_final_path), exist_ok=True)
        
        # 1. Create temporary list file for demuxer
        list_file_path = os.path.dirname(output_final_path) + "/concat_list.txt"
        try:
            with open(list_file_path, "w", encoding="utf-8") as f:
                for path in scene_mp4_paths:
                    # Escape path backslashes for FFmpeg text file
                    clean_path = path.replace("\\", "/")
                    f.write(f"file '{clean_path}'\n")
                    
            # 2. Execute FFmpeg concat copy trying multiple executable paths
            executables_to_try = ["ffmpeg", "C:/Users/user/.gemini/antigravity/bin/ffmpeg.exe"]
            
            for ffmpeg_path in executables_to_try:
                cmd = [
                    ffmpeg_path, "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", list_file_path,
                    "-c", "copy",
                    output_final_path
                ]
                
                print(f"Executing FFmpeg concat using path '{ffmpeg_path}': {' '.join(cmd)}")
                
                try:
                    proc = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    
                    # Register subprocess for cancellation
                    from app.workflow.runner import WorkflowRegistry
                    if project_id:
                        WorkflowRegistry.register_subprocess(project_id, proc)

                    stdout, stderr = await proc.communicate()
                    
                    if proc.returncode == 0:
                        print("FFmpeg concatenation succeeded!")
                        # Clean up temporary list file
                        if os.path.exists(list_file_path):
                            os.remove(list_file_path)
                        return True
                    else:
                        print(f"FFmpeg concat failed using path '{ffmpeg_path}': {stderr.decode('utf-8', errors='ignore')}")
                except FileNotFoundError:
                    print(f"FFmpeg path '{ffmpeg_path}' not found for concat. Trying next.")
                except Exception as e:
                    print(f"Error running FFmpeg concat with path '{ffmpeg_path}': {e}")
                    
            # Clean up temporary list file on failure
            if os.path.exists(list_file_path):
                os.remove(list_file_path)
            return False
        except Exception as e:
            print(f"Error preparing FFmpeg concat: {e}")
            if os.path.exists(list_file_path):
                os.remove(list_file_path)
            return False


    @classmethod
    def generate_ass_file(cls, text: str, duration: float, ass_path: str, aspect_ratio: str = "9:16"):
        """Generates an Advanced Substation Alpha (ASS) file with word-by-word active highlights."""
        words = text.split()
        if not words:
            # Create a simple empty subtitle file if no text
            with open(ass_path, "w", encoding="utf-8") as f:
                f.write("")
            return
            
        num_words = len(words)
        time_per_word = duration / num_words
        
        # Determine actual script resolution and margins depending on layout aspect ratio
        play_res_x = 1080
        play_res_y = 1920
        fontsize = 76
        vertical_margin = 350
        
        if aspect_ratio == "16:9":
            play_res_x = 1920
            play_res_y = 1080
            fontsize = 64
            vertical_margin = 150
        elif aspect_ratio == "1:1":
            play_res_x = 1080
            play_res_y = 1080
            fontsize = 68
            vertical_margin = 200
            
        # Structure the ASS file header
        # Using a heavy bold font like Arial (Bold=-1) and a thick black outline (Outline=5, Shadow=2)
        ass_content = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {play_res_x}
PlayResY: {play_res_y}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial, {fontsize}, &H00FFFFFF, &H0000D7FF, &H00000000, &H80000000, -1, 0, 0, 0, 100, 100, 0, 0, 1, 5, 2, 2, 10, 10, {vertical_margin}, 1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        
        chunk_size = 3
        for i in range(num_words):
            word_start = i * time_per_word
            word_end = (i + 1) * time_per_word
            
            def format_time(t):
                hrs = int(t // 3600)
                mins = int((t % 3600) // 60)
                secs = int(t % 60)
                centis = int(round((t - int(t)) * 100))
                if centis == 100:
                    secs += 1
                    centis = 0
                return f"{hrs}:{mins:02d}:{secs:02d}.{centis:02d}"
                
            start_str = format_time(word_start)
            end_str = format_time(word_end)
            
            # Sub-chunk words to display (max 3 words on screen at once)
            chunk_start_idx = (i // chunk_size) * chunk_size
            chunk_words = words[chunk_start_idx : chunk_start_idx + chunk_size]
            
            formatted_words = []
            for idx, w in enumerate(chunk_words):
                actual_word_idx = chunk_start_idx + idx
                if actual_word_idx == i:
                    # Active word highlighted in gold (Hex BGR: 00D7FF)
                    formatted_words.append(f"{{\\c&H00D7FF&}}{w}{{\\c&HFFFFFF&}}")
                else:
                    formatted_words.append(w)
                    
            line_text = " ".join(formatted_words)
            ass_content += f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{line_text}\n"
            
        os.makedirs(os.path.dirname(ass_path), exist_ok=True)
        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(ass_content)
