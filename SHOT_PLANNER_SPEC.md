# OpenFilmAI: Scene-Based Shot Planner Specification

## Overview
Transform the timeline from a video editor into a **Cinematic Shot Planner** where:
1. **Scene** = Global context (setting, cast, appearances)
2. **Timeline** = Detailed shot-by-shot planning
3. **AI Assistant** = Cinematographer that helps plan shots
4. **Generation** = Image → Audio → Video per shot with automatic consistency

---

## Phase 1: Data Model & AI Cinematographer

### 1.1 Extend Scene Model

**File:** `backend/main.py` (Scene class around line 90)

Add these fields to the Scene model:
```python
class Scene(BaseModel):
    scene_id: str
    title: str
    # NEW FIELDS:
    description: Optional[str] = None           # Scene description/context
    location_notes: Optional[str] = None        # Location details
    master_image_ids: List[str] = []            # Reference images for the setting
    cast: List[SceneCast] = []                  # Characters in this scene
    shots: List[Shot] = []
    audio_tracks: Dict[str, Any] = {}

class SceneCast(BaseModel):
    """Character appearance in a specific scene"""
    character_id: str                           # Links to Character
    appearance_notes: Optional[str] = None      # "Muddy clothes", "Formal wear"
    scene_reference_ids: List[str] = []         # Scene-specific ref images (overrides character defaults)
```

### 1.2 Extend Shot Model

**File:** `backend/main.py` (Shot class around line 70)

Add planning fields:
```python
class Shot(BaseModel):
    shot_id: str
    # PLANNING FIELDS (new):
    shot_number: Optional[int] = None           # Order in shot list
    camera_angle: Optional[str] = None          # "Wide", "Medium", "Close-up", "OTS", etc.
    subject: Optional[str] = None               # Who/what is the focus
    action: Optional[str] = None                # What happens in this shot
    dialogue: Optional[str] = None              # Any dialogue in this shot
    status: str = "planned"                     # "planned" | "image_ready" | "audio_ready" | "video_ready"

    # IMAGE GENERATION:
    prompt: Optional[str] = None
    start_frame_path: Optional[str] = None      # Generated start frame image

    # AUDIO:
    audio_path: Optional[str] = None            # Voice/dialogue audio
    audio_character_id: Optional[str] = None    # Who's speaking

    # VIDEO GENERATION:
    model: Optional[str] = None
    duration: Optional[float] = None
    file_path: Optional[str] = None             # Final video
    first_frame_path: Optional[str] = None
    last_frame_path: Optional[str] = None

    # Existing fields...
    continuity_source: Optional[str] = None
    start_offset: float = 0.0
    end_offset: float = 0.0
    volume: float = 1.0
```

### 1.3 Add LLM API Key Settings

**File:** `backend/main.py` (settings endpoints)

Add to settings schema:
```python
# In POST /settings and GET /settings:
"openai_api_key": str        # For GPT-4
"anthropic_api_key": str     # For Claude
"llm_provider": str          # "openai" | "anthropic" (user preference)
```

### 1.4 Create Cinematographer Agent

**New file:** `backend/ai/cinematographer.py`

