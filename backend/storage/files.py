from pathlib import Path
import json
from typing import Any, Dict, List, Optional
import time


def ensure_project(project_id: str) -> Path:
    base = Path("project_data") / project_id
    (base / "media").mkdir(parents=True, exist_ok=True)
    meta = base / "metadata.json"
    if not meta.exists():
        with open(meta, "w", encoding="utf-8") as f:
            json.dump({"project_id": project_id, "scenes": [], "shots": [], "characters": [], "media": []}, f, indent=2)
    return base


def read_metadata(project_id: str) -> Dict[str, Any]:
    base = ensure_project(project_id)
    with open(base / "metadata.json", "r", encoding="utf-8") as f:
        return json.load(f)


def write_metadata(project_id: str, data: Dict[str, Any]) -> None:
    base = ensure_project(project_id)
    with open(base / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# Scenes helpers (metadata.json structure per blueprint)
def list_scenes(project_id: str) -> List[Dict[str, Any]]:
    meta = read_metadata(project_id)
    return meta.get("scenes", [])


def get_scene(project_id: str, scene_id: str) -> Optional[Dict[str, Any]]:
    for scene in list_scenes(project_id):
        if scene.get("scene_id") == scene_id:
            return scene
    return None


def add_scene(project_id: str, scene_id: str, title: str) -> Dict[str, Any]:
    meta = read_metadata(project_id)
    scenes = meta.get("scenes", [])
    if any(s.get("scene_id") == scene_id for s in scenes):
        raise ValueError("Scene already exists")
    scene = {"scene_id": scene_id, "title": title, "shots": [], "audio_tracks": {}}
    scenes.append(scene)
    meta["scenes"] = scenes
    write_metadata(project_id, meta)
    return scene


def add_shot(project_id: str, scene_id: str, shot: Dict[str, Any]) -> Dict[str, Any]:
    meta = read_metadata(project_id)
    for s in meta.get("scenes", []):
        if s.get("scene_id") == scene_id:
            s.setdefault("shots", []).append(shot)
            write_metadata(project_id, meta)
            return shot
    raise ValueError("Scene not found")


def next_shot_id(scene_id: str) -> str:
    ts = int(time.time())
    return f"{scene_id}_shot_{ts}"


def ensure_scene_dirs(project_id: str, scene_id: str) -> Dict[str, Path]:
    base = ensure_project(project_id) / "scenes" / scene_id
    shots = base / "shots"
    frames = base / "frames"
    audio = base / "audio"
    for p in (shots, frames, audio):
        p.mkdir(parents=True, exist_ok=True)
    return {"base": base, "shots": shots, "frames": frames, "audio": audio}


# Media helpers
def list_media(project_id: str) -> List[Dict[str, Any]]:
    meta = read_metadata(project_id)
    return meta.get("media", [])


def add_media(project_id: str, item: Dict[str, Any]) -> Dict[str, Any]:
    meta = read_metadata(project_id)
    media = meta.get("media", [])
    media.append(item)
    meta["media"] = media
    write_metadata(project_id, meta)
    return item


def media_dirs(project_id: str) -> Dict[str, Path]:
    base = ensure_project(project_id) / "media"
    video = base / "video"
    audio = base / "audio"
    images = base / "images"
    for p in (video, audio, images):
        p.mkdir(parents=True, exist_ok=True)
    return {"video": video, "audio": audio, "images": images}



