# OpenFilm AI

A professional scene orchestrator and shot planner for AI filmmaking. Design complete scenes with an AI cinematographer, lock character appearances per scene, and generate shot lists with automatic visual consistency.

## Core Workflow

```
Global Characters → Scene Setup → Shot Planning → Generation
```

### 1. Global Characters
Define your cast once. Upload reference images that establish each character's identity across your entire project.

### 2. Scene Setup
For each scene, the AI cinematographer analyzes your description and proposes:
- **Scene setting** — location, time of day, lighting, atmosphere
- **Character appearances** — wardrobe, hair, makeup specific to this scene
- **Visual style** — color palette, camera style, cinematography notes

Generate and approve a **master scene image** that locks the visual foundation. Then generate **scene-specific character references** using both the global character refs and the scene setting for consistency.

### 3. Shot Planning
The AI generates a complete shot list with:
- Camera angles and framing
- Subject and action descriptions
- Dialogue assignments
- Pre-written image generation prompts

Each shot inherits:
- Scene master images (setting consistency)
- Scene character references (wardrobe/appearance consistency)
- Previous shot frames (continuity between cuts)

### 4. Generation
Generate images, audio, and video per shot. The system automatically injects the appropriate references at each step.

---

## Architecture

**Scene Hierarchy:**
```
Project
└── Characters (global identity refs)
└── Scenes
    ├── Scene Settings (master images, visual style)
    ├── Scene Cast (scene-specific character refs)
    └── Shots (inherit all above)
```

**Progressive Consistency:**
- Wide/establishing shots serve as anchors
- Each shot can reference the previous shot's last frame
- Scene refs propagate to all shots automatically

---

## Supported Providers

| Provider | Capability |
|----------|------------|
| **Replicate** | Video (Veo 3.1), Images (Seedream-4) |
| **Google Vertex AI** | Video (Veo 3.1) with GCS storage |
| **Anthropic / OpenAI** | AI cinematographer (shot planning) |
| **ElevenLabs** | Text-to-speech, voice conversion |
| **WaveSpeed** | Lip-sync (image + audio → video) |

---

## Setup

### Requirements
- Node.js 18+
- Python 3.9+
- ffmpeg with ffprobe

### Install

```bash
git clone <repository-url>
cd openfilmai

# Node dependencies
npm install

# Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Run

```bash
npm run dev
```

Starts backend (`:8000`), frontend (`:5173`), and Electron.

### API Keys

Configure in Settings (gear icon):

- **Replicate API Token** — [replicate.com](https://replicate.com)
- **Anthropic API Key** — [anthropic.com](https://anthropic.com) (for AI cinematographer)
- **OpenAI API Key** — [openai.com](https://openai.com) (alternative for AI cinematographer)
- **ElevenLabs API Key** — [elevenlabs.io](https://elevenlabs.io)
- **WaveSpeed API Key** — [wavespeed.ai](https://wavespeed.ai)

**Vertex AI (optional):**
1. Create GCP project, enable Vertex AI + Cloud Storage APIs
2. Create service account with "Vertex AI User" and "Storage Admin" roles
3. Download JSON key file
4. Configure path, project ID, location, and bucket in Settings

---

## Project Structure

```
openfilmai/
├── frontend/           # React + TypeScript + Tailwind
│   └── src/App.tsx     # Main application
├── backend/
│   ├── main.py         # FastAPI server
│   ├── ai/
│   │   └── cinematographer.py  # Shot planning AI
│   └── video/          # FFmpeg processing
├── project_data/       # User projects (created at runtime)
└── electron.js         # Desktop wrapper
```

---

## Usage

### Scene Setup Workflow

1. **Create scene** — Add title and description
2. **AI Assist** — Click to analyze scene and auto-fill:
   - Visual style, color palette, camera approach
   - Character appearances and wardrobe for this scene
   - Establishing shot prompts
3. **Generate scene image** — Create master reference, accept/reject until satisfied
4. **Generate character refs** — For each cast member, generate scene-locked appearance using global refs + scene setting
5. **Plan shots** — Open AI Shot Planner, auto-generates shot list from scene context

### Shot Generation

Each shot card shows:
- Shot number, camera angle, subject, action
- Characters in frame
- Dialogue (if any)
- Generation buttons: Image → Audio → Video/Lip-sync

Clicking "Gen Image" auto-injects:
- Scene master images
- Scene character references (or global refs as fallback)
- Wide shot references for consistency
- Previous shot's last frame for continuity

### Transitions

Click the arrow between clips to smooth transitions using optical flow interpolation.

---

## Extending

### Adding Models

Add Replicate model IDs directly to the frontend dropdown — the client is generic.

For custom providers, implement a client in `backend/ai/` following `replicate_client.py` as reference.

### Data Model

**Scene:**
```python
scene_id, title, description, location_notes
master_image_ids: List[str]  # Scene setting refs
cast: List[SceneCast]        # Characters + scene appearances
shots: List[Shot]
visual_style, color_palette, camera_style, tone_notes
```

**SceneCast:**
```python
character_id: str
appearance_notes: str         # AI-generated wardrobe/look
scene_reference_ids: List[str]  # Scene-locked character refs
```

**Shot:**
```python
shot_id, shot_number, camera_angle, subject, action, dialogue
characters_in_shot: List[str]
prompt: str                   # Image generation prompt
start_frame_path, audio_path, file_path
status: "planned" | "image_ready" | "audio_ready" | "video_ready"
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Backend won't start | Activate venv, check port 8000, verify Python 3.9+ |
| ffmpeg errors | Install ffmpeg and ffprobe, verify in PATH |
| API failures | Check keys in Settings, verify account credits |
| Vertex auth errors | Verify service account JSON path and permissions |
| Port in use | `kill -9 $(lsof -t -i:8000)` or `:5173` |

---

## License

TBD

---

Built for filmmakers who need systematic control over AI-generated visual consistency.
