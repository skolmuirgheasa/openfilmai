from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
from pathlib import Path
import json
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
)
from backend.ai.replicate_client import ReplicateClient
from backend.ai.vertex_client import VertexClient
from backend.storage.settings import read_settings, write_settings

app = FastAPI(title="OpenFilmAI Backend", version="0.1.0")

PROJECT_DATA_DIR = Path("project_data")
PROJECT_DATA_DIR.mkdir(parents=True, exist_ok=True)

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


@app.get("/health")
def health():
    return {"status": "ok"}


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
            client_v = VertexClient(credentials_path=cred, project_id=pid, location=loc, model=req.model or "veo-3.1-generate-preview", temp_bucket=temp_bucket)
            # If only one of start/end is provided, avoid Vertex interpolation error by sending neither.
            start_img = req.start_frame_path or req.reference_frame
            end_img = req.end_frame_path
            if bool(start_img) ^ bool(end_img):
                start_img = None
                end_img = None
            output_url = client_v.generate_video(
                prompt=req.prompt,
                first_frame_image=start_img,
                last_frame_image=end_img,
                reference_images=req.reference_images or None,
                duration=req.duration or 8,
                resolution=req.resolution or "1080p",
                aspect_ratio=req.aspect_ratio or "16:9",
            )
            model_used = req.model or "veo-3.1-generate-preview"
        else:
            # Default to Replicate
            client_r = ReplicateClient()
            model_used = req.model or "google/veo-3.1"
            output_url = client_r.generate_video(
                model=model_used,
                prompt=req.prompt,
                first_frame_image=req.reference_frame,
                duration=req.duration or 8,
                resolution=req.resolution or "1080p",
                aspect_ratio=req.aspect_ratio or "16:9",
                generate_audio=True,
            )
        # Download file
        import requests, os
        video_path = dirs["shots"] / f"{shot_id}.mp4"
        with requests.get(output_url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(video_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        # Extract frames
        from backend.video.ffmpeg import extract_first_last_frames
        first = dirs["frames"] / f"{shot_id}_first.png"
        last = dirs["frames"] / f"{shot_id}_last.png"
        extract_first_last_frames(str(video_path), str(first), str(last))
        # Update metadata
        rel_video = str(video_path.relative_to(Path.cwd()))
        # Static URL under /files maps to project_data dir
        rel_from_project = str(video_path.relative_to(PROJECT_DATA_DIR))
        video_url = f"/files/{rel_from_project}"
        rel_first = str(first.relative_to(PROJECT_DATA_DIR))
        rel_last = str(last.relative_to(PROJECT_DATA_DIR))
        shot_meta = {
            "shot_id": shot_id,
            "prompt": req.prompt,
            "model": model_used,
            "duration": req.duration,
            "file_path": rel_video,
            "first_frame_path": f"project_data/{rel_first}",
            "last_frame_path": f"project_data/{rel_last}",
            "continuity_source": None,
        }
        add_shot(req.project_id, req.scene_id, shot_meta)
        return {"status": "ok", "shot": shot_meta, "file_url": video_url}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


class VoiceRequest(BaseModel):
    project_id: str
    text: Optional[str] = None
    source_wav: Optional[str] = None
    voice_id: Optional[str] = None


@app.post("/ai/generate-voice")
def generate_voice(req: VoiceRequest):
    # Stub: ElevenLabs integration pending
    return {"status": "not_implemented", "detail": "ElevenLabs integration pending"}


class LipSyncRequest(BaseModel):
    project_id: str
    image_or_video_path: str
    audio_wav_path: str


@app.post("/ai/lip-sync")
def lip_sync(req: LipSyncRequest):
    # Stub: Wavespeed integration pending
    return {"status": "not_implemented", "detail": "Wavespeed integration pending"}


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
    meta = {
        "project_id": project_id,
        "scenes": [],
        "shots": [],
        "characters": [],
        "media": []
    }
    with open(proj_dir / "metadata.json", "w", encoding="utf-8") as f:
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
    # Ensure scene exists; if not, create it for robustness
    scene = get_scene(project_id, scene_id)
    if scene is None:
        # Fallback create with a simple title
        try:
            add_scene(project_id, scene_id, scene_id.replace("_", " ").title())
        except Exception:
            pass
    shot = add_shot(project_id, scene_id, body.model_dump(exclude_none=True))
    return {"status": "ok", "shot": shot}


# Media upload/list
@app.get("/storage/{project_id}/media")
def api_list_media(project_id: str):
    return {"media": list_media(project_id)}


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