```python
"""
AI Cinematographer - Generates shot lists from scene descriptions
"""
import os
import json
from typing import Optional
import requests

SHOT_PLANNING_PROMPT = '''You are an expert cinematographer and film director.

Given a scene description and/or dialogue, create a detailed shot list that:
1. Provides complete editorial coverage (establishing, wide, medium, close-up, reaction shots)
2. Uses varied camera angles for visual interest
3. Ensures smooth visual storytelling flow
4. Captures key emotional moments with appropriate framing

For each shot, specify:
- shot_number: Sequential number
- camera_angle: One of "Extreme Wide", "Wide", "Medium Wide", "Medium", "Medium Close-up", "Close-up", "Extreme Close-up", "Over-the-shoulder", "POV", "Two-shot", "Insert"
- subject: Who or what is the focus
- action: What happens in this shot
- dialogue: Any lines spoken (if applicable)
- prompt_suggestion: A detailed image generation prompt for this shot

Return ONLY valid JSON array. Example:
[
  {
    "shot_number": 1,
    "camera_angle": "Wide",
    "subject": "Exterior warehouse",
    "action": "Establishing shot of the abandoned warehouse at dusk",
    "dialogue": null,
    "prompt_suggestion": "Cinematic wide shot of an abandoned industrial warehouse at golden hour, dramatic lighting, film grain, anamorphic lens flare"
  }
]
'''

def generate_shot_list(
    scene_description: str,
    dialogue: Optional[str] = None,
    characters: Optional[list] = None,
    location_notes: Optional[str] = None,
    provider: str = "anthropic",
    api_key: Optional[str] = None
) -> list:
    """
    Generate a shot list from scene description using LLM.

    Returns list of shot dictionaries.
    """

    # Build context
    context_parts = []
    if scene_description:
        context_parts.append(f"SCENE DESCRIPTION:\n{scene_description}")
    if dialogue:
        context_parts.append(f"DIALOGUE:\n{dialogue}")
    if characters:
        char_list = ", ".join([c.get("name", "Unknown") for c in characters])
        context_parts.append(f"CHARACTERS IN SCENE: {char_list}")
    if location_notes:
        context_parts.append(f"LOCATION NOTES:\n{location_notes}")

    user_message = "\n\n".join(context_parts)
    user_message += "\n\nCreate a comprehensive shot list for this scene."

    if provider == "anthropic":
        return _call_anthropic(user_message, api_key)
    else:
        return _call_openai(user_message, api_key)


def _call_anthropic(user_message: str, api_key: str) -> list:
    """Call Claude API"""
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        },
        json={
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 4096,
            "system": SHOT_PLANNING_PROMPT,
            "messages": [{"role": "user", "content": user_message}]
        }
    )
    response.raise_for_status()
    content = response.json()["content"][0]["text"]

    # Extract JSON from response
    return _parse_shot_list(content)


def _call_openai(user_message: str, api_key: str) -> list:
    """Call OpenAI API"""
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": SHOT_PLANNING_PROMPT},
                {"role": "user", "content": user_message}
            ],
            "response_format": {"type": "json_object"}
        }
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]

    return _parse_shot_list(content)


def _parse_shot_list(content: str) -> list:
    """Parse LLM response into shot list"""
    # Try to find JSON array in response
    content = content.strip()

    # If wrapped in markdown code block
    if "```" in content:
        start = content.find("```")
        end = content.rfind("```")
        if start != end:
            content = content[start:end]
            # Remove ```json or ``` prefix
            content = content.split("\n", 1)[-1] if "\n" in content else content

    # Find array boundaries
    start_idx = content.find("[")
    end_idx = content.rfind("]") + 1

    if start_idx != -1 and end_idx > start_idx:
        json_str = content[start_idx:end_idx]
        return json.loads(json_str)

    # Try parsing whole content as JSON
    return json.loads(content)
```

### 1.5 Add Cinematographer Endpoint

**File:** `backend/main.py`

```python
from ai.cinematographer import generate_shot_list

class ShotPlanRequest(BaseModel):
    scene_description: str
    dialogue: Optional[str] = None
    character_names: Optional[List[str]] = None
    location_notes: Optional[str] = None

@app.post("/ai/plan-shots")
async def plan_shots(request: ShotPlanRequest):
    """Generate shot list using AI cinematographer"""
    settings = load_settings()

    provider = settings.get("llm_provider", "anthropic")
    api_key = settings.get(f"{provider}_api_key") or settings.get("anthropic_api_key")

    if not api_key:
        raise HTTPException(400, f"No API key configured for {provider}")

    try:
        shots = generate_shot_list(
            scene_description=request.scene_description,
            dialogue=request.dialogue,
            characters=[{"name": n} for n in (request.character_names or [])],
            location_notes=request.location_notes,
            provider=provider,
            api_key=api_key
        )
        return {"shots": shots}
    except Exception as e:
        raise HTTPException(500, f"Shot planning failed: {str(e)}")
