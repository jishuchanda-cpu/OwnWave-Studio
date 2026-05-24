import os
import wave
import httpx
import asyncio
import subprocess
from pathlib import Path
from typing import Tuple, Optional
from app.core.config import settings

class TTSService:
    def __init__(self):
        self.bin_path = settings.PIPER_BIN_PATH
        self.voices_dir = settings.STORAGE_DIR / "voices"

    async def ensure_voice_model_downloaded(self, voice_name: str):
        """Ensures that the ONNX voice model and JSON config are downloaded locally."""
        model_path = self.voices_dir / f"{voice_name}.onnx"
        config_path = self.voices_dir / f"{voice_name}.onnx.json"
        
        if model_path.exists() and config_path.exists():
            return model_path, config_path

        os.makedirs(self.voices_dir, exist_ok=True)
        
        # Hugging Face URL for Rhasspy Piper voices
        if voice_name == "en_US-ryan-medium":
            base_hf_url = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/medium"
        elif voice_name == "hi_IN-rohan-medium":
            base_hf_url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN/rohan/medium"
        else: # default: en_US-lessac-medium
            base_hf_url = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium"
            
        model_url = f"{base_hf_url}/{voice_name}.onnx"
        config_url = f"{base_hf_url}/{voice_name}.onnx.json"

        async with httpx.AsyncClient(timeout=300.0) as client:
            print(f"Downloading Piper voice model: {voice_name}...")
            
            if not model_path.exists():
                resp = await client.get(model_url, follow_redirects=True)
                resp.raise_for_status()
                with open(model_path, "wb") as f:
                    f.write(resp.content)
                    
            if not config_path.exists():
                resp = await client.get(config_url, follow_redirects=True)
                resp.raise_for_status()
                with open(config_path, "wb") as f:
                    f.write(resp.content)
            
            print(f"Piper voice model {voice_name} download complete.")
            
        return model_path, config_path

    def get_wav_duration(self, wav_path: str) -> float:
        """Reads the WAV file header and returns duration in seconds."""
        try:
            with wave.open(wav_path, "rb") as wav_file:
                frames = wav_file.getnframes()
                rate = wav_file.getframerate()
                duration = frames / float(rate)
                return round(duration, 2)
        except Exception as e:
            print(f"Error parsing WAV duration: {e}")
            return 0.0

    async def generate_narration(self, text: str, output_wav_path: str, project_id: str = "", voice_option: Optional[str] = None) -> Tuple[bool, float]:
        """Generates voice narration WAV from text using Piper TTS CLI subprocess."""
        if not text or not text.strip():
            print(f"[TTS] Empty narration text received. Generating silent audio fallback.")
            return self._fallback_audio("Silence", output_wav_path)

        # Retrieve voice_option from project if not directly supplied
        if not voice_option and project_id:
            try:
                from app.core.database import engine
                from app.models.base import Project
                from sqlmodel import Session
                with Session(engine) as session:
                    project = session.get(Project, project_id)
                    if project:
                        voice_option = project.voice_option
            except Exception as e:
                print(f"[TTS] Error fetching project voice option: {e}")

        # Map voice_option to model name
        voice_name = "en_US-lessac-medium"
        if voice_option == "english_male":
            voice_name = "en_US-ryan-medium"
        elif voice_option == "hindi_male":
            voice_name = "hi_IN-rohan-medium"

        # 1. Ensure model is present
        try:
            model_path, config_path = await self.ensure_voice_model_downloaded(voice_name)
        except Exception as e:
            print(f"Failed to fetch Piper model '{voice_name}' automatically: {e}")
            return self._fallback_audio(text, output_wav_path)

        # Ensure directory for output exists
        os.makedirs(os.path.dirname(output_wav_path), exist_ok=True)

        # 2. Build Piper subprocess command
        # Syntax: piper --model <model> --output_file <wav>
        executables_to_try = [self.bin_path, "C:/Users/user/.gemini/antigravity/bin/piper_extracted/piper/piper.exe"]
        
        for piper_bin in executables_to_try:
            cmd = [
                piper_bin,
                "--model", str(model_path),
                "--output_file", output_wav_path
            ]

            try:
                # Run the process asynchronously
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                from app.workflow.runner import WorkflowRegistry
                if project_id:
                    WorkflowRegistry.register_subprocess(project_id, proc)

                # Pipe text to Piper stdin
                stdout, stderr = await proc.communicate(input=text.encode("utf-8"))
                
                if proc.returncode == 0:
                    duration = self.get_wav_duration(output_wav_path)
                    return True, duration
                else:
                    print(f"Piper execution failed with '{piper_bin}': {stderr.decode('utf-8', errors='ignore')}")
            except FileNotFoundError:
                print(f"Piper binary '{piper_bin}' not found. Trying next candidate.")
            except Exception as e:
                print(f"Unhandled exception in Piper generation with '{piper_bin}': {e}")
                
        print("All Piper execution attempts failed.")
        return self._fallback_audio(text, output_wav_path)


    def _fallback_audio(self, text: str, output_wav_path: str) -> Tuple[bool, float]:
        """Creates a dummy silent WAV file if Piper is unavailable, returning estimated duration."""
        print(f"Creating fallback silent audio at {output_wav_path}")
        
        # Estimate duration: average speaking rate is 3 words per second (min 2.5s)
        word_count = len(text.split())
        duration = max(2.5, round(word_count / 2.5, 2))
        
        # Simple silent WAV generator (44100Hz, 16-bit mono, duration * sample rate samples)
        sample_rate = 22050  # Piper standard sample rate
        num_samples = int(duration * sample_rate)
        
        try:
            with wave.open(output_wav_path, "wb") as wav_file:
                # parameters: nchannels, sampwidth, framerate, nframes, comptype, compname
                wav_file.setparams((1, 2, sample_rate, num_samples, "NONE", "not compressed"))
                # Write empty bytes (silence)
                wav_file.writeframes(b"\x00\x00" * num_samples)
            return True, duration
        except Exception as e:
            print(f"Failed to write silent audio file: {e}")
            return False, 0.0
