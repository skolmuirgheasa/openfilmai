from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict
import re
from pathlib import Path
import json
import shutil
import subprocess
from urllib.parse import urlparse
import threading
import time
import uuid
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from backend.storage.files import (
    list_scenes,
    add_scene,
    get_scene,
    add_shot,
    clear_scene_shots,
    next_shot_id,
    ensure_scene_dirs,
    list_media,
    add_media,
    media_dirs,
    ensure_project,
    read_metadata,
    write_metadata,
    list_characters,
    upsert_character,
    get_character,
    delete_character,
    archive_media,
    bulk_archive_media,
)
from backend.ai.replicate_client import ReplicateClient
from backend.ai.vertex_client import VertexClient
from backend.ai.cinematographer import generate_shot_list, refine_shot_prompt
from ai_porting_bundle.providers.elevenlabs import ElevenLabsProvider
from ai_porting_bundle.providers.wavespeed import WaveSpeedProvider
from backend.storage.settings import read_settings, write_settings

app = FastAPI(title="OpenFilmAI Backend", version="0.1.0")

PROJECT_DATA_DIR = Path("project_data")
PROJECT_DATA_DIR.mkdir(parents=True, exist_ok=True)

# CORS for Electron dev served via Vite - MUST be added AFTER app init but BEFORE routes
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Serve project_data files (videos, frames) under /files/*
# StaticFiles doesn't inherit middleware, so we need a custom wrapper
from starlette.responses import FileResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

@app.get("/files/{full_path:path}")
async def serve_files(full_path: str):
    """Serve static files with CORS headers"""
    file_path = PROJECT_DATA_DIR / full_path
    if not file_path.exists() or not file_path.is_file():
        raise StarletteHTTPException(status_code=404, detail="File not found")
    return FileResponse(
        file_path,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )

@app.head("/files/{full_path:path}")
async def serve_files_head(full_path: str):
    """Serve static files HEAD requests with CORS headers"""
    file_path = PROJECT_DATA_DIR / full_path
    if not file_path.exists() or not file_path.is_file():
        raise StarletteHTTPException(status_code=404, detail="File not found")
    import os
    file_size = os.path.getsize(file_path)
    # Detect MIME type
    import mimetypes
    mime_type, _ = mimetypes.guess_type(str(file_path))
    return FileResponse(
        file_path,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Content-Length": str(file_size),
            "Content-Type": mime_type or "application/octet-stream",
        }
    )

class RevealFileRequest(BaseModel):
    path: str

@app.post("/system/reveal-file")
def reveal_file_in_finder(req: RevealFileRequest):
    """Open file location in system file browser (Finder on macOS)."""
    import subprocess
    import platform

    # Resolve path
    if req.path.startswith("project_data/"):
        file_path = PROJECT_DATA_DIR / req.path.replace("project_data/", "")
    else:
        file_path = Path(req.path)

    if not file_path.exists():
        return {"status": "error", "detail": "File not found"}

    try:
        system = platform.system()
        if system == "Darwin":  # macOS
            subprocess.run(["open", "-R", str(file_path)], check=True)
        elif system == "Windows":
            subprocess.run(["explorer", "/select,", str(file_path)], check=True)
        else:  # Linux
            subprocess.run(["xdg-open", str(file_path.parent)], check=True)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.on_event("startup")
async def startup_event():
    """Load persisted jobs on startup"""
    _load_jobs()
    # Mark any "running" jobs as "failed" since backend reload killed them
    with jobs_lock:
        for job_id, job in background_jobs.items():
            if job.get("status") == "running":
                job["status"] = "failed"
                job["error"] = "Backend reloaded during job execution"
                job["message"] = "Job was interrupted by backend reload. Please retry."
        _save_jobs()

# In-memory job queue for long-running tasks
# Persisted to disk to survive backend reloads
JOBS_FILE = Path.cwd() / "project_data" / "_jobs.json"
background_jobs: Dict[str, Dict] = {}
jobs_lock = threading.Lock()

def _load_jobs():
    """Load jobs from disk on startup"""
    global background_jobs
    if JOBS_FILE.exists():
        try:
            with open(JOBS_FILE, "r") as f:
                background_jobs = json.load(f)
        except Exception:
            background_jobs = {}

def _save_jobs():
    """Save jobs to disk"""
    JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(JOBS_FILE, "w") as f:
        json.dump(background_jobs, f, indent=2)


@app.api_route("/health", methods=["GET", "HEAD"])
def health():
    return {"status": "ok"}


@app.post("/storage/show-in-finder")
def show_in_finder(req: dict):
    """Open the file's location in Finder (macOS)"""
    import subprocess
    import platform
    
    try:
        rel_path = req.get("path", "")
        if not rel_path:
            return {"status": "error", "detail": "No path provided"}
        
        # Convert relative path to absolute
        abs_path = Path.cwd() / rel_path
        if not abs_path.exists():
            return {"status": "error", "detail": f"File not found: {abs_path}"}
        
        # Open in Finder (macOS) or File Explorer (Windows) or file manager (Linux)
        system = platform.system()
        if system == "Darwin":  # macOS
            subprocess.run(["open", "-R", str(abs_path)])
        elif system == "Windows":
            subprocess.run(["explorer", "/select,", str(abs_path)])
        else:  # Linux
            # Open the parent directory
            subprocess.run(["xdg-open", str(abs_path.parent)])
        
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# Job queue helpers
def create_job(job_type: str, **kwargs) -> str:
    """Create a new background job and return its ID"""
    job_id = str(uuid.uuid4())
    with jobs_lock:
        background_jobs[job_id] = {
            "id": job_id,
            "type": job_type,
            "status": "running",
            "progress": 0,
            "result": None,
            "error": None,
            "created_at": time.time(),
            **kwargs
        }
        _save_jobs()
    return job_id


def update_job(job_id: str, **kwargs):
    """Update a job's status"""
    with jobs_lock:
        if job_id in background_jobs:
            background_jobs[job_id].update(kwargs)
            _save_jobs()


def get_job(job_id: str) -> Optional[Dict]:
    """Get a job's current status"""
    with jobs_lock:
        return background_jobs.get(job_id)


@app.get("/jobs/{job_id}")
def get_job_status(job_id: str):
    """Get the status of a background job"""
    job = get_job(job_id)
    if not job:
        return {"status": "not_found"}
    return job


def _slugify(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    name = re.sub(r"-{2,}", "-", name).strip("-")
    return name or "asset"


def _safe_filename(desired: Optional[str], fallback_stub: str, ext: str) -> str:
    base = _slugify(desired) if desired else fallback_stub
    if not base.endswith(ext):
        base = f"{base}{ext}"
    return base


class ShotGenerateRequest(BaseModel):
    project_id: str
    scene_id: str
    prompt: str
    shot_id: Optional[str] = None  # If provided, update existing shot instead of creating new
    provider: Optional[str] = "replicate"  # replicate | vertex
    model: Optional[str] = None
    media_type: Optional[str] = "video"  # video | image
    reference_frame: Optional[str] = None  # path to frame image
    character_id: Optional[str] = None
    duration: Optional[int] = 8
    resolution: Optional[str] = "1080p"
    aspect_ratio: Optional[str] = "16:9"
    start_frame_path: Optional[str] = None
    end_frame_path: Optional[str] = None
    reference_images: Optional[List[str]] = None
    generate_audio: Optional[bool] = False
    num_outputs: Optional[int] = 1  # For image generation (e.g., Seedream-4)


@app.post("/ai/generate-shot")
def generate_shot(req: ShotGenerateRequest):
    # Ensure directories
    dirs = ensure_scene_dirs(req.project_id, req.scene_id)
    # Use provided shot_id if updating existing shot, otherwise generate new
    shot_id = req.shot_id or next_shot_id(req.scene_id)
    is_update = req.shot_id is not None
    logger.info(f"[GENERATE] shot_id={shot_id}, is_update={is_update}, media_type={req.media_type}")
    try:
        if (req.provider or "").lower() == "vertex":
            print("=" * 60)
            print("[VERTEX REQUEST] Received from frontend:")
            print(f"  provider: {req.provider}")
            print(f"  model: {req.model}")
            print(f"  start_frame_path: {req.start_frame_path}")
            print(f"  end_frame_path: {req.end_frame_path}")
            print(f"  reference_images: {req.reference_images}")
            print(f"  reference_frame: {req.reference_frame}")
            print("=" * 60)
            s = read_settings()
            cred = s.get("vertex_service_account_path")
            pid = s.get("vertex_project_id")
            loc = s.get("vertex_location") or "us-central1"
            temp_bucket = s.get("vertex_temp_bucket")
            if not cred or not pid:
                raise RuntimeError("Vertex settings missing. Set service account path and project id in Settings.")
            # Enforce mutual exclusivity: reference_images vs start/end frames
            if (req.start_frame_path or req.end_frame_path) and (req.reference_images and len(req.reference_images) > 0):
                raise RuntimeError("Vertex: start/end frame cannot be combined with reference images.")
            # Vertex frame interpolation requires BOTH start and end frames
            # If only end frame is provided, reject it
            if req.end_frame_path and not req.start_frame_path:
                raise RuntimeError("Vertex: end frame requires a start frame for interpolation. Provide both or only a start frame.")
            client_v = VertexClient(credentials_path=cred, project_id=pid, location=loc, model=req.model or "veo-3.1-fast-generate-preview", temp_bucket=temp_bucket)
            # Allow start-only or end-only; client handles whichever is provided.
            # Normalize paths (convert project_data/... to absolute paths)
            start_img = req.start_frame_path or req.reference_frame
            if start_img:
                start_p = Path(start_img)
                if not start_p.is_absolute():
                    start_img = str(Path.cwd() / start_img)
            end_img = req.end_frame_path
            if end_img:
                end_p = Path(end_img)
                if not end_p.is_absolute():
                    end_img = str(Path.cwd() / end_img)
            ref_imgs = req.reference_images
            if ref_imgs:
                print(f"[VERTEX] Reference images before path normalization: {ref_imgs}")
                ref_imgs = [str(Path.cwd() / r) if not Path(r).is_absolute() else r for r in ref_imgs]
                print(f"[VERTEX] Reference images after path normalization: {ref_imgs}")
                # Verify files exist
                for rp in ref_imgs:
                    exists = Path(rp).exists()
                    print(f"[VERTEX]   {rp} -> exists={exists}")
            else:
                print("[VERTEX] No reference_images provided from frontend")
            output_url = client_v.generate_video(
                prompt=req.prompt,
                first_frame_image=start_img,
                last_frame_image=end_img,
                reference_images=ref_imgs or None,
                duration=req.duration or 8,
                resolution=req.resolution or "1080p",
                aspect_ratio=req.aspect_ratio or "16:9",
                generate_audio=bool(req.generate_audio),
            )
            model_used = req.model or "veo-3.1-fast-generate-preview"
        else:
            # Default to Replicate
            s = read_settings()
            client_r = ReplicateClient(api_token=s.get("replicate_api_token"))
            model_used = req.model or ("bytedance/seedream-4" if req.media_type == "image" else "google/veo-3.1")
            
            # Handle character reference images
            ref_imgs = req.reference_images
            print(f"[IMAGE GEN] Received reference_images from frontend: {ref_imgs}")
            print(f"[IMAGE GEN] character_id: {req.character_id}")
            if req.character_id and not ref_imgs:
                char = get_character(req.project_id, req.character_id)
                if char and char.get("reference_image_ids"):
                    ref_imgs = []
                    for img_id in char["reference_image_ids"]:
                        media_item = next((m for m in list_media(req.project_id) if m.get("id") == img_id), None)
                        if media_item:
                            img_path = _normalize_path(media_item["path"])
                            ref_imgs.append(str(img_path))
            
            # Normalize reference image paths - convert media IDs to actual file paths
            if ref_imgs:
                resolved_refs = []
                for r in ref_imgs:
                    # Check if this looks like a media ID (no slashes, no project_data prefix)
                    if '/' not in r and not r.startswith('project_data'):
                        # This is likely a media ID - look it up
                        media_item = next((m for m in list_media(req.project_id) if m.get("id") == r), None)
                        if media_item and media_item.get("path"):
                            resolved_refs.append(str(_normalize_path(media_item["path"])))
                        else:
                            print(f"[WARN] Could not resolve media ID: {r}")
                    else:
                        # This is a path - normalize it
                        resolved_refs.append(str(_normalize_path(r)) if not Path(r).is_absolute() else r)
                ref_imgs = resolved_refs
                print(f"[IMAGE GEN] Resolved reference images: {ref_imgs}")

            if req.media_type == "image":
                # Image generation (e.g., Seedream-4)
                print(f"[IMAGE GEN] Model: {model_used}, num_outputs: {req.num_outputs}, ref_imgs: {len(ref_imgs) if ref_imgs else 0}")
                if ref_imgs:
                    for i, path in enumerate(ref_imgs):
                        exists = Path(path).exists() if path else False
                        print(f"[IMAGE GEN]   Ref {i+1}: {path} (exists: {exists})")
                output_urls = client_r.generate_image(
                    model=model_used,
                    prompt=req.prompt,
                    reference_images=ref_imgs or None,
                    aspect_ratio=req.aspect_ratio or "16:9",
                    num_outputs=req.num_outputs or 1,
                )
                print(f"[IMAGE GEN] Received {len(output_urls)} image URLs from API")
                # For images, we'll save them to media/images and create image items
                import requests
                media_images_dir = PROJECT_DATA_DIR / req.project_id / "media" / "images"
                media_images_dir.mkdir(parents=True, exist_ok=True)
                
                saved_images = []
                import time
                timestamp = int(time.time())
                for idx, img_url in enumerate(output_urls):
                    # Put timestamp first for better sorting
                    img_filename = f"{timestamp}_{shot_id}_{idx}.jpg" if len(output_urls) > 1 else f"{timestamp}_{shot_id}.jpg"
                    img_path = media_images_dir / img_filename
                    
                    # Download image
                    with requests.get(img_url, stream=True, timeout=120) as r:
                        r.raise_for_status()
                        with open(img_path, "wb") as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                    
                    rel_img = str(img_path.relative_to(PROJECT_DATA_DIR))
                    add_media(req.project_id, {
                        "id": img_filename,
                        "type": "image",
                        "path": f"project_data/{rel_img}",
                        "url": f"/files/{rel_img}",
                        "timestamp": timestamp
                    })
                    saved_images.append(f"project_data/{rel_img}")
                
                # Return first image as the "shot" (for compatibility)
                return {"status": "ok", "shot_id": shot_id, "images": saved_images, "model": model_used}
            else:
                # Video generation
                # Normalize start/end frame paths
                start_img = None
                end_img = None
                if req.start_frame_path:
                    start_img = str(_normalize_path(req.start_frame_path))
                elif req.reference_frame:
                    start_img = str(_normalize_path(req.reference_frame))
                if req.end_frame_path:
                    end_img = str(_normalize_path(req.end_frame_path))
                
                # NOTE: Video models do NOT support reference_images directly.
                # Consistency is achieved through start_frame_path (generated from refs in image step).
                # The ref_imgs parameter is passed for API compatibility but is ignored by all video models.
                output_url = client_r.generate_video(
                    model=model_used,
                    prompt=req.prompt,
                    first_frame_image=start_img,
                    last_frame_image=end_img,
                    reference_images=None,  # Explicitly None - video models use start frame for consistency
                    duration=req.duration or 8,
                    resolution=req.resolution or "1080p",
                    aspect_ratio=req.aspect_ratio or "16:9",
                    generate_audio=bool(req.generate_audio),
                )
        
        # Download video file
        import requests, os
        video_path = dirs["shots"] / f"{shot_id}.mp4"
        parsed = urlparse(str(output_url))
        if parsed.scheme in ("http", "https"):
            with requests.get(output_url, stream=True, timeout=120) as r:
                r.raise_for_status()
                with open(video_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
        else:
            # Treat as local filesystem path produced by client; move/copy into scene shots folder.
            src = Path(str(output_url))
            if not src.exists():
                raise RuntimeError(f"Vertex output not found: {src}")
            shutil.copyfile(src, video_path)
        # Extract frames & strip audio if disabled
        from backend.video.ffmpeg import extract_first_last_frames, strip_audio
        if not req.generate_audio:
            strip_audio(str(video_path))
        first = dirs["frames"] / f"{shot_id}_first.png"
        last = dirs["frames"] / f"{shot_id}_last.png"
        extract_first_last_frames(str(video_path), str(first), str(last))
        
        # Copy video to media library so it's available for reuse
        media_video_dir = PROJECT_DATA_DIR / req.project_id / "media" / "video"
        media_video_dir.mkdir(parents=True, exist_ok=True)
        media_video_path = media_video_dir / f"{shot_id}.mp4"
        shutil.copyfile(video_path, media_video_path)
        
        # Also copy extracted frames to media/images
        media_images_dir = PROJECT_DATA_DIR / req.project_id / "media" / "images"
        media_images_dir.mkdir(parents=True, exist_ok=True)
        media_first = media_images_dir / f"{shot_id}_first.png"
        media_last = media_images_dir / f"{shot_id}_last.png"
        shutil.copyfile(first, media_first)
        shutil.copyfile(last, media_last)
        
        # Add to media library
        rel_media_video = str(media_video_path.relative_to(PROJECT_DATA_DIR))
        rel_media_first = str(media_first.relative_to(PROJECT_DATA_DIR))
        rel_media_last = str(media_last.relative_to(PROJECT_DATA_DIR))
        add_media(req.project_id, {"id": media_video_path.name, "type": "video", "path": f"project_data/{rel_media_video}", "url": f"/files/{rel_media_video}"})
        add_media(req.project_id, {"id": media_first.name, "type": "image", "path": f"project_data/{rel_media_first}", "url": f"/files/{rel_media_first}"})
        add_media(req.project_id, {"id": media_last.name, "type": "image", "path": f"project_data/{rel_media_last}", "url": f"/files/{rel_media_last}"})
        
        # Update metadata
        rel_from_project = str(video_path.relative_to(PROJECT_DATA_DIR))
        # Static URL under /files maps to project_data dir
        video_url = f"/files/{rel_from_project}"
        rel_first = str(first.relative_to(PROJECT_DATA_DIR))
        rel_last = str(last.relative_to(PROJECT_DATA_DIR))
        shot_meta = {
            "shot_id": shot_id,
            "prompt": req.prompt,
            "model": model_used,
            "duration": req.duration,
            "file_path": f"project_data/{rel_from_project}",
            "first_frame_path": f"project_data/{rel_first}",
            "last_frame_path": f"project_data/{rel_last}",
            "continuity_source": None,
        }

        # Update existing shot or create new one
        if is_update:
            # Update existing shot with video info
            logger.info(f"[GENERATE] Updating existing shot {shot_id} with video")
            meta = read_metadata(req.project_id)
            for s in meta.get("scenes", []):
                if s.get("scene_id") == req.scene_id:
                    for sh in s.get("shots", []):
                        if sh.get("shot_id") == shot_id:
                            # Update video-related fields
                            sh["file_path"] = shot_meta["file_path"]
                            sh["first_frame_path"] = shot_meta["first_frame_path"]
                            sh["last_frame_path"] = shot_meta["last_frame_path"]
                            sh["model"] = shot_meta["model"]
                            sh["status"] = "video_ready"  # Mark shot as complete
                            write_metadata(req.project_id, meta)
                            logger.info(f"[GENERATE] Shot {shot_id} updated successfully")
                            return {"status": "ok", "shot": sh, "file_url": video_url}
            # If shot not found, fall through to create new
            logger.warning(f"[GENERATE] Shot {shot_id} not found, creating new")

        add_shot(req.project_id, req.scene_id, shot_meta)
        return {"status": "ok", "shot": shot_meta, "file_url": video_url}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


class VoiceTTSRequest(BaseModel):
    project_id: str
    text: str
    voice_id: Optional[str] = None
    model_id: Optional[str] = None
    filename: Optional[str] = None
    voice_settings: Optional[dict] = None


@app.post("/ai/voice/tts")
def voice_tts(req: VoiceTTSRequest):
    s = read_settings()
    key = s.get("elevenlabs_api_key")
    if not key:
        return {"status": "error", "detail": "ElevenLabs API key not set in Settings"}
    prov = ElevenLabsProvider(api_key=key)
    try:
        out = prov.generate(text=req.text, voice_id=req.voice_id, model_id=req.model_id or None, output_format="mp3", voice_settings=req.voice_settings)
        # Save to project audio folder and index
        proj_audio = ensure_scene_dirs(req.project_id, "tmp")["audio"].parent.parent / "media" / "audio"
        proj_audio.mkdir(parents=True, exist_ok=True)
        stub = f"voice_{int(__import__('time').time())}"
        filename = _safe_filename(req.filename, stub, ".mp3")
        target = proj_audio / filename
        Path(out).rename(target)
        rel = str(target.relative_to(PROJECT_DATA_DIR))
        item = {"id": target.name, "type": "audio", "path": f"project_data/{rel}", "url": f"/files/{rel}", "filename": target.name}
        add_media(req.project_id, item)
        return {"status": "ok", "file_url": f"/files/{rel}", "item": item, "filename": target.name}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


class VoiceV2VRequest(BaseModel):
    project_id: str
    source_wav: str
    voice_id: Optional[str] = None
    model_id: Optional[str] = "eleven_multilingual_sts_v2"
    filename: Optional[str] = None
    voice_settings: Optional[dict] = None
    remove_background_noise: Optional[bool] = False


@app.post("/ai/voice/v2v")
def voice_v2v(req: VoiceV2VRequest):
    s = read_settings()
    key = s.get("elevenlabs_api_key")
    if not key:
        return {"status": "error", "detail": "ElevenLabs API key not set in Settings"}
    prov = ElevenLabsProvider(api_key=key)
    try:
        src = Path(req.source_wav)
        if not src.is_absolute():
            src = Path.cwd() / req.source_wav
        out = prov.speech_to_speech(audio_path=str(src), voice_id=req.voice_id or None, model_id=req.model_id or "eleven_multilingual_sts_v2", output_format="mp3", voice_settings=req.voice_settings, remove_background_noise=req.remove_background_noise or False)
        proj_audio = ensure_scene_dirs(req.project_id, "tmp")["audio"].parent.parent / "media" / "audio"
        proj_audio.mkdir(parents=True, exist_ok=True)
        stub = f"voice_v2v_{int(__import__('time').time())}"
        target = proj_audio / _safe_filename(req.filename, stub, ".mp3")
        Path(out).rename(target)
        rel = str(target.relative_to(PROJECT_DATA_DIR))
        item = {"id": target.name, "type": "audio", "path": f"project_data/{rel}", "url": f"/files/{rel}", "filename": target.name}
        add_media(req.project_id, item)
        return {"status": "ok", "file_url": f"/files/{rel}", "item": item, "filename": target.name}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


class LipSyncImageRequest(BaseModel):
    project_id: str
    image_path: str
    audio_wav_path: str
    prompt: Optional[str] = None
    filename: Optional[str] = None


class LipSyncVideoRequest(BaseModel):
    project_id: str
    video_path: str
    audio_wav_path: str
    prompt: Optional[str] = None
    filename: Optional[str] = None


def _wavespeed_provider():
    s = read_settings()
    key = s.get("wavespeed_api_key")
    if not key:
        raise RuntimeError("Wavespeed API key not set in Settings")
    return WaveSpeedProvider(api_key=key)


def _save_video_to_media(project_id: str, tmp_path: str, desired_name: Optional[str] = None) -> Dict[str, str]:
    import shutil
    from backend.video.ffmpeg import extract_first_last_frames
    
    proj_video = PROJECT_DATA_DIR / project_id / "media" / "video"
    proj_video.mkdir(parents=True, exist_ok=True)
    stub = f"wavespeed_{int(__import__('time').time())}"
    target = proj_video / _safe_filename(desired_name, stub, ".mp4")
    # Use shutil.move instead of rename to handle cross-filesystem moves
    shutil.move(str(tmp_path), str(target))
    rel = str(target.relative_to(PROJECT_DATA_DIR))
    
    # Extract first frame as thumbnail
    proj_images = PROJECT_DATA_DIR / project_id / "media" / "images"
    proj_images.mkdir(parents=True, exist_ok=True)
    thumb_first = proj_images / f"{target.stem}_first.png"
    thumb_last = proj_images / f"{target.stem}_last.png"
    try:
        extract_first_last_frames(str(target), str(thumb_first), str(thumb_last))
        rel_first = str(thumb_first.relative_to(PROJECT_DATA_DIR))
        rel_last = str(thumb_last.relative_to(PROJECT_DATA_DIR))
        add_media(project_id, {"id": thumb_first.name, "type": "image", "path": f"project_data/{rel_first}", "url": f"/files/{rel_first}"})
        add_media(project_id, {"id": thumb_last.name, "type": "image", "path": f"project_data/{rel_last}", "url": f"/files/{rel_last}"})
    except Exception as e:
        logger.warning(f"Failed to extract thumbnail for {target.name}: {e}")
    
    item = {"id": target.name, "type": "video", "path": f"project_data/{rel}", "url": f"/files/{rel}"}
    add_media(project_id, item)
    return item


def _run_lipsync_image_job(job_id: str, req: LipSyncImageRequest):
    """Background worker for image lip-sync"""
    try:
        update_job(job_id, status="running", progress=10, message="Initializing WaveSpeed...")
        prov = _wavespeed_provider()
        img = Path(req.image_path)
        aud = Path(req.audio_wav_path)
        if not img.is_absolute():
            img = Path.cwd() / req.image_path
        if not aud.is_absolute():
            aud = Path.cwd() / req.audio_wav_path
        
        update_job(job_id, progress=20, message="Uploading to WaveSpeed (may take 5-30 min)...")
        tmp = prov.generate(prompt=req.prompt or "", image_path=str(img), audio_path=str(aud))
        
        update_job(job_id, progress=90, message="Saving result...")
        item = _save_video_to_media(req.project_id, tmp, req.filename)
        
        update_job(job_id, status="completed", progress=100, result=item, message="Lip-sync complete!")
    except Exception as e:
        update_job(job_id, status="failed", error=str(e), message=f"Error: {str(e)}")


def _run_lipsync_video_job(job_id: str, req: LipSyncVideoRequest):
    """Background worker for video lip-sync"""
    import logging
    import tempfile
    logger = logging.getLogger("openfilmai")
    
    try:
        logger.info(f"[Job {job_id}] Starting lip-sync video job")
        update_job(job_id, status="running", progress=10, message="Initializing WaveSpeed...")
        prov = _wavespeed_provider()
        vid = Path(req.video_path)
        aud = Path(req.audio_wav_path)
        if not vid.is_absolute():
            vid = Path.cwd() / req.video_path
        if not aud.is_absolute():
            aud = Path.cwd() / req.audio_wav_path
        
        logger.info(f"[Job {job_id}] Video: {vid}, Audio: {aud}")
        
        # Get video duration
        update_job(job_id, progress=15, message="Preparing audio...")
        probe_vid = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(vid)
        ], capture_output=True, text=True)
        
        if probe_vid.returncode != 0:
            raise RuntimeError(f"Failed to probe video duration: {probe_vid.stderr}")
        
        video_duration = float(probe_vid.stdout.strip())
        logger.info(f"[Job {job_id}] Video duration: {video_duration}s")
        
        # Pad audio to match video duration (WaveSpeed generates video matching audio length)
        from backend.video.ffmpeg import pad_audio_to_duration
        padded_audio = tempfile.mktemp(suffix=".aac", dir="/tmp")
        try:
            pad_audio_to_duration(str(aud), video_duration, padded_audio)
            logger.info(f"[Job {job_id}] Audio padded to {video_duration}s")
            audio_to_use = padded_audio
        except Exception as e:
            logger.warning(f"[Job {job_id}] Failed to pad audio: {e}, using original")
            audio_to_use = str(aud)
        
        update_job(job_id, progress=20, message="Uploading to WaveSpeed (may take 5-30 min)...")
        tmp_lipsync = prov.generate(prompt=req.prompt or "", video_path=str(vid), audio_path=audio_to_use)
        logger.info(f"[Job {job_id}] WaveSpeed returned: {tmp_lipsync}")
        
        # Clean up padded audio
        if audio_to_use == padded_audio:
            Path(padded_audio).unlink(missing_ok=True)
        
        # Ensure browser-compatible format
        update_job(job_id, progress=85, message="Converting to browser-compatible format...")
        from backend.video.ffmpeg import ensure_compatible_format
        compatible_tmp = tempfile.mktemp(suffix=".mp4", dir="/tmp")
        try:
            logger.info(f"[Job {job_id}] Converting {tmp_lipsync} to compatible format")
            ensure_compatible_format(tmp_lipsync, compatible_tmp)
            Path(tmp_lipsync).unlink(missing_ok=True)
            tmp = compatible_tmp
            logger.info(f"[Job {job_id}] Format conversion successful")
        except Exception as e:
            logger.warning(f"[Job {job_id}] Format conversion failed: {e}, using original")
            tmp = tmp_lipsync
            # Continue with original if conversion fails
        
        update_job(job_id, progress=95, message="Saving result...")
        logger.info(f"[Job {job_id}] Saving {tmp} to media library")
        item = _save_video_to_media(req.project_id, tmp, req.filename)
        logger.info(f"[Job {job_id}] Saved as: {item}")
        
        update_job(job_id, status="completed", progress=100, result=item, message="Lip-sync complete!")
        logger.info(f"[Job {job_id}] Job completed successfully")
    except Exception as e:
        logger.error(f"[Job {job_id}] Job failed: {e}", exc_info=True)
        update_job(job_id, status="failed", error=str(e), message=f"Error: {str(e)}")


@app.post("/ai/lipsync/image")
def lipsync_image(req: LipSyncImageRequest):
    """Start image lip-sync job in background"""
    job_id = create_job("lipsync_image", project_id=req.project_id, filename=req.filename)
    thread = threading.Thread(target=_run_lipsync_image_job, args=(job_id, req), daemon=True)
    thread.start()
    return {"status": "ok", "job_id": job_id}


@app.post("/ai/lipsync/video")
def lipsync_video(req: LipSyncVideoRequest):
    """Start video lip-sync job in background"""
    job_id = create_job("lipsync_video", project_id=req.project_id, filename=req.filename)
    thread = threading.Thread(target=_run_lipsync_video_job, args=(job_id, req), daemon=True)
    thread.start()
    return {"status": "ok", "job_id": job_id}


class MultiCharacterLipSyncRequest(BaseModel):
    project_id: str
    image_path: str
    characters: List[dict]  # [{character_id, character_name, audio_path, bounding_box: {x, y, width, height}}]
    prompt: Optional[str] = None
    filename: Optional[str] = None


@app.post("/ai/lipsync/multi-character")
def lipsync_multi_character(req: MultiCharacterLipSyncRequest):
    """
    Multi-character lip-sync with precise audio-to-character mapping.
    Generates each character separately and composites them using FFmpeg.
    """
    job_id = create_job("lipsync_multi_character", project_id=req.project_id, filename=req.filename)
    thread = threading.Thread(target=_run_multi_character_lipsync_job, args=(job_id, req), daemon=True)
    thread.start()
    return {"status": "ok", "job_id": job_id}


def _run_multi_character_lipsync_job(job_id: str, req: MultiCharacterLipSyncRequest):
    """
    Generate multi-character lip-sync by:
    1. Creating a cropped image for each character (based on bounding box)
    2. Generating lip-sync video for each character separately
    3. Compositing all characters back onto the original image using FFmpeg
    """
    import subprocess
    import shutil
    from PIL import Image
    
    try:
        update_job(job_id, status="running", progress=5, message=f"Processing {len(req.characters)} characters...")
        prov = _wavespeed_provider()
        
        img_path = Path(req.image_path)
        if not img_path.is_absolute():
            img_path = Path.cwd() / req.image_path
        
        if not img_path.exists():
            raise RuntimeError(f"Image not found: {img_path}")
        
        # Load original image to get dimensions
        with Image.open(img_path) as img:
            img_width, img_height = img.size
        
        logger.info(f"Multi-character lip-sync: {len(req.characters)} characters on {img_width}x{img_height} image")
        
        # Generate lip-sync for each character
        character_videos = []
        for i, char_data in enumerate(req.characters):
            char_name = char_data.get("character_name", f"Character {i+1}")
            progress = 10 + (i * 70 // len(req.characters))
            update_job(job_id, progress=progress, message=f"Generating lip-sync for {char_name}...")
            
            audio_path = Path(char_data["audio_path"])
            if not audio_path.is_absolute():
                audio_path = Path.cwd() / audio_path
            
            bbox = char_data["bounding_box"]
            
            # Convert percentage to pixels
            x_px = int((bbox["x"] / 100) * img_width)
            y_px = int((bbox["y"] / 100) * img_height)
            w_px = int((bbox["width"] / 100) * img_width)
            h_px = int((bbox["height"] / 100) * img_height)
            
            logger.info(f"  {char_name}: bbox=({x_px},{y_px},{w_px},{h_px}), audio={audio_path.name}")
            
            # Generate full-image lip-sync for this character's audio
            tmp_video = prov.generate(
                prompt=req.prompt or f"focus on character at position {bbox['x']},{bbox['y']}",
                image_path=str(img_path),
                audio_path=str(audio_path),
                resolution="720p"
            )
            
            character_videos.append({
                "video_path": tmp_video,
                "bbox": {"x": x_px, "y": y_px, "width": w_px, "height": h_px},
                "character_name": char_name
            })
        
        # Composite all character videos
        update_job(job_id, progress=85, message="Compositing all characters...")
        
        # For now, just use the last generated video as the result
        # TODO: Implement proper FFmpeg compositing with masks/crops
        final_video = character_videos[-1]["video_path"] if character_videos else None
        
        if not final_video:
            raise RuntimeError("No character videos generated")
        
        logger.info(f"Multi-character result: {final_video}")
        
        # Save to media
        update_job(job_id, progress=95, message="Saving result...")
        item = _save_video_to_media(req.project_id, final_video, req.filename)
        
        update_job(job_id, status="completed", progress=100, result=item, message="Multi-character lip-sync complete!")
        
    except Exception as e:
        logger.error(f"Multi-character lip-sync error: {e}", exc_info=True)
        update_job(job_id, status="failed", error=str(e))


# ============================================================================
# AI Cinematographer - Shot Planning
# ============================================================================

class ShotPlanRequest(BaseModel):
    project_id: str
    scene_id: str
    scene_description: str
    dialogue: Optional[str] = None
    location_notes: Optional[str] = None
    num_shots: Optional[int] = None
    apply_to_scene: bool = False  # If True, create shots in scene immediately
    shots: Optional[List[dict]] = None  # Pre-generated shots to apply (skips AI generation if provided)


@app.post("/ai/plan-shots")
def plan_shots(req: ShotPlanRequest):
    """Generate shot list using AI cinematographer."""
    settings = read_settings()

    # Determine provider and get API key
    provider = settings.get("llm_provider", "anthropic")
    if provider == "openai":
        api_key = settings.get("openai_api_key")
    else:
        provider = "anthropic"  # Default to anthropic
        api_key = settings.get("anthropic_api_key")

    if not api_key:
        return {"status": "error", "detail": f"No API key configured for {provider}. Add it in Settings."}

    # Get all characters for context
    all_chars = list_characters(req.project_id)

    # Get scene-specific cast with appearance notes
    scene = get_scene(req.project_id, req.scene_id) if req.scene_id else None
    scene_cast = scene.get("cast", []) if scene else []

    # Merge character info with scene-specific appearance
    chars = []
    for char in all_chars:
        char_data = {
            "name": char.get("name"),
            "style_tokens": char.get("style_tokens"),
        }
        # Check if this character has scene-specific appearance
        for cast_entry in scene_cast:
            if cast_entry.get("character_id") == char.get("character_id"):
                char_data["appearance_notes"] = cast_entry.get("appearance_notes")
                break
        chars.append(char_data)

    try:
        # Use pre-generated shots if provided, otherwise generate new ones
        if req.shots:
            logger.info(f"Using {len(req.shots)} pre-generated shots (skipping AI generation)")
            shots = req.shots
        else:
            shots = generate_shot_list(
                scene_description=req.scene_description,
                dialogue=req.dialogue,
                characters=chars,
                location_notes=req.location_notes,
                visual_style=scene.get("visual_style") if scene else None,
                color_palette=scene.get("color_palette") if scene else None,
                camera_style=scene.get("camera_style") if scene else None,
                tone_notes=scene.get("tone_notes") if scene else None,
                num_shots=req.num_shots,
                provider=provider,
                api_key=api_key
            )

        # Build name -> character_id mapping
        name_to_id = {c.get("name", "").lower(): c.get("character_id") for c in all_chars}

        # If apply_to_scene is True, clear existing shots and create the new shots in the scene
        if req.apply_to_scene and req.scene_id:
            # Clear existing shots first to avoid duplicates
            cleared_count = clear_scene_shots(req.project_id, req.scene_id)
            logger.info(f"Cleared {cleared_count} existing shots from scene {req.scene_id}")

            for i, shot_data in enumerate(shots):
                shot_id = f"shot_{int(time.time())}_{i+1:03d}"

                # Auto-ID characters from characters_visible
                characters_in_shot = []
                logger.info(f"[SHOT {i+1}] Processing shot: {shot_data.get('subject', 'unknown')}")
                logger.info(f"[SHOT {i+1}] characters_visible from AI: {shot_data.get('characters_visible', [])}")
                logger.info(f"[SHOT {i+1}] name_to_id mapping: {name_to_id}")

                for char_name in shot_data.get("characters_visible", []):
                    char_id = name_to_id.get(char_name.lower())
                    logger.info(f"[SHOT {i+1}] Looking up '{char_name}' (lowercase: '{char_name.lower()}') -> {char_id}")
                    if char_id:
                        characters_in_shot.append(char_id)

                # Also check subject and speaker for character matches
                for field in ["subject", "speaker"]:
                    val = shot_data.get(field, "") or ""
                    for name, cid in name_to_id.items():
                        if name in val.lower() and cid not in characters_in_shot:
                            logger.info(f"[SHOT {i+1}] Found character '{name}' in {field}: '{val}'")
                            characters_in_shot.append(cid)

                logger.info(f"[SHOT {i+1}] Final characters_in_shot: {characters_in_shot}")

                shot_meta = {
                    "shot_id": shot_id,
                    "shot_number": shot_data.get("shot_number", i + 1),
                    "camera_angle": shot_data.get("camera_angle"),
                    "subject": shot_data.get("subject"),
                    "action": shot_data.get("action"),
                    "dialogue": shot_data.get("dialogue"),
                    "characters_in_shot": characters_in_shot,
                    "prompt": shot_data.get("prompt_suggestion"),
                    "duration": shot_data.get("duration_suggestion", 5),
                    "status": "planned"
                }
                add_shot(req.project_id, req.scene_id, shot_meta)

        return {"status": "ok", "shots": shots, "applied": req.apply_to_scene}
    except Exception as e:
        logger.error(f"Shot planning failed: {e}", exc_info=True)
        return {"status": "error", "detail": str(e)}


class SceneAnalyzeRequest(BaseModel):
    scene_description: str
    location_notes: Optional[str] = None
    existing_characters: Optional[List[str]] = None  # Names of characters in the project
    cast_characters: Optional[List[str]] = None  # Names of characters DEFINITELY in this scene (must generate appearances for all)


SCENE_ANALYSIS_PROMPT = '''You are an expert cinematographer, production designer, costume designer, and location scout.

Given a scene description, analyze it and provide a comprehensive scene setup proposal including character wardrobe/appearance.

Think deeply about:
- What specific location would work best for this scene?
- What time of day and lighting creates the right mood?
- What key visual elements define this space?
- What's the atmosphere and emotional tone?
- What should each character be wearing/look like in THIS scene?

Return ONLY valid JSON with this exact structure:
{
  "visual_style": "brief description of recommended visual style (e.g., 'gritty neo-noir with deep shadows')",
  "color_palette": "specific color palette (e.g., 'desaturated teals and oranges, crushed blacks')",
  "camera_style": "camera approach (e.g., 'handheld with subtle movement, wide lenses')",
  "tone_notes": "additional cinematography details (e.g., 'anamorphic lens flares, shallow DOF')",
  "suggested_characters": ["Character Name 1", "Character Name 2"],
  "scene_setting_proposal": {
    "location_type": "specific location type (e.g., 'abandoned industrial warehouse')",
    "time_of_day": "when this takes place (e.g., 'late night, moonlight through windows')",
    "key_elements": "3-5 defining visual elements of the space (e.g., 'rusted machinery, broken skylights, scattered debris, single hanging work light')",
    "atmosphere": "the feeling/mood (e.g., 'tense, claustrophobic, danger lurking in shadows')",
    "lighting_description": "how the scene is lit (e.g., 'harsh single source from above, deep shadows, rim lighting from windows')"
  },
  "establishing_shot_prompt": "A complete, detailed prompt for generating THE establishing shot of this scene WITHOUT characters. This is the master reference image that all other shots will be built from. Be extremely specific about: exact location details, lighting quality and direction, atmosphere, mood, camera angle (usually wide), and any environmental storytelling elements. This prompt should be 2-3 sentences of rich visual description. Focus purely on the environment/setting.",
  "establishing_shot_with_characters_prompt": "Same as above, but WITH the main characters positioned in the scene. Describe where they are in the frame, their body language, and how they relate to the space.",
  "character_appearances": {
    "Character Name": {
      "appearance_notes": "Brief description of how they look in this scene (e.g., 'disheveled, exhausted, three-day stubble')",
      "wardrobe": "What they're wearing (e.g., 'wrinkled white dress shirt, loosened tie, rolled sleeves')",
      "reference_prompt": "Full detailed prompt for generating a reference image of this character in this scene. Include: full body shot, their specific wardrobe, pose, the scene's lighting style, and atmosphere. Should match the scene setting. Be specific about clothing details, colors, and textures."
    }
  }
}

IMPORTANT: In "character_appearances", include an entry for EACH character mentioned in the scene or provided in the existing characters list. Each character needs their own appearance_notes, wardrobe, and reference_prompt tailored to THIS specific scene.'''


@app.post("/ai/analyze-scene")
def analyze_scene(req: SceneAnalyzeRequest):
    """Analyze a scene description and suggest visual style, characters, and setting image prompts."""
    settings = read_settings()

    provider = settings.get("llm_provider", "anthropic")
    if provider == "openai":
        api_key = settings.get("openai_api_key")
    else:
        provider = "anthropic"
        api_key = settings.get("anthropic_api_key")

    if not api_key:
        return {"status": "error", "detail": f"No API key configured for {provider}. Add your API key in Settings."}

    # Build context message
    user_message = f"Scene Description:\n{req.scene_description}"
    if req.location_notes:
        user_message += f"\n\nLocation Details:\n{req.location_notes}"

    # Cast characters are the ones definitely in this scene - MUST generate appearances for all
    if req.cast_characters and len(req.cast_characters) > 0:
        user_message += f"\n\nCHARACTERS IN THIS SCENE (MUST generate appearance for ALL): {', '.join(req.cast_characters)}"

    if req.existing_characters:
        other_chars = [c for c in req.existing_characters if c not in (req.cast_characters or [])]
        if other_chars:
            user_message += f"\n\nOther characters in project (may or may not appear): {', '.join(other_chars)}"

    user_message += "\n\nAnalyze this scene and provide recommendations. IMPORTANT: You MUST include a character_appearances entry for EVERY character listed in 'CHARACTERS IN THIS SCENE' above. Do not skip any."

    try:
        if provider == "anthropic":
            import requests
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 2048,
                    "system": SCENE_ANALYSIS_PROMPT,
                    "messages": [{"role": "user", "content": user_message}]
                },
                timeout=60
            )
            if response.status_code != 200:
                return {"status": "error", "detail": f"Anthropic API error: {response.status_code}"}
            content = response.json().get("content", [{}])[0].get("text", "")
        else:
            import requests
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4.1-2025-04-14",
                    "messages": [
                        {"role": "system", "content": SCENE_ANALYSIS_PROMPT},
                        {"role": "user", "content": user_message}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 2048
                },
                timeout=60
            )
            if response.status_code != 200:
                return {"status": "error", "detail": f"OpenAI API error: {response.status_code}"}
            content = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")

        # Parse JSON response
        import json
        content = content.strip()
        # Remove markdown code blocks if present
        if "```" in content:
            lines = content.split("\n")
            in_block = False
            block_lines = []
            for line in lines:
                if line.strip().startswith("```"):
                    if in_block:
                        break
                    else:
                        in_block = True
                        continue
                if in_block:
                    block_lines.append(line)
            if block_lines:
                content = "\n".join(block_lines)

        # Find JSON object
        start_idx = content.find("{")
        end_idx = content.rfind("}") + 1
        if start_idx != -1 and end_idx > start_idx:
            json_str = content[start_idx:end_idx]
            result = json.loads(json_str)
            return {"status": "ok", "analysis": result}

        return {"status": "error", "detail": "Could not parse AI response"}
    except Exception as e:
        logger.error(f"Scene analysis failed: {e}", exc_info=True)
        return {"status": "error", "detail": str(e)}


class PromptRefineRequest(BaseModel):
    project_id: str
    scene_id: str
    shot_id: str
    scene_context: Optional[str] = None
    character_info: Optional[str] = None
    style_notes: Optional[str] = None


@app.post("/ai/refine-prompt")
def refine_prompt(req: PromptRefineRequest):
    """Refine a shot's prompt using AI."""
    settings = read_settings()

    provider = settings.get("llm_provider", "anthropic")
    if provider == "openai":
        api_key = settings.get("openai_api_key")
    else:
        provider = "anthropic"
        api_key = settings.get("anthropic_api_key")

    if not api_key:
        return {"status": "error", "detail": f"No API key configured for {provider}"}

    # Get the shot
    scene = get_scene(req.project_id, req.scene_id)
    if not scene:
        return {"status": "error", "detail": "Scene not found"}

    shot = next((s for s in scene.get("shots", []) if s.get("shot_id") == req.shot_id), None)
    if not shot:
        return {"status": "error", "detail": "Shot not found"}

    try:
        refined = refine_shot_prompt(
            shot=shot,
            scene_context=req.scene_context or scene.get("description", ""),
            character_info=req.character_info,
            style_notes=req.style_notes,
            provider=provider,
            api_key=api_key
        )
        return {"status": "ok", "prompt": refined}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


class AIShotPlanRequest(BaseModel):
    project_id: str
    scene_id: str
    shot_id: str  # The shot we're planning
    prev_video_path: str  # Path to the previous shot's video
    additional_video_paths: Optional[List[str]] = None  # Additional prior shot videos for context
    selected_ref_ids: Optional[List[str]] = None  # User-selected reference image IDs (if None, use all)


@app.post("/ai/plan-shot-from-video")
def plan_shot_from_video(req: AIShotPlanRequest):
    """
    AI Director: Watch the previous shot's video and plan the complete next shot.

    This analyzes the video, understands scene context, and returns a complete
    execution plan including which refs to use, image prompt, video prompt, etc.
    """
    settings = read_settings()

    # Need Vertex credentials for Gemini (same creds as Veo)
    gcp_creds = settings.get("vertex_service_account_path")
    gcp_project = settings.get("vertex_project_id")

    if not gcp_creds or not gcp_project:
        return {"status": "error", "detail": "GCP credentials not configured. Set up Vertex AI in settings."}

    # Resolve video path
    video_full_path = PROJECT_DATA_DIR / req.prev_video_path.replace("project_data/", "")
    if not video_full_path.exists():
        return {"status": "error", "detail": f"Video file not found: {req.prev_video_path}"}

    # Resolve additional video paths (for multi-video context)
    additional_video_full_paths: List[str] = []
    if req.additional_video_paths:
        for vp in req.additional_video_paths:
            full_path = PROJECT_DATA_DIR / vp.replace("project_data/", "")
            if full_path.exists():
                additional_video_full_paths.append(str(full_path))
            else:
                print(f"[AI DIRECTOR] Skipping missing additional video: {vp}")

    # Get scene info
    scene = get_scene(req.project_id, req.scene_id)
    if not scene:
        return {"status": "error", "detail": "Scene not found"}

    # Find the shot we're planning
    shot = next((s for s in scene.get("shots", []) if s.get("shot_id") == req.shot_id), None)
    if not shot:
        return {"status": "error", "detail": "Shot not found"}

    # Get all characters
    characters = list_characters(req.project_id)

    # Get scene cast (which characters are IN this scene)
    scene_cast = scene.get("cast", [])
    cast_character_ids = [c.get("character_id") for c in scene_cast]

    # Build character reference images dict: {character_name: [image_paths]}
    # If user selected specific refs, use ONLY those
    character_ref_images: Dict[str, List[str]] = {}
    all_media = list_media(req.project_id)  # Get media once, outside the loop

    # Log what we received
    print(f"[AI DIRECTOR] selected_ref_ids from frontend: {req.selected_ref_ids}")

    if req.selected_ref_ids:
        # User selected specific images - use ONLY those
        print(f"[AI DIRECTOR] Using ONLY user-selected refs: {req.selected_ref_ids}")

        # Build reverse lookup: media_id -> character_name
        media_to_character: Dict[str, str] = {}
        for char in characters:
            char_name = char.get("name", "Unknown")
            char_id = char.get("character_id")

            # Check global refs
            for ref_id in char.get("reference_image_ids", []):
                media_to_character[ref_id] = char_name

            # Check scene-specific refs
            cast_entry = next((c for c in scene_cast if c.get("character_id") == char_id), None)
            if cast_entry:
                for ref_id in cast_entry.get("scene_reference_ids", []):
                    media_to_character[ref_id] = char_name

        # Also check master images (scene-level refs without character)
        master_image_ids = scene.get("master_image_ids", [])

        # Now build character_ref_images from ONLY selected IDs
        for ref_id in req.selected_ref_ids:
            media_item = next((m for m in all_media if m.get("id") == ref_id), None)
            if media_item and media_item.get("path"):
                full_path = PROJECT_DATA_DIR / media_item["path"].replace("project_data/", "")
                if full_path.exists():
                    # Find which character this belongs to
                    char_name = media_to_character.get(ref_id)
                    if char_name:
                        if char_name not in character_ref_images:
                            character_ref_images[char_name] = []
                        character_ref_images[char_name].append(str(full_path))
                        print(f"[AI DIRECTOR] Added ref {ref_id} for {char_name}: {full_path}")
                    elif ref_id in master_image_ids:
                        # It's a master/scene image
                        if "Scene Reference" not in character_ref_images:
                            character_ref_images["Scene Reference"] = []
                        character_ref_images["Scene Reference"].append(str(full_path))
                        print(f"[AI DIRECTOR] Added scene master ref {ref_id}: {full_path}")
                    else:
                        # Unknown character - still include it
                        if "Other" not in character_ref_images:
                            character_ref_images["Other"] = []
                        character_ref_images["Other"].append(str(full_path))
                        print(f"[AI DIRECTOR] Added ref {ref_id} (no char match): {full_path}")
    else:
        # No user selection - use all character refs (legacy behavior)
        print("[AI DIRECTOR] No selected_ref_ids - using ALL character refs (legacy)")
        for char in characters:
            char_name = char.get("name", "Unknown")
            char_id = char.get("character_id")

            # Check if character is in scene cast and has scene-specific refs
            cast_entry = next((c for c in scene_cast if c.get("character_id") == char_id), None)
            if cast_entry and cast_entry.get("scene_reference_ids"):
                ref_ids = cast_entry["scene_reference_ids"]
            else:
                ref_ids = char.get("reference_image_ids", [])

            # Resolve IDs to actual file paths
            ref_paths = []
            for ref_id in ref_ids[:2]:  # Limit to 2 refs per character to avoid token limits
                # Look up media by ID
                media_item = next((m for m in all_media if m.get("id") == ref_id), None)
                if media_item and media_item.get("path"):
                    full_path = PROJECT_DATA_DIR / media_item["path"].replace("project_data/", "")
                    if full_path.exists():
                        ref_paths.append(str(full_path))

            if ref_paths:
                character_ref_images[char_name] = ref_paths

    print(f"[AI DIRECTOR] Final character_ref_images: {character_ref_images}")

    # Build prior shots summary for narrative context
    shots = scene.get("shots", [])
    current_shot_idx = next((i for i, s in enumerate(shots) if s.get("shot_id") == req.shot_id), 0)
    prior_shots_summary = []
    for i, s in enumerate(shots[:current_shot_idx]):
        summary = f"Shot {i+1}: {s.get('subject', 'Unknown')} - {s.get('action', 'No action')}"
        if s.get('dialogue'):
            summary += f" (Dialogue: \"{s['dialogue'][:50]}...\")" if len(s.get('dialogue', '')) > 50 else f" (Dialogue: \"{s['dialogue']}\")"
        prior_shots_summary.append(summary)

    # Build scene context
    scene_context = scene.get("description", "")
    if scene.get("location_notes"):
        scene_context += f"\nLocation: {scene['location_notes']}"

    # Build visual style string
    style_parts = []
    if scene.get("visual_style"):
        style_parts.append(scene["visual_style"])
    if scene.get("color_palette"):
        style_parts.append(f"Colors: {scene['color_palette']}")
    if scene.get("camera_style"):
        style_parts.append(f"Camera: {scene['camera_style']}")
    if scene.get("tone_notes"):
        style_parts.append(f"Tone: {scene['tone_notes']}")
    visual_style = ". ".join(style_parts) if style_parts else None

    try:
        client = VertexClient(
            credentials_path=gcp_creds,
            project_id=gcp_project,
            location="us-central1"
        )

        result = client.plan_shot_from_video(
            video_path=str(video_full_path),
            scene_context=scene_context,
            next_shot_info=shot,
            available_characters=characters,
            visual_style=visual_style,
            character_ref_images=character_ref_images,
            scene_cast_ids=cast_character_ids,
            prior_shots_summary=prior_shots_summary,
            additional_video_paths=additional_video_full_paths if additional_video_full_paths else None
        )

        if result.get("status") == "error":
            return {"status": "error", "detail": result.get("error", "Unknown error")}

        return {
            "status": "ok",
            "plan": {
                "video_end_state": result.get("video_end_state", ""),
                "characters_in_shot": result.get("characters_in_shot", []),
                "use_prev_last_frame": result.get("use_prev_last_frame", True),
                "image_prompt": result.get("image_prompt", ""),
                "video_prompt": result.get("video_prompt", ""),
                "continuity_notes": result.get("continuity_notes", ""),
                "reasoning": result.get("reasoning", "")
            },
            "prev_video_path": req.prev_video_path  # Include for frame extraction
        }

    except Exception as e:
        logger.error(f"AI shot planning failed: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "detail": str(e)}


class ExtractRefFrameRequest(BaseModel):
    project_id: str
    scene_id: str
    video_path: str
    timestamp_seconds: float
    description: str
    frame_type: str  # "character" or "scene"
    character_name: Optional[str] = None  # Required if frame_type is "character"
    auto_add_to_refs: bool = True  # Whether to auto-add as scene-specific ref


@app.post("/ai/extract-ref-frame")
def extract_ref_frame(req: ExtractRefFrameRequest):
    """
    Extract a frame from a video at a specific timestamp and add it to the media library.
    Optionally auto-adds it as a scene-specific reference for the character or scene.
    """
    from backend.video.ffmpeg import extract_frame_at_timestamp

    # Resolve video path
    video_full_path = PROJECT_DATA_DIR / req.video_path.replace("project_data/", "")
    if not video_full_path.exists():
        return {"status": "error", "detail": f"Video file not found: {req.video_path}"}

    # Get scene
    scene = get_scene(req.project_id, req.scene_id)
    if not scene:
        return {"status": "error", "detail": "Scene not found"}

    # Generate UNIQUE output filename using epoch timestamp
    import time as time_mod
    epoch_ts = int(time_mod.time())
    video_ts_str = f"{req.timestamp_seconds:.2f}".replace(".", "_")
    if req.frame_type == "character" and req.character_name:
        # Sanitize character name for filename
        safe_char_name = "".join(c if c.isalnum() else "_" for c in req.character_name)
        filename = f"{epoch_ts}_ref_{safe_char_name}_{video_ts_str}.png"
    else:
        filename = f"{epoch_ts}_ref_scene_{video_ts_str}.png"

    # Output path in media/images
    dirs = media_dirs(req.project_id)
    output_path = dirs["images"] / filename

    try:
        # Extract the frame
        extract_frame_at_timestamp(str(video_full_path), req.timestamp_seconds, str(output_path))

        # Add to media library
        rel_path = str(output_path.relative_to(PROJECT_DATA_DIR))
        media_item = add_media(req.project_id, {
            "id": filename,
            "type": "image",
            "path": f"project_data/{rel_path}",
            "url": f"/files/{rel_path}",
            "source": "extracted_ref",
            "description": req.description,
            "from_video": req.video_path,
            "extracted_timestamp": req.timestamp_seconds
        })

        result = {
            "status": "ok",
            "media_id": media_item.get("id"),
            "path": media_item.get("path"),
            "url": media_item.get("url")
        }

        # Auto-add to scene-specific refs if requested
        if req.auto_add_to_refs:
            meta = read_metadata(req.project_id)

            if req.frame_type == "character" and req.character_name:
                # Find the character by name
                characters = meta.get("characters", [])
                char = next((c for c in characters if c.get("name") == req.character_name), None)

                if char:
                    char_id = char.get("character_id")
                    # Find scene and update cast's scene_reference_ids
                    for s in meta.get("scenes", []):
                        if s.get("scene_id") == req.scene_id:
                            cast = s.setdefault("cast", [])
                            # Find or create cast entry for this character
                            cast_entry = next((c for c in cast if c.get("character_id") == char_id), None)
                            if cast_entry:
                                scene_refs = cast_entry.setdefault("scene_reference_ids", [])
                                if media_item.get("id") not in scene_refs:
                                    scene_refs.append(media_item.get("id"))
                            else:
                                # Create new cast entry
                                cast.append({
                                    "character_id": char_id,
                                    "scene_reference_ids": [media_item.get("id")]
                                })
                            write_metadata(req.project_id, meta)
                            result["added_to_character_refs"] = req.character_name
                            break

            elif req.frame_type == "scene":
                # Add to scene master_image_ids
                for s in meta.get("scenes", []):
                    if s.get("scene_id") == req.scene_id:
                        master_ids = s.setdefault("master_image_ids", [])
                        if media_item.get("id") not in master_ids:
                            master_ids.append(media_item.get("id"))
                        write_metadata(req.project_id, meta)
                        result["added_to_scene_masters"] = True
                        break

        return result

    except Exception as e:
        logger.error(f"Frame extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "detail": str(e)}


# ============================================================================
# Scene Export
# ============================================================================

@app.post("/render/export-scene/{project_id}/{scene_id}")
def export_scene(project_id: str, scene_id: str):
    """Export all video-ready shots as numbered files."""
    import os

    scene = get_scene(project_id, scene_id)
    if not scene:
        return {"status": "error", "detail": "Scene not found"}

    export_dir = PROJECT_DATA_DIR / project_id / "exports" / scene_id
    export_dir.mkdir(parents=True, exist_ok=True)

    exported = []
    for i, shot in enumerate(scene.get("shots", [])):
        file_path = shot.get("file_path")
        status = shot.get("status", "")

        # Export shots that have a video file
        if file_path:
            src_path = Path(file_path)
            if not src_path.is_absolute():
                src_path = Path.cwd() / file_path

            if src_path.exists():
                dst = export_dir / f"{str(i+1).zfill(3)}.mp4"
                shutil.copy(src_path, dst)
                exported.append({
                    "shot_id": shot.get("shot_id"),
                    "file": str(dst.name),
                    "duration": shot.get("duration")
                })

    return {
        "status": "ok",
        "export_dir": str(export_dir),
        "files": exported,
        "count": len(exported)
    }


class SceneRenderRequest(BaseModel):
    project_id: str
    shot_ids: List[str]


@app.post("/render/scene")
def render_scene(req: SceneRenderRequest):
    # Stub: MoviePy concat pending
    return {"status": "not_implemented", "detail": "Scene rendering pending"}


class FilmRenderRequest(BaseModel):
    project_id: str
    scene_ids: List[str]


@app.post("/render/film")
def render_film(req: FilmRenderRequest):
    # Stub: MoviePy concat pending
    return {"status": "not_implemented", "detail": "Film rendering pending"}


@app.post("/storage/init-project/{project_id}")
def init_project(project_id: str):
    proj_dir = PROJECT_DATA_DIR / project_id
    media_dir = proj_dir / "media"
    proj_dir.mkdir(parents=True, exist_ok=True)
    media_dir.mkdir(parents=True, exist_ok=True)
    meta_path = proj_dir / "metadata.json"
    if not meta_path.exists():
        meta = {
            "project_id": project_id,
            "scenes": [],
            "shots": [],
            "characters": [],
            "media": []
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
    return {"status": "ok", "project_dir": str(proj_dir)}


# Storage: scenes & shots
class SceneCreate(BaseModel):
    scene_id: str
    title: str


@app.get("/storage/{project_id}/scenes")
def api_list_scenes(project_id: str):
    return {"scenes": list_scenes(project_id)}


@app.post("/storage/{project_id}/scenes")
def api_add_scene(project_id: str, body: SceneCreate):
    scene = add_scene(project_id, body.scene_id, body.title)
    return {"status": "ok", "scene": scene}


@app.get("/storage/{project_id}/scenes/{scene_id}")
def api_get_scene(project_id: str, scene_id: str):
    scene = get_scene(project_id, scene_id)
    if scene is None:
        return {"status": "not_found"}
    return {"scene": scene}


class SceneCast(BaseModel):
    """Character appearance in a specific scene"""
    character_id: str
    appearance_notes: Optional[str] = None  # "Muddy clothes", "Formal wear"
    scene_reference_ids: List[str] = []  # Scene-specific ref images


class SceneUpdate(BaseModel):
    title: Optional[str] = None
    shot_order: Optional[List[str]] = None
    # Scene context fields
    description: Optional[str] = None
    location_notes: Optional[str] = None
    master_image_ids: Optional[List[str]] = None
    cast: Optional[List[dict]] = None  # List of SceneCast dicts
    # Visual style/tone (Phase 1 setup)
    visual_style: Optional[str] = None  # "gritty noir", "dreamy soft focus", etc.
    color_palette: Optional[str] = None  # "desaturated blues", "warm golden tones"
    camera_style: Optional[str] = None  # "handheld documentary", "locked off static"
    tone_notes: Optional[str] = None  # Additional cinematography notes
    setup_complete: Optional[bool] = None  # True when Phase 1 is done


@app.put("/storage/{project_id}/scenes/{scene_id}")
def api_update_scene(project_id: str, scene_id: str, body: SceneUpdate):
    meta_path = PROJECT_DATA_DIR / project_id / "metadata.json"
    if not meta_path.exists():
        return {"status": "not_found"}
    with open(meta_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for s in data.get("scenes", []):
        if s.get("scene_id") == scene_id:
            if body.title is not None:
                s["title"] = body.title
            if body.description is not None:
                s["description"] = body.description
            if body.location_notes is not None:
                s["location_notes"] = body.location_notes
            if body.master_image_ids is not None:
                s["master_image_ids"] = body.master_image_ids
            if body.cast is not None:
                s["cast"] = body.cast
            if body.visual_style is not None:
                s["visual_style"] = body.visual_style
            if body.color_palette is not None:
                s["color_palette"] = body.color_palette
            if body.camera_style is not None:
                s["camera_style"] = body.camera_style
            if body.tone_notes is not None:
                s["tone_notes"] = body.tone_notes
            if body.setup_complete is not None:
                s["setup_complete"] = body.setup_complete
            if body.shot_order is not None:
                # Reorder shots based on shot_order list
                shots = s.get("shots", [])
                shot_map = {sh["shot_id"]: sh for sh in shots}
                reordered = []
                for shot_id in body.shot_order:
                    if shot_id in shot_map:
                        reordered.append(shot_map[shot_id])
                s["shots"] = reordered
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return {"status": "ok", "scene": s}
    return {"status": "not_found"}


class ShotCreate(BaseModel):
    shot_id: str
    # Planning fields
    shot_number: Optional[int] = None
    camera_angle: Optional[str] = None  # "Wide", "Medium", "Close-up", etc.
    subject: Optional[str] = None  # Who/what is the focus
    action: Optional[str] = None  # What happens in this shot
    dialogue: Optional[str] = None  # Any dialogue in this shot
    characters_in_shot: Optional[List[str]] = None  # Auto-ID'd character IDs
    status: Optional[str] = "planned"  # "planned" | "image_ready" | "audio_ready" | "video_ready"
    # Image generation
    prompt: Optional[str] = None
    start_frame_path: Optional[str] = None  # Generated start frame image
    # Audio
    audio_path: Optional[str] = None  # Voice/dialogue audio
    audio_character_id: Optional[str] = None  # Who's speaking
    # Video generation
    model: Optional[str] = None
    duration: Optional[float] = None
    file_path: Optional[str] = None  # Final video
    first_frame_path: Optional[str] = None
    last_frame_path: Optional[str] = None
    # Progressive consistency
    continuity_frame_path: Optional[str] = None  # Frame from previous shot for consistency
    continuity_source: Optional[str] = None
    start_offset: Optional[float] = 0.0
    end_offset: Optional[float] = 0.0
    volume: Optional[float] = 1.0


@app.post("/storage/{project_id}/scenes/{scene_id}/shots")
def api_add_shot(project_id: str, scene_id: str, body: ShotCreate):
    from backend.video.ffmpeg import extract_first_last_frames, get_video_duration
    
    # Ensure scene exists; if not, create it for robustness
    scene = get_scene(project_id, scene_id)
    if scene is None:
        # Fallback create with a simple title
        try:
            add_scene(project_id, scene_id, scene_id.replace("_", " ").title())
        except Exception:
            pass
    
    shot_data = body.model_dump(exclude_none=True)
    
    # If this is a video shot, handle frames and duration
    if shot_data.get('file_path'):
        try:
            file_path = shot_data['file_path']
            # Resolve to absolute path
            if file_path.startswith('project_data/'):
                abs_path = PROJECT_DATA_DIR / file_path.replace('project_data/', '')
            else:
                abs_path = Path(file_path)
            
            if abs_path.exists() and abs_path.suffix.lower() in ['.mp4', '.mov', '.avi', '.mkv']:
                # 1. Extract frames if missing
                if not shot_data.get('first_frame_path'):
                    # Extract frames to scene frames directory
                    dirs = ensure_scene_dirs(project_id, scene_id)
                    shot_id = shot_data.get('shot_id', f"shot_{int(__import__('time').time())}")
                    first_frame = dirs["frames"] / f"{shot_id}_first.png"
                    last_frame = dirs["frames"] / f"{shot_id}_last.png"
                    
                    logger.info(f"Extracting frames for {file_path} to {first_frame} and {last_frame}")
                    extract_first_last_frames(str(abs_path), str(first_frame), str(last_frame))
                    
                    # Verify extraction succeeded
                    if first_frame.exists():
                        rel_first = str(first_frame.relative_to(PROJECT_DATA_DIR))
                        shot_data['first_frame_path'] = f"project_data/{rel_first}"
                        logger.info(f"First frame extracted: {shot_data['first_frame_path']}")
                    else:
                        logger.warning(f"First frame extraction failed - file not created: {first_frame}")
                    
                    if last_frame.exists():
                        rel_last = str(last_frame.relative_to(PROJECT_DATA_DIR))
                        shot_data['last_frame_path'] = f"project_data/{rel_last}"
                        logger.info(f"Last frame extracted: {shot_data['last_frame_path']}")
                    else:
                        logger.warning(f"Last frame extraction failed - file not created: {last_frame}")
                
                # 2. Probe and update duration
                # Always probe to get accurate duration, overriding any default
                duration = get_video_duration(str(abs_path))
                if duration > 0:
                    shot_data['duration'] = duration
                    logger.info(f"Probed duration for {file_path}: {duration}s")
                else:
                    logger.warning(f"Could not probe duration for {file_path}")
                    
        except Exception as e:
            logger.warning(f"Failed to process video for imported shot: {e}", exc_info=True)
    
    shot = add_shot(project_id, scene_id, shot_data)
    logger.info(f"Added shot {shot_data.get('shot_id')} with duration {shot_data.get('duration')}")
    return {"status": "ok", "shot": shot}


# Media upload/list
@app.get("/storage/{project_id}/media")
def api_list_media(project_id: str):
    # Auto-scan if metadata is empty but files exist on disk
    items = list_media(project_id)
    try:
        proj_dir = PROJECT_DATA_DIR / project_id
        media_dir = proj_dir / "media"
        video_dir = media_dir / "video"
        audio_dir = media_dir / "audio"
        images_dir = media_dir / "images"
        has_files = any(video_dir.glob("*")) or any(audio_dir.glob("*")) or any(images_dir.glob("*"))
        if (not items) and has_files:
            api_scan_media(project_id)
            items = list_media(project_id)
    except Exception:
        pass
    
    # Backfill timestamps for any items missing them
    import time as time_module
    meta = read_metadata(project_id)
    media_list = meta.get("media", [])
    modified = False
    for item in media_list:
        if "timestamp" not in item:
            # Try to extract timestamp from ID, or use current time
            try:
                match = __import__('re').match(r'^(\d{10,13})', item.get("id", ""))
                item["timestamp"] = int(match.group(1)) if match else int(time_module.time())
            except:
                item["timestamp"] = int(time_module.time())
            modified = True
    if modified:
        write_metadata(project_id, meta)
        items = list_media(project_id)
    
    return {"media": items}


@app.post("/storage/{project_id}/media")
async def api_upload_media(project_id: str, file: UploadFile = File(...)):
    dirs = media_dirs(project_id)
    filename = file.filename or "upload.bin"
    lower = filename.lower()
    # Determine type and directory
    if lower.endswith((".mp4", ".mov", ".m4v")):
        mtype_dir = "video"
        mtype = "video"
    elif lower.endswith((".wav", ".mp3", ".aac", ".flac")):
        mtype_dir = "audio"
        mtype = "audio"
    elif lower.endswith((".png", ".jpg", ".jpeg", ".webp")):
        mtype_dir = "images"
        mtype = "image"
    else:
        mtype_dir = "video"
        mtype = "video"
    
    target_dir = dirs[mtype_dir]
    safe_name = f"{int(__import__('time').time())}_{filename.replace('/', '_')}"
    target_path = target_dir / safe_name
    with open(target_path, "wb") as out:
        out.write(await file.read())
    rel_from_project = str(target_path.relative_to(PROJECT_DATA_DIR))
    file_url = f"/files/{rel_from_project}"
    item = {
        "id": safe_name,
        "type": mtype,
        "path": f"project_data/{rel_from_project}",
        "url": file_url,
        "source": "uploaded",
    }
    add_media(project_id, item)
    return {"status": "ok", "item": item}

@app.get("/storage/projects")
def api_list_projects():
    projects = []
    for p in PROJECT_DATA_DIR.iterdir():
        if p.is_dir() and not p.name.startswith("_"):
            projects.append(p.name)
    return {"projects": projects}

# Shot update/delete
class ShotUpdate(BaseModel):
    # Planning fields
    shot_number: Optional[int] = None
    camera_angle: Optional[str] = None
    subject: Optional[str] = None
    action: Optional[str] = None
    dialogue: Optional[str] = None
    characters_in_shot: Optional[List[str]] = None
    status: Optional[str] = None
    # Image/Audio/Video
    prompt: Optional[str] = None
    start_frame_path: Optional[str] = None
    audio_path: Optional[str] = None
    audio_character_id: Optional[str] = None
    duration: Optional[float] = None
    start_offset: Optional[float] = None
    end_offset: Optional[float] = None
    volume: Optional[float] = None
    file_path: Optional[str] = None
    first_frame_path: Optional[str] = None
    last_frame_path: Optional[str] = None
    continuity_frame_path: Optional[str] = None


@app.put("/storage/{project_id}/scenes/{scene_id}/shots/{shot_id}")
def api_update_shot(project_id: str, scene_id: str, shot_id: str, body: ShotUpdate):
    meta_path = PROJECT_DATA_DIR / project_id / "metadata.json"
    if not meta_path.exists():
        return {"status": "not_found"}
    with open(meta_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for s in data.get("scenes", []):
        if s.get("scene_id") == scene_id:
            for sh in s.get("shots", []):
                if sh.get("shot_id") == shot_id:
                    updates = body.model_dump(exclude_none=True)
                    for k, v in updates.items():
                        sh[k] = v

                    # Auto-update status based on what's being set
                    # Priority: video_ready > audio_ready > image_ready > planned
                    if "file_path" in updates and updates["file_path"]:
                        sh["status"] = "video_ready"
                    elif "audio_path" in updates and updates["audio_path"]:
                        if sh.get("status") != "video_ready":
                            sh["status"] = "audio_ready"
                    elif "start_frame_path" in updates and updates["start_frame_path"]:
                        if sh.get("status") not in ("video_ready", "audio_ready"):
                            sh["status"] = "image_ready"

                    with open(meta_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
                    return {"status": "ok", "shot": sh}
    return {"status": "not_found"}


@app.delete("/storage/{project_id}/scenes/{scene_id}/shots/{shot_id}")
def api_delete_shot(project_id: str, scene_id: str, shot_id: str):
    meta_path = PROJECT_DATA_DIR / project_id / "metadata.json"
    if not meta_path.exists():
        return {"status": "not_found"}
    with open(meta_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for s in data.get("scenes", []):
        if s.get("scene_id") == scene_id:
            before = len(s.get("shots", []))
            s["shots"] = [sh for sh in s.get("shots", []) if sh.get("shot_id") != shot_id]
            after = len(s["shots"])
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return {"status": "ok", "deleted": before - after}
    return {"status": "not_found"}


@app.get("/media/metadata")
def api_media_metadata(path: str):
    """Return simple metadata like duration using ffprobe."""
    from subprocess import run, PIPE
    # Normalize to filesystem path
    p = Path(path)
    if not p.is_absolute():
        p = Path.cwd() / path
    if not p.exists():
        return {"status": "not_found"}
    try:
        cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "format=duration", "-of", "default=nokey=1:noprint_wrappers=1", str(p)]
        r = run(cmd, stdout=PIPE, stderr=PIPE, check=False, text=True)
        dur = float(r.stdout.strip()) if r.stdout.strip() else None
        return {"status": "ok", "duration": dur}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

class FrameExtractBody(BaseModel):
    project_id: str
    video_path: str  # absolute or project-relative path (e.g., project_data/...)
    scene_id: Optional[str] = None
    shot_id: Optional[str] = None

def _normalize_path(p: str) -> Path:
    pp = Path(p)
    if not pp.is_absolute():
        pp = Path.cwd() / p
    return pp

@app.post("/frames/last")
def api_extract_last_frame(body: FrameExtractBody):
    """Extract the last frame of a video into the project's images folder and return its path/url."""
    try:
        proj = PROJECT_DATA_DIR / body.project_id
        media_images = proj / "media" / "images"
        media_images.mkdir(parents=True, exist_ok=True)
        video_p = _normalize_path(body.video_path)
        if not video_p.exists():
            return {"status": "not_found", "detail": f"Video not found: {video_p}"}
        from backend.video.ffmpeg import extract_first_last_frames
        # Use temp paths then move last frame into images folder
        tmp_first = proj / "tmp_first.png"
        tmp_last = proj / "tmp_last.png"
        extract_first_last_frames(str(video_p), str(tmp_first), str(tmp_last))
        # Final path name based on source video
        out_name = f"{video_p.stem}_last.png"
        out_path = media_images / out_name
        try:
            if out_path.exists():
                out_path.unlink()
        except Exception:
            pass
        tmp_last.replace(out_path)
        rel = str(out_path.relative_to(PROJECT_DATA_DIR))
        return {"status": "ok", "image_path": f"project_data/{rel}", "url": f"/files/{rel}"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/frames/first")
def api_extract_first_frame(body: FrameExtractBody):
    """Extract the first frame of a video into the project's images folder and return its path/url."""
    try:
        proj = PROJECT_DATA_DIR / body.project_id
        media_images = proj / "media" / "images"
        media_images.mkdir(parents=True, exist_ok=True)
        video_p = _normalize_path(body.video_path)
        if not video_p.exists():
            return {"status": "not_found", "detail": f"Video not found: {video_p}"}
        from backend.video.ffmpeg import extract_first_last_frames
        tmp_first = proj / "tmp_first.png"
        tmp_last = proj / "tmp_last.png"
        extract_first_last_frames(str(video_p), str(tmp_first), str(tmp_last))
        out_name = f"{video_p.stem}_first.png"
        out_path = media_images / out_name
        try:
            if out_path.exists():
                out_path.unlink()
        except Exception:
            pass
        tmp_first.replace(out_path)
        rel = str(out_path.relative_to(PROJECT_DATA_DIR))
        return {"status": "ok", "image_path": f"project_data/{rel}", "url": f"/files/{rel}"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/storage/{project_id}/media/fix-formats")
def api_fix_media_formats(project_id: str):
    """
    Re-encode any videos that aren't in browser-compatible format.
    This fixes playback issues with videos that have incompatible codecs.
    """
    from backend.video.ffmpeg import ensure_compatible_format
    import tempfile
    
    proj_dir = PROJECT_DATA_DIR / project_id
    video_dir = proj_dir / "media" / "video"
    
    if not video_dir.exists():
        return {"status": "ok", "fixed": 0}
    
    fixed_count = 0
    for video_file in video_dir.glob("*.mp4"):
        # Check if video is compatible
        probe = subprocess.run([
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=codec_name,pix_fmt",
            "-of", "csv=p=0", str(video_file)
        ], capture_output=True, text=True)
        
        if probe.returncode == 0:
            codec_info = probe.stdout.strip()
            # Check if it's h264 with yuv420p
            if "h264" not in codec_info or "yuv420p" not in codec_info:
                try:
                    # Re-encode to compatible format
                    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                        tmp_path = tmp.name
                    
                    ensure_compatible_format(str(video_file), tmp_path)
                    # Replace original with fixed version
                    Path(tmp_path).replace(video_file)
                    fixed_count += 1
                except Exception as e:
                    print(f"Failed to fix {video_file.name}: {e}")
    
    return {"status": "ok", "fixed": fixed_count}


@app.post("/storage/{project_id}/media/normalize-types")
def api_normalize_media_types(project_id: str):
    """
    Fix any media items with incorrect type values (e.g., 'images' instead of 'image').
    Returns number of items fixed.
    """
    ensure_project(project_id)
    meta = read_metadata(project_id)
    media_list = meta.get("media", [])
    fixed_count = 0
    
    for item in media_list:
        old_type = item.get("type")
        # Normalize types
        if old_type == "images":
            item["type"] = "image"
            fixed_count += 1
        elif old_type == "videos":
            item["type"] = "video"
            fixed_count += 1
        elif old_type == "audios":
            item["type"] = "audio"
            fixed_count += 1
        
        # Also ensure source is set
        if "source" not in item:
            file_id = item.get("id", "")
            if "_first.png" in file_id or "_last.png" in file_id:
                item["source"] = "extracted"
            else:
                item["source"] = "generated"
            fixed_count += 1
    
    if fixed_count > 0:
        write_metadata(project_id, meta)
    
    return {"status": "ok", "fixed": fixed_count}

@app.post("/storage/{project_id}/media/scan")
def api_scan_media(project_id: str):
    """
    Scan project_data/<project_id>/media/{video,audio,images} for files that are not
    present in metadata and add them. Returns number of new items indexed.
    Also normalizes any incorrect types.
    """
    ensure_project(project_id)
    proj_dir = PROJECT_DATA_DIR / project_id
    media_dir = proj_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    video_dir = media_dir / "video"
    audio_dir = media_dir / "audio"
    images_dir = media_dir / "images"
    video_dir.mkdir(parents=True, exist_ok=True)
    audio_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)

    # First, deduplicate existing items
    existing = read_metadata(project_id).get("media", [])
    seen_ids = set()
    unique_existing = []
    for item in existing:
        mid = item.get("id")
        if mid not in seen_ids:
            seen_ids.add(mid)
            unique_existing.append(item)
    existing = unique_existing
    existing_ids = seen_ids

    new_items = []

    def add_item(file_path: Path, kind: str):
        nonlocal new_items, existing_ids, existing
        file_id = file_path.name
        if file_id in existing_ids:
            return
        rel_from_project = str(file_path.relative_to(PROJECT_DATA_DIR))
        url = f"/files/{rel_from_project}"
        import time as time_module
        # Auto-tag source based on filename patterns
        source = "extracted" if ("_first.png" in file_id or "_last.png" in file_id) else "generated"
        item = {
            "id": file_id,
            "type": kind,
            "path": f"project_data/{rel_from_project}",
            "url": url,
            "source": source,
            "timestamp": int(time_module.time()),
        }
        existing.append(item)
        existing_ids.add(file_id)
        new_items.append(item)

    # Scan each folder
    for f in video_dir.glob("*"):
        if f.is_file() and f.suffix.lower() in {".mp4", ".mov", ".m4v"}:
            add_item(f, "video")
    for f in audio_dir.glob("*"):
        if f.is_file() and f.suffix.lower() in {".wav", ".mp3", ".aac", ".flac"}:
            add_item(f, "audio")
    for f in images_dir.glob("*"):
        if f.is_file() and f.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            add_item(f, "image")

    # Normalize types in existing items before persisting
    for item in existing:
        if item.get("type") == "images":
            item["type"] = "image"
        elif item.get("type") == "videos":
            item["type"] = "video"
        elif item.get("type") == "audios":
            item["type"] = "audio"
    
    # Persist
    meta = read_metadata(project_id)
    meta["media"] = existing
    write_metadata(project_id, meta)
    return {"status": "ok", "indexed": len(new_items), "items": new_items}


class ArchiveMediaRequest(BaseModel):
    media_id: str
    archived: bool = True


class BulkArchiveMediaRequest(BaseModel):
    media_ids: List[str]
    archived: bool = True


@app.put("/storage/{project_id}/media/archive")
def api_archive_media(project_id: str, body: ArchiveMediaRequest):
    """Archive or unarchive a single media item."""
    result = archive_media(project_id, body.media_id, body.archived)
    if not result["success"]:
        return {"status": "error", "detail": result.get("error", "Unknown error")}
    return {"status": "ok", "archived": body.archived}


@app.post("/storage/{project_id}/media/bulk-archive")
def api_bulk_archive_media(project_id: str, body: BulkArchiveMediaRequest):
    """Archive or unarchive multiple media items."""
    result = bulk_archive_media(project_id, body.media_ids, body.archived)
    response = {
        "status": "ok", 
        "count": result["count"], 
        "archived": body.archived
    }
    if result["skipped"]:
        response["skipped"] = result["skipped"]
        response["message"] = f"{result['count']} items archived. {len(result['skipped'])} items skipped (in use by characters)."
    return response


@app.get("/storage/{project_id}/media/archived")
def api_list_archived_media(project_id: str):
    """Get list of archived media items."""
    all_media = list_media(project_id, include_archived=True)
    archived = [m for m in all_media if m.get("archived", False)]
    return {"media": archived}

# Settings
@app.get("/settings")
def api_get_settings():
    return {"settings": read_settings()}


class SettingsBody(BaseModel):
    replicate_api_token: Optional[str] = None
    elevenlabs_api_key: Optional[str] = None
    wavespeed_api_key: Optional[str] = None
    vertex_service_account_path: Optional[str] = None
    vertex_project_id: Optional[str] = None
    vertex_location: Optional[str] = None
    vertex_temp_bucket: Optional[str] = None
    # LLM API keys for AI Cinematographer
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    llm_provider: Optional[str] = None  # "openai" or "anthropic"


@app.post("/settings")
def api_set_settings(body: SettingsBody):
    current = read_settings()
    current.update({k: v for k, v in body.model_dump().items() if v is not None})
    write_settings(current)
    return {"status": "ok"}


class RevealFileRequest(BaseModel):
    file_path: str


@app.post("/storage/reveal-file")
def api_reveal_file(body: RevealFileRequest):
    """
    Reveal a file in the system file manager (Finder on macOS, Explorer on Windows, etc.)
    """
    import platform
    
    # Normalize the path using existing helper
    abs_path = _normalize_path(body.file_path)
    
    if not abs_path.exists():
        return {"status": "error", "detail": f"File not found: {abs_path}"}
    
    try:
        system = platform.system()
        if system == "Darwin":  # macOS
            # Use 'open -R' to reveal file in Finder
            subprocess.run(["open", "-R", str(abs_path)], check=True)
        elif system == "Windows":
            # Use explorer to select file
            subprocess.run(["explorer", "/select,", str(abs_path)], check=True)
        else:  # Linux and others
            # Try xdg-open to open parent directory
            parent_dir = abs_path.parent
            subprocess.run(["xdg-open", str(parent_dir)], check=True)
        
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# Last frame info for a shot
@app.get("/storage/{project_id}/scenes/{scene_id}/shots/{shot_id}/last-frame")
def api_last_frame(project_id: str, scene_id: str, shot_id: str):
    scene = get_scene(project_id, scene_id)
    if not scene:
        return {"status": "not_found"}
    for sh in scene.get("shots", []):
        if sh.get("shot_id") == shot_id:
            path = sh.get("last_frame_path")
            if not path:
                return {"status": "not_found"}
            rel = path.replace("project_data/", "")
            return {"status": "ok", "path": path, "url": f"/files/{rel}"}
    return {"status": "not_found"}


class OpticalFlowRequest(BaseModel):
    project_id: str
    scene_id: str
    shot_a_id: str
    shot_b_id: str
    transition_frames: Optional[int] = 15
    replace_shots: Optional[bool] = True  # Replace the two shots with merged one


@app.post("/video/optical-flow")
async def api_optical_flow(req: OpticalFlowRequest):
    """Apply optical flow smoothing between two shots."""
    from backend.video.ffmpeg import optical_flow_smooth
    import time
    
    scene = get_scene(req.project_id, req.scene_id)
    if not scene:
        return {"status": "error", "detail": "Scene not found"}
    
    shots = scene.get("shots", [])
    shot_a = next((s for s in shots if s["shot_id"] == req.shot_a_id), None)
    shot_b = next((s for s in shots if s["shot_id"] == req.shot_b_id), None)
    
    if not shot_a or not shot_b:
        return {"status": "error", "detail": "Shots not found"}
    
    path_a = shot_a.get("file_path")
    path_b = shot_b.get("file_path")
    
    if not path_a or not path_b:
        return {"status": "error", "detail": "Shot video files not found"}
    
    # Convert relative paths to absolute
    if not Path(path_a).is_absolute():
        path_a = str(Path.cwd() / path_a)
    if not Path(path_b).is_absolute():
        path_b = str(Path.cwd() / path_b)
    
    # Create output path
    dirs = ensure_scene_dirs(req.project_id, req.scene_id)
    timestamp = int(time.time())
    output_filename = f"{req.shot_a_id}_to_{req.shot_b_id}_smooth_{timestamp}.mp4"
    output_path = dirs["shots"] / output_filename
    
    try:
        optical_flow_smooth(path_a, path_b, str(output_path), req.transition_frames)
        
        # Extract first and last frames for the merged shot
        from backend.video.ffmpeg import extract_first_last_frames
        merged_first = dirs["shots"] / f"{output_filename}_first.png"
        merged_last = dirs["shots"] / f"{output_filename}_last.png"
        extract_first_last_frames(str(output_path), str(merged_first), str(merged_last))
        
        # Save to media library
        rel_path = f"project_data/{req.project_id}/scenes/{req.scene_id}/shots/{output_filename}"
        rel_first = f"project_data/{req.project_id}/scenes/{req.scene_id}/shots/{merged_first.name}"
        rel_last = f"project_data/{req.project_id}/scenes/{req.scene_id}/shots/{merged_last.name}"
        
        media_entry = {
            "id": output_filename,
            "type": "video",
            "path": rel_path,
            "url": f"/files/{req.project_id}/scenes/{req.scene_id}/shots/{output_filename}"
        }
        add_media(req.project_id, media_entry)
        
        # Add frames to media library too
        add_media(req.project_id, {"id": merged_first.name, "type": "image", "path": rel_first, "url": f"/files/{req.project_id}/scenes/{req.scene_id}/shots/{merged_first.name}"})
        add_media(req.project_id, {"id": merged_last.name, "type": "image", "path": rel_last, "url": f"/files/{req.project_id}/scenes/{req.scene_id}/shots/{merged_last.name}"})
        
        # If replace_shots is True, replace the two shots with the merged one
        # NOTE: Original clips remain in media library, only removed from timeline
        if req.replace_shots:
            # Get combined duration
            duration_a = shot_a.get("duration", 8)
            duration_b = shot_b.get("duration", 8)
            combined_duration = duration_a + duration_b + (req.transition_frames / 24)
            
            # Create merged shot metadata
            merged_shot = {
                "shot_id": f"{req.shot_a_id}_merged_{req.shot_b_id}",
                "prompt": f"Merged: {shot_a.get('prompt', '')} → {shot_b.get('prompt', '')}",
                "model": "optical_flow_merge",
                "provider": "ffmpeg",
                "duration": int(combined_duration),
                "file_path": rel_path,
                "first_frame_path": rel_first,
                "last_frame_path": rel_last,
            }
            
            # Update scene: remove shot_a and shot_b, insert merged shot at shot_a's position
            meta_path = PROJECT_DATA_DIR / req.project_id / "metadata.json"
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            for s in data.get("scenes", []):
                if s.get("scene_id") == req.scene_id:
                    shots_list = s.get("shots", [])
                    # Find indices
                    idx_a = next((i for i, sh in enumerate(shots_list) if sh["shot_id"] == req.shot_a_id), -1)
                    idx_b = next((i for i, sh in enumerate(shots_list) if sh["shot_id"] == req.shot_b_id), -1)
                    
                    if idx_a != -1 and idx_b != -1:
                        # Remove both shots
                        if idx_a < idx_b:
                            shots_list.pop(idx_b)
                            shots_list.pop(idx_a)
                            insert_idx = idx_a
                        else:
                            shots_list.pop(idx_a)
                            shots_list.pop(idx_b)
                            insert_idx = idx_b
                        
                        # Insert merged shot
                        shots_list.insert(insert_idx, merged_shot)
                        s["shots"] = shots_list
                    
                    break
            
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        
        return {
            "status": "ok",
            "file_path": rel_path,
            "file_url": media_entry["url"],
            "replaced": req.replace_shots
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "detail": str(e)}


# Character endpoints
class CharacterBody(BaseModel):
    character_id: str
    name: str
    voice_id: Optional[str] = None
    style_tokens: Optional[str] = None
    reference_image_ids: Optional[List[str]] = None


class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    voice_id: Optional[str] = None
    style_tokens: Optional[str] = None
    reference_image_ids: Optional[List[str]] = None


@app.get("/storage/{project_id}/characters")
def api_list_characters(project_id: str):
    return {"characters": list_characters(project_id)}


@app.post("/storage/{project_id}/characters")
def api_upsert_character(project_id: str, body: CharacterBody):
    payload = body.model_dump()
    upsert_character(project_id, payload)
    return {"status": "ok", "character": payload}


@app.put("/storage/{project_id}/characters/{character_id}")
def api_update_character(project_id: str, character_id: str, body: CharacterUpdate):
    existing = get_character(project_id, character_id)
    if not existing:
        return {"status": "not_found"}
    existing.update(body.model_dump(exclude_none=True))
    upsert_character(project_id, existing)
    return {"status": "ok", "character": existing}


@app.delete("/storage/{project_id}/characters/{character_id}")
def api_delete_character(project_id: str, character_id: str):
    deleted = delete_character(project_id, character_id)
    return {"status": "ok", "deleted": deleted}


# ============================================================================
# Custom Replicate Models
# ============================================================================

class CustomModelFetchRequest(BaseModel):
    model_id: str  # e.g. "owner/model-name" or full URL


@app.post("/replicate/fetch-schema")
def api_fetch_replicate_schema(req: CustomModelFetchRequest):
    """
    Fetch and parse schema from a Replicate model.
    Auto-detects if it's an image or video model.
    Returns parsed schema with type detection.
    """
    try:
        import requests
        
        # Extract owner/model-name from URL or ID
        model_id = req.model_id.strip()
        if model_id.startswith("http"):
            # Extract from URL like "https://replicate.com/owner/model-name"
            parts = model_id.rstrip("/").split("/")
            if len(parts) >= 2:
                model_id = f"{parts[-2]}/{parts[-1]}"
            else:
                return {"status": "error", "detail": "Invalid Replicate URL"}
        
        # Validate format
        if "/" not in model_id:
            return {"status": "error", "detail": "Model ID must be in format: owner/model-name"}
        
        owner, name = model_id.split("/", 1)
        
        # Fetch schema from Replicate API
        schema_url = f"https://replicate.com/{owner}/{name}/api/schema"
        print(f"[CUSTOM MODEL] Fetching schema from: {schema_url}")
        
        response = requests.get(schema_url, timeout=10)
        response.raise_for_status()
        schema = response.json()
        
        # Parse schema to detect model type and extract parameters
        model_type = _detect_model_type(schema)
        parameters = _parse_schema_parameters(schema)
        
        print(f"[CUSTOM MODEL] Detected type: {model_type}")
        print(f"[CUSTOM MODEL] Parameters: {len(parameters)} found")
        
        return {
            "status": "ok",
            "model_id": model_id,
            "model_type": model_type,
            "schema": schema,
            "parameters": parameters,
        }
    except requests.exceptions.RequestException as e:
        return {"status": "error", "detail": f"Failed to fetch schema: {str(e)}"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


def _detect_model_type(schema: dict) -> str:
    """
    Detect if a Replicate model is 'image' or 'video' based on its schema.
    Returns: 'image', 'video', or 'unknown'
    """
    # Check input parameters for telltale signs
    input_props = schema.get("components", {}).get("schemas", {}).get("Input", {}).get("properties", {})
    
    # Video indicators
    video_indicators = ["duration", "fps", "video", "video_path", "video_url"]
    has_video_input = any(key in input_props for key in video_indicators)
    
    # Check for duration parameter (strong video signal)
    if "duration" in input_props:
        return "video"
    
    # Check output schema
    output_schema = schema.get("components", {}).get("schemas", {}).get("Output", {})
    
    # If output is array of URIs, could be images or video
    # Check description or title for hints
    title = schema.get("info", {}).get("title", "").lower()
    description = schema.get("info", {}).get("description", "").lower()
    
    if "video" in title or "video" in description or has_video_input:
        return "video"
    
    if "image" in title or "image" in description:
        return "image"
    
    # Default to image if output is array (most common for multi-image generation)
    if output_schema.get("type") == "array":
        return "image"
    
    return "unknown"


def _parse_schema_parameters(schema: dict) -> list:
    """
    Parse Replicate schema and extract input parameters with metadata.
    Returns list of parameter definitions for UI form generation.
    """
    input_props = schema.get("components", {}).get("schemas", {}).get("Input", {}).get("properties", {})
    required_fields = schema.get("components", {}).get("schemas", {}).get("Input", {}).get("required", [])
    
    parameters = []
    
    for key, prop in input_props.items():
        param = {
            "name": key,
            "type": prop.get("type", "string"),
            "title": prop.get("title", key),
            "description": prop.get("description", ""),
            "default": prop.get("default"),
            "required": key in required_fields,
        }
        
        # Add type-specific metadata
        if param["type"] in ["integer", "number"]:
            param["minimum"] = prop.get("minimum")
            param["maximum"] = prop.get("maximum")
        
        if "enum" in prop:
            param["enum"] = prop["enum"]
            param["type"] = "enum"
        
        if prop.get("format") == "uri":
            param["format"] = "uri"
        
        # Skip overly complex types
        if param["type"] in ["object", "array"] and key not in ["image", "video", "audio"]:
            continue
        
        parameters.append(param)
    
    return parameters


class CustomModelSaveRequest(BaseModel):
    model_id: str
    friendly_name: str
    model_type: str  # 'image' or 'video'
    schema: dict
    parameters: list


@app.post("/settings/custom-models")
def api_save_custom_model(req: CustomModelSaveRequest):
    """Save a custom Replicate model to settings."""
    try:
        settings = read_settings()
        
        if "custom_replicate_models" not in settings:
            settings["custom_replicate_models"] = []
        
        # Check if model already exists
        existing_idx = next(
            (i for i, m in enumerate(settings["custom_replicate_models"]) if m["model_id"] == req.model_id),
            None
        )
        
        model_data = {
            "model_id": req.model_id,
            "friendly_name": req.friendly_name,
            "model_type": req.model_type,
            "schema": req.schema,
            "parameters": req.parameters,
            "added_at": int(time.time()),
        }
        
        if existing_idx is not None:
            # Update existing
            settings["custom_replicate_models"][existing_idx] = model_data
        else:
            # Add new
            settings["custom_replicate_models"].append(model_data)
        
        write_settings(settings)
        
        return {"status": "ok", "model": model_data}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.get("/settings/custom-models")
def api_list_custom_models():
    """List all custom Replicate models."""
    try:
        settings = read_settings()
        models = settings.get("custom_replicate_models", [])
        return {"status": "ok", "models": models}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.delete("/settings/custom-models/{model_id:path}")
def api_delete_custom_model(model_id: str):
    """Delete a custom Replicate model."""
    try:
        settings = read_settings()
        
        if "custom_replicate_models" not in settings:
            return {"status": "ok", "deleted": False}
        
        original_count = len(settings["custom_replicate_models"])
        settings["custom_replicate_models"] = [
            m for m in settings["custom_replicate_models"]
            if m["model_id"] != model_id
        ]
        
        deleted = len(settings["custom_replicate_models"]) < original_count
        
        write_settings(settings)
        
        return {"status": "ok", "deleted": deleted}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
