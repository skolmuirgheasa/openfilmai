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


def clear_scene_shots(project_id: str, scene_id: str) -> int:
    """Clear all shots from a scene. Returns the number of shots removed."""
    meta = read_metadata(project_id)
    for s in meta.get("scenes", []):
        if s.get("scene_id") == scene_id:
            count = len(s.get("shots", []))
            s["shots"] = []
            write_metadata(project_id, meta)
            return count
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
def list_media(project_id: str, include_archived: bool = False) -> List[Dict[str, Any]]:
    meta = read_metadata(project_id)
    all_media = meta.get("media", [])
    if include_archived:
        return all_media
    # Filter out archived items by default
    return [m for m in all_media if not m.get("archived", False)]


def add_media(project_id: str, item: Dict[str, Any]) -> Dict[str, Any]:
    import time as time_module
    meta = read_metadata(project_id)
    media = meta.get("media", [])
    
    # Check for duplicate IDs and append (1), (2), etc. if needed
    original_id = item.get("id", "")
    if original_id:
        existing_ids = {m.get("id") for m in media}
        if original_id in existing_ids:
            # Find the next available number
            counter = 1
            base_name, ext = original_id.rsplit(".", 1) if "." in original_id else (original_id, "")
            while True:
                new_id = f"{base_name} ({counter}).{ext}" if ext else f"{base_name} ({counter})"
                if new_id not in existing_ids:
                    item["id"] = new_id
                    # Also update path and url if they exist
                    if "path" in item and original_id in item["path"]:
                        item["path"] = item["path"].replace(original_id, new_id)
                    if "url" in item and original_id in item["url"]:
                        item["url"] = item["url"].replace(original_id, new_id)
                    break
                counter += 1
    
    # Auto-tag source if not specified
    if "source" not in item:
        if "_first.png" in item.get("id", "") or "_last.png" in item.get("id", ""):
            item["source"] = "extracted"
        else:
            item["source"] = "generated"
    # Add timestamp for reliable sorting
    if "timestamp" not in item:
        item["timestamp"] = int(time_module.time())
    media.append(item)
    meta["media"] = media
    write_metadata(project_id, meta)
    return item


def archive_media(project_id: str, media_id: str, archived: bool = True) -> Dict[str, Any]:
    """Archive or unarchive a media item by ID. Returns dict with success status and optional error."""
    meta = read_metadata(project_id)

    # Check if this media is used as a reference image (character or scene-specific)
    if archived:  # Only check when archiving, not unarchiving
        # Check global character references
        characters = meta.get("characters", [])
        for char in characters:
            ref_images = char.get("reference_image_ids", [])
            if media_id in ref_images:
                return {
                    "success": False,
                    "error": f"Cannot archive: this image is used as a reference for character '{char.get('name', 'Unknown')}'. Remove it from the character first."
                }

        # Check scene-specific references (cast scene_reference_ids and master_image_ids)
        scenes = meta.get("scenes", [])
        for scene in scenes:
            # Check master images
            master_ids = scene.get("master_image_ids", [])
            if media_id in master_ids:
                return {
                    "success": False,
                    "error": f"Cannot archive: this image is used as a master reference for scene '{scene.get('title', scene.get('scene_id', 'Unknown'))}'. Remove it from the scene first."
                }

            # Check scene-specific character refs
            cast = scene.get("cast", [])
            for cast_member in cast:
                scene_refs = cast_member.get("scene_reference_ids", [])
                if media_id in scene_refs:
                    char_id = cast_member.get("character_id", "Unknown")
                    # Try to get character name
                    char = next((c for c in characters if c.get("character_id") == char_id), None)
                    char_name = char.get("name", char_id) if char else char_id
                    return {
                        "success": False,
                        "error": f"Cannot archive: this image is used as a scene-specific reference for '{char_name}' in scene '{scene.get('title', scene.get('scene_id', 'Unknown'))}'. Remove it from the scene cast first."
                    }
    
    media = meta.get("media", [])
    for item in media:
        if item.get("id") == media_id:
            item["archived"] = archived
            write_metadata(project_id, meta)
            return {"success": True}
    return {"success": False, "error": "Media item not found"}


def bulk_archive_media(project_id: str, media_ids: List[str], archived: bool = True) -> Dict[str, Any]:
    """Archive or unarchive multiple media items. Returns dict with count and skipped items."""
    meta = read_metadata(project_id)

    # Build set of media IDs that are protected (character refs + scene refs + master images)
    protected_ids = {}  # Maps ID to reason string
    if archived:  # Only check when archiving
        characters = meta.get("characters", [])
        scenes = meta.get("scenes", [])

        # Global character references
        for char in characters:
            ref_images = char.get("reference_image_ids", [])
            for ref_id in ref_images:
                protected_ids[ref_id] = f"character ref: {char.get('name', 'Unknown')}"

        # Scene-specific references
        for scene in scenes:
            scene_name = scene.get("title", scene.get("scene_id", "Unknown"))

            # Master images
            for master_id in scene.get("master_image_ids", []):
                protected_ids[master_id] = f"scene master: {scene_name}"

            # Cast scene refs
            for cast_member in scene.get("cast", []):
                char_id = cast_member.get("character_id", "Unknown")
                char = next((c for c in characters if c.get("character_id") == char_id), None)
                char_name = char.get("name", char_id) if char else char_id
                for ref_id in cast_member.get("scene_reference_ids", []):
                    protected_ids[ref_id] = f"scene ref: {char_name} in {scene_name}"

    media = meta.get("media", [])
    count = 0
    skipped = []

    for item in media:
        item_id = item.get("id")
        if item_id in media_ids:
            if item_id in protected_ids:
                skipped.append({"id": item_id, "reason": protected_ids[item_id]})
            else:
                item["archived"] = archived
                count += 1

    if count > 0:
        write_metadata(project_id, meta)

    return {"count": count, "skipped": skipped}


def media_dirs(project_id: str) -> Dict[str, Path]:
    base = ensure_project(project_id) / "media"
    video = base / "video"
    audio = base / "audio"
    images = base / "images"
    for p in (video, audio, images):
        p.mkdir(parents=True, exist_ok=True)
    return {"video": video, "audio": audio, "images": images}


# Character helpers
def list_characters(project_id: str) -> List[Dict[str, Any]]:
    meta = read_metadata(project_id)
    return meta.get("characters", [])


def upsert_character(project_id: str, character: Dict[str, Any]) -> Dict[str, Any]:
    meta = read_metadata(project_id)
    chars = meta.get("characters", [])
    # replace if exists
    for idx, c in enumerate(chars):
        if c.get("character_id") == character.get("character_id"):
            chars[idx] = character
            break
    else:
        chars.append(character)
    meta["characters"] = chars
    write_metadata(project_id, meta)
    return character


def get_character(project_id: str, character_id: str) -> Optional[Dict[str, Any]]:
    for c in list_characters(project_id):
        if c.get("character_id") == character_id:
            return c
    return None


def delete_character(project_id: str, character_id: str) -> bool:
    meta = read_metadata(project_id)
    chars = meta.get("characters", [])
    new_chars = [c for c in chars if c.get("character_id") != character_id]
    if len(new_chars) == len(chars):
        return False
    meta["characters"] = new_chars
    write_metadata(project_id, meta)
    return True