```

---

## Phase 2: UI Refactor - The Shot Planner

### 2.1 Scene Context Panel

Add a collapsible panel above the timeline showing:
- Scene title and description (editable)
- Master scene images (drag-drop upload area)
- Cast list with character cards showing:
  - Character name
  - Scene-specific appearance notes
  - Thumbnail of reference image

### 2.2 Shot Cards (Replace Timeline)

Each shot becomes a card with:

```
┌─────────────────────────────────────────────────────┐
│ [1] Close-up                           [✓ Planned] │
├─────────────────────────────────────────────────────┤
│ ┌──────────┐  Subject: Jonas                        │
│ │          │  Action: Looks up from newspaper       │
│ │  IMAGE   │  Dialogue: "What did you say?"         │
│ │          │                                        │
│ └──────────┘  ─────────────────────────────────────│
│               Prompt: [editable text area]          │
├─────────────────────────────────────────────────────┤
│ [🖼 Gen Image] [🎤 Gen Audio] [🎬 Gen Video] [🗑]    │
└─────────────────────────────────────────────────────┘
```

Status indicator colors:
- Gray: Planned (no assets)
- Blue: Image Ready
- Yellow: Audio Ready
- Green: Video Ready

### 2.3 AI Chat Interface

Add a slide-out panel (right side) with:
- Text input for scene description/dialogue
- "Generate Shot List" button
- Chat history showing:
  - User inputs
  - AI responses (shot list previews)
- "Apply to Timeline" button to create shot cards from AI suggestions

### 2.4 Scene Settings Panel

In the left sidebar or as a modal:
- Scene description textarea
- Location notes textarea
- Master images grid (from media library)
- Cast assignment:
  - Select characters to cast
  - Per-character appearance notes
  - Per-character scene reference images

---

## Phase 3: Generation Pipeline & Consistency

### 3.1 Consistency Logic for Image Generation

When generating a start frame for a shot:

1. **Collect scene context:**
   - Scene master images → Use as style reference
   - Scene description → Append to prompt

2. **Collect character context:**
   - If shot.subject matches a cast member:
     - Get character's scene-specific refs OR default refs
     - Include in generation as reference images

3. **Build final prompt:**
   ```
   {shot.prompt}

   Scene context: {scene.description}
   Character: {character.name} - {character.style_tokens}
   Camera: {shot.camera_angle}
   ```

4. **Call generation with refs:**
   - Pass master_image as style/IP-adapter ref
   - Pass character refs as subject refs

### 3.2 Asset Chaining

Each generation button should:

**"Generate Image" button:**
- Opens image generation dialog
- Pre-fills prompt from shot.prompt_suggestion or shot.action
- Auto-selects scene master image as reference
- Auto-selects character refs if subject matches cast
- On success: Updates shot.start_frame_path, shot.status = "image_ready"

**"Generate Audio" button:**
- Opens voice dialog (TTS or V2V)
- Pre-fills text from shot.dialogue
- Pre-selects character voice if shot.audio_character_id set
- On success: Updates shot.audio_path, shot.status = "audio_ready"

**"Generate Video" button:**
- Opens video generation dialog
- Auto-selects shot.start_frame_path as start frame
- Pre-fills prompt from shot context
- On success: Updates shot.file_path, shot.status = "video_ready"

**"Lip Sync" button (alternative to video):**
- Opens lip sync dialog
- Auto-selects shot.start_frame_path as image
- Auto-selects shot.audio_path as audio
- On success: Updates shot.file_path, shot.status = "video_ready"

### 3.3 Export Function

**New endpoint:** `POST /render/export-scene`

```python
@app.post("/render/export-scene/{project_id}/{scene_id}")
async def export_scene(project_id: str, scene_id: str):
    """Export all video-ready shots as numbered files"""
    metadata = load_metadata(project_id)
    scene = next((s for s in metadata["scenes"] if s["scene_id"] == scene_id), None)

    if not scene:
        raise HTTPException(404, "Scene not found")

    export_dir = f"project_data/{project_id}/exports/{scene_id}"
    os.makedirs(export_dir, exist_ok=True)

    exported = []
    for i, shot in enumerate(scene["shots"]):
        if shot.get("file_path") and shot.get("status") == "video_ready":
            src = shot["file_path"]
            dst = f"{export_dir}/{str(i+1).zfill(3)}.mp4"
            shutil.copy(src, dst)
            exported.append(dst)

    return {
        "export_dir": export_dir,
        "files": exported,
        "count": len(exported)
    }
```

---

## Implementation Order

### Step 1: Backend Data Model Changes
1. Update Scene and Shot models in `backend/main.py`
2. Add SceneCast model
3. Update metadata save/load to handle new fields
4. Add migration for existing projects (set defaults)

### Step 2: Cinematographer Agent
1. Create `backend/ai/cinematographer.py`
2. Add LLM API keys to settings
3. Add `/ai/plan-shots` endpoint
4. Test with sample scene descriptions

### Step 3: UI - Scene Context
1. Add scene description/notes fields to scene detail
2. Add master image selection
3. Add cast assignment UI

### Step 4: UI - Shot Cards
1. Refactor timeline to use shot cards
2. Add shot planning fields (camera, subject, action, dialogue)
3. Add per-shot status indicators
4. Add generation buttons per card

### Step 5: UI - AI Chat
1. Add chat panel component
2. Wire up to `/ai/plan-shots` endpoint
3. Add "Apply to Timeline" functionality
4. Add editing of AI suggestions before applying

### Step 6: Generation Integration
1. Update image generation to inject scene/character refs
2. Update audio generation to pre-select character voice
3. Update video generation to use shot's start frame
4. Add lip sync shortcut button

### Step 7: Export
1. Add export endpoint
2. Add "Export Scene" button in UI
3. Show export progress and result

---

## File Changes Summary

**Backend:**
- `backend/main.py` - Update models, add endpoints
- `backend/ai/cinematographer.py` - NEW: LLM shot planning

**Frontend:**
- `frontend/src/App.tsx` - Major UI refactor:
  - Scene context panel
  - Shot card components
  - AI chat panel
  - Updated generation flows

**Settings:**
- Add `openai_api_key` and `anthropic_api_key` to settings
