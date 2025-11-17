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
from backend.storage.files import (
    list_scenes,
    add_scene,
    get_scene,
    add_shot,
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
)
from backend.ai.replicate_client import ReplicateClient
from backend.ai.vertex_client import VertexClient
from ai_porting_bundle.providers.elevenlabs import ElevenLabsProvider
from ai_porting_bundle.providers.wavespeed import WaveSpeedProvider
from backend.storage.settings import read_settings, write_settings

app = FastAPI(title="OpenFilmAI Backend", version="0.1.0")

PROJECT_DATA_DIR = Path("project_data")
PROJECT_DATA_DIR.mkdir(parents=True, exist_ok=True)

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

# Serve project_data files (videos, frames) under /files/*
app.mount("/files", StaticFiles(directory=str(PROJECT_DATA_DIR)), name="files")
# CORS for Electron dev served via Vite
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.api_route("/health", methods=["GET", "HEAD"])
def health():
    return {"status": "ok"}


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
    provider: Optional[str] = "replicate"  # replicate | vertex
    model: Optional[str] = None
    reference_frame: Optional[str] = None  # path to frame image
    character_id: Optional[str] = None
    duration: Optional[int] = 8
    resolution: Optional[str] = "1080p"
    aspect_ratio: Optional[str] = "16:9"
    start_frame_path: Optional[str] = None
    end_frame_path: Optional[str] = None
    reference_images: Optional[List[str]] = None
    generate_audio: Optional[bool] = False


@app.post("/ai/generate-shot")
def generate_shot(req: ShotGenerateRequest):
    # Ensure directories
    dirs = ensure_scene_dirs(req.project_id, req.scene_id)
    shot_id = next_shot_id(req.scene_id)
    try:
        if (req.provider or "").lower() == "vertex":
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
                ref_imgs = [str(Path.cwd() / r) if not Path(r).is_absolute() else r for r in ref_imgs]
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
            model_used = req.model or "google/veo-3.1"
            output_url = client_r.generate_video(
                model=model_used,
                prompt=req.prompt,
                first_frame_image=req.reference_frame,
                duration=req.duration or 8,
                resolution=req.resolution or "1080p",
                aspect_ratio=req.aspect_ratio or "16:9",
                generate_audio=bool(req.generate_audio),
            )
        # Download file
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


@app.post("/ai/voice/tts")
def voice_tts(req: VoiceTTSRequest):
    s = read_settings()
    key = s.get("elevenlabs_api_key")
    if not key:
        return {"status": "error", "detail": "ElevenLabs API key not set in Settings"}
    prov = ElevenLabsProvider(api_key=key)
    try:
        out = prov.generate(text=req.text, voice_id=req.voice_id, model_id=req.model_id or None, output_format="mp3")
        # Save to project audio folder and index
        proj_audio = ensure_scene_dirs(req.project_id, "tmp")["audio"].parent.parent / "media" / "audio"
        proj_audio.mkdir(parents=True, exist_ok=True)
        stub = f"voice_{int(__import__('time').time())}"
        filename = _safe_filename(req.filename, stub, ".mp3")
        target = proj_audio / filename
        Path(out).rename(target)
        rel = str(target.relative_to(PROJECT_DATA_DIR))
        item = {"id": target.name, "type": "audio", "path": f"project_data/{rel}", "url": f"/files/{rel}"}
        add_media(req.project_id, item)
        return {"status": "ok", "file_url": f"/files/{rel}", "item": item}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


class VoiceV2VRequest(BaseModel):
    project_id: str
    source_wav: str
    voice_id: Optional[str] = None
    model_id: Optional[str] = "eleven_multilingual_sts_v2"
    filename: Optional[str] = None


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
        out = prov.speech_to_speech(audio_path=str(src), voice_id=req.voice_id or None, model_id=req.model_id or "eleven_multilingual_sts_v2", output_format="mp3")
        proj_audio = ensure_scene_dirs(req.project_id, "tmp")["audio"].parent.parent / "media" / "audio"
        proj_audio.mkdir(parents=True, exist_ok=True)
        stub = f"voice_v2v_{int(__import__('time').time())}"
        target = proj_audio / _safe_filename(req.filename, stub, ".mp3")
        Path(out).rename(target)
        rel = str(target.relative_to(PROJECT_DATA_DIR))
        item = {"id": target.name, "type": "audio", "path": f"project_data/{rel}", "url": f"/files/{rel}"}
        add_media(req.project_id, item)
        return {"status": "ok", "file_url": f"/files/{rel}", "item": item}
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


class SceneUpdate(BaseModel):
    title: Optional[str] = None
    shot_order: Optional[List[str]] = None


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
    prompt: Optional[str] = None
    model: Optional[str] = None
    duration: Optional[int] = None
    file_path: Optional[str] = None
    first_frame_path: Optional[str] = None
    last_frame_path: Optional[str] = None
    continuity_source: Optional[str] = None
    start_offset: Optional[float] = 0.0
    end_offset: Optional[float] = 0.0
    volume: Optional[float] = 1.0


