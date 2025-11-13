from pathlib import Path
import json
from typing import Dict, Any

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
                return json.load(f)
        except Exception:
            return {}
    return {}


def write_settings(data: Dict[str, Any]) -> None:
    GLOBAL_DIR.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


