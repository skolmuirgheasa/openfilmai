from pathlib import Path
import json
from typing import Dict, Any
import os

# Global settings path (user home) to persist across projects
GLOBAL_DIR = Path.home() / ".openfilmai"
SETTINGS_PATH = GLOBAL_DIR / "settings.json"

# Backward-compat migration path (old location inside repo)
LEGACY_SETTINGS_PATH = Path("project_data") / "_settings.json"


def _ensure_migrated():
    """Migrate legacy project-local settings to global if present."""
    try:
        GLOBAL_DIR.mkdir(parents=True, exist_ok=True)
        if LEGACY_SETTINGS_PATH.exists() and not SETTINGS_PATH.exists():
            with open(LEGACY_SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
    except Exception:
        # Best-effort migration
        pass


def read_settings() -> Dict[str, Any]:
    _ensure_migrated()
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    else:
        data = {}
    # Merge environment fallbacks so the UI doesn't appear empty if user has env vars set
    env_overrides = {
        "replicate_api_token": os.environ.get("REPLICATE_API_TOKEN") or os.environ.get("REPLICATE_API_KEY"),
        "elevenlabs_api_key": os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("XI_API_KEY"),
        "wavespeed_api_key": os.environ.get("WAVESPEED_API_KEY"),
        "vertex_service_account_path": os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"),
        "vertex_project_id": os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCLOUD_PROJECT"),
        "vertex_location": os.environ.get("VERTEX_LOCATION"),
        "vertex_temp_bucket": os.environ.get("VERTEX_TEMP_BUCKET"),
    }
    for k, v in env_overrides.items():
        if v and not data.get(k):
            data[k] = v
    return data


def write_settings(data: Dict[str, Any]) -> None:
    GLOBAL_DIR.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