@app.post("/storage/{project_id}/scenes/{scene_id}/shots")
def api_add_shot(project_id: str, scene_id: str, body: ShotCreate):
    from backend.video.ffmpeg import extract_first_last_frames
    
    # Ensure scene exists; if not, create it for robustness
    scene = get_scene(project_id, scene_id)
    if scene is None:
        # Fallback create with a simple title
        try:
            add_scene(project_id, scene_id, scene_id.replace("_", " ").title())
        except Exception:
            pass
    
    shot_data = body.model_dump(exclude_none=True)
    
    # If this is a video shot without frames, extract them
    if shot_data.get('file_path') and not shot_data.get('first_frame_path'):
        try:
            file_path = shot_data['file_path']
            # Resolve to absolute path
            if file_path.startswith('project_data/'):
                abs_path = PROJECT_DATA_DIR / file_path.replace('project_data/', '')
            else:
                abs_path = Path(file_path)
            
            if abs_path.exists() and abs_path.suffix.lower() in ['.mp4', '.mov', '.avi', '.mkv']:
                # Extract frames to scene frames directory
                dirs = ensure_scene_dirs(project_id, scene_id)
                shot_id = shot_data.get('shot_id', f"shot_{int(__import__('time').time())}")
                first_frame = dirs["frames"] / f"{shot_id}_first.png"
                last_frame = dirs["frames"] / f"{shot_id}_last.png"
                
                extract_first_last_frames(str(abs_path), str(first_frame), str(last_frame))
                
                # Add frame paths to shot data
                rel_first = str(first_frame.relative_to(PROJECT_DATA_DIR))
                rel_last = str(last_frame.relative_to(PROJECT_DATA_DIR))
                shot_data['first_frame_path'] = f"project_data/{rel_first}"
                shot_data['last_frame_path'] = f"project_data/{rel_last}"
        except Exception as e:
            logger.warning(f"Failed to extract frames for imported shot: {e}")
    
    shot = add_shot(project_id, scene_id, shot_data)
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
    return {"media": items}


@app.post("/storage/{project_id}/media")
async def api_upload_media(project_id: str, file: UploadFile = File(...)):
    dirs = media_dirs(project_id)
    filename = file.filename or "upload.bin"
    lower = filename.lower()
    mtype = "video" if lower.endswith((".mp4", ".mov", ".m4v")) else "audio" if lower.endswith((".wav", ".mp3", ".aac", ".flac")) else "images" if lower.endswith((".png", ".jpg", ".jpeg", ".webp")) else "video"
    target_dir = dirs[mtype]
    safe_name = f"{int(__import__('time').time())}_{filename.replace('/', '_')}"
    target_path = target_dir / safe_name
    with open(target_path, "wb") as out:
        out.write(await file.read())
    rel_from_project = str(target_path.relative_to(PROJECT_DATA_DIR))
    file_url = f"/files/{rel_from_project}"
    item = {
        "id": safe_name,
        "type": mtype[:-1] if mtype.endswith("s") else mtype,
        "path": f"project_data/{rel_from_project}",
        "url": file_url,
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
    prompt: Optional[str] = None
    duration: Optional[float] = None
    start_offset: Optional[float] = None
    end_offset: Optional[float] = None
    volume: Optional[float] = None
    file_path: Optional[str] = None


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
                    for k, v in body.model_dump(exclude_none=True).items():
                        sh[k] = v
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


@app.post("/storage/{project_id}/media/scan")
def api_scan_media(project_id: str):
    """
    Scan project_data/<project_id>/media/{video,audio,images} for files that are not
    present in metadata and add them. Returns number of new items indexed.
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

    existing = read_metadata(project_id).get("media", [])
    existing_ids = set(item.get("id") for item in existing)

    new_items = []

    def add_item(file_path: Path, kind: str):
        nonlocal new_items, existing_ids, existing
        file_id = file_path.name
        if file_id in existing_ids:
            return
        rel_from_project = str(file_path.relative_to(PROJECT_DATA_DIR))
        url = f"/files/{rel_from_project}"
        item = {
            "id": file_id,
            "type": kind,
            "path": f"project_data/{rel_from_project}",
            "url": url,
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

    # Persist
    meta = read_metadata(project_id)
    meta["media"] = existing
    write_metadata(project_id, meta)
    return {"status": "ok", "indexed": len(new_items), "items": new_items}

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


@app.post("/settings")
def api_set_settings(body: SettingsBody):
    current = read_settings()
    current.update({k: v for k, v in body.model_dump().items() if v is not None})
    write_settings(current)
    return {"status": "ok"}


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
