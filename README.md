# OpenFilm AI

<div align="center">

### Agentic Shot Orchestration for AI Filmmaking

*A state-management engine for video generation that treats film production as a graph of inherited context, not a single prompt.*

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![React 18](https://img.shields.io/badge/react-18-61dafb.svg)](https://reactjs.org/)
[![Electron](https://img.shields.io/badge/electron-desktop-47848f.svg)](https://www.electronjs.org/)

</div>

---

![OpenFilm Interface](readme-media/timeline-shot-organization.png)

> **The Shot Graph:** A node-based editor where every shot inherits state (lighting, wardrobe, style) from the scene container.

---

## Demo


https://github.com/user-attachments/assets/e5fe4140-4180-4440-a33c-5031f991e967


**12 shots | 01:54 runtime | Consistent characters, setting, voices**

*Generated as a graph of discrete shots—not a single long-context prompt. Character identity remains stable across lighting setups, camera angles, and scene transitions.*

---

## The Problem OpenFilmAI Solves

The generative video industry optimizes for **Long Context Tuning (LCT)**—expanding context windows to generate 60+ seconds in a single pass. This approach has fundamental problems:

| Issue | Description |
|-------|-------------|
| **Latent Drift** | Character faces "melt" as the latent representation degrades over time |
| **Editorial Rigidity** | Can't edit pacing without regenerating the entire sequence |
| **Compute Inefficiency** | Exponentially more resources for longer sequences |

### The OpenFilm Solution: Hierarchical State Injection

| LCT Approach | OpenFilm Approach |
|--------------|-------------------|
| Expand context window | Inject state per-shot |
| Fight latent drift | Eliminate it structurally |
| Generate entire scenes | Generate optimal 4-8s clips |
| Pixels remember pixels | State objects remember state |

**How it works:**

1. **State Management** — The "Scene" is a state object holding immutable variables (lighting, character refs, visual style)
2. **Short-Shot Inference** — Generate 4-8s clips where diffusion models perform best
3. **Inheritance** — Each shot inherits the *State* of the scene, not just the pixels of the previous frame

**Result**: Infinite runtime with zero identity drift.

---

## Platform Walkthrough

### Scene State Configuration

Lock lighting, color palette, and atmosphere before generation. All shots inherit this state.

![Scene Setup](readme-media/ai-assisted-scene-planning.png)

### Hierarchical Character Casting

Define **Global Identity** (face), map to **Scene Appearance** (wardrobe). The system injects the correct combination into every prompt.

![Character Mapping](readme-media/scene-level-casting-and-character-adaptation.png)

### Agentic Shot Planning

The AI Cinematographer generates coverage plans based on film theory—Wide, Over-the-Shoulder, Close-up.

![Shot Planning](readme-media/ai-script-to-shot-planning.png)

### Context-Aware Continuity

The AI Director analyzes the previous shot's video to extract character positions and lighting for the next shot.

![Continuity Analysis](readme-media/adaptive-context-based-shot-continuity.png)

---

## Architecture

```mermaid
graph TD
    subgraph "Global State"
        A[Cast Registry] -->|Character Identity| B
        A -->|Voice Profiles| V[TTS Engine]
    end

    subgraph "Scene State"
        B[Scene Context] -->|Visual Style Lock| C
        B -->|Lighting/Tone| C
        M[Master Scene Images] -->|Setting Reference| C
        SC[Scene-Specific Character Refs] -->|Wardrobe Lock| C
    end

    subgraph "Agentic Orchestration"
        C{AI Director} -->|Video Analysis| D
        D[Shot Planner] -->|Shot 1| E
        D -->|Shot 2| E
        D -->|Shot N| E
    end

    subgraph "Generative Pipeline"
        E[Context Injection] -->|Refs + Prompts| F[Image Gen]
        F -->|Start Frame| G[Video Gen]
        G -->|End Frame| E
        V -->|Audio| L[Audio-Driven Animation]
        F -->|Face Image| L
    end
```

### Progressive Shot Chain

```
Shot 1 (Wide)     Shot 2 (Medium)    Shot 3 (Close-up)
    │                  │                   │
    ▼                  ▼                   ▼
┌─────────┐      ┌─────────┐        ┌─────────┐
│ Generate│      │ Generate│        │ Generate│
│  Image  │      │  Image  │        │  Image  │
└────┬────┘      └────┬────┘        └────┬────┘
     │                │                   │
     ▼                ▼                   ▼
┌─────────┐      ┌─────────┐        ┌─────────┐
│ Generate│──────│ Generate│────────│ Generate│
│  Video  │ end  │  Video  │  end   │  Video  │
└─────────┘frame └─────────┘ frame  └─────────┘
              ▲                  ▲
              │                  │
         Start Frame        Start Frame
         Continuity         Continuity
```

The **last frame of Shot N becomes the start frame for Shot N+1**, creating seamless visual continuity.

---

## Quick Start

### Prerequisites

- Node.js 18+
- Python 3.9+
- ffmpeg (with ffprobe)

### Installation

```bash
# Clone
git clone https://github.com/skolmuirgheasa/openfilmai.git
cd openfilmai

# Frontend dependencies
npm install

# Python environment
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run (starts backend + frontend + Electron)
npm run dev
```

### API Keys Required

Configure in Settings:

| Service | Purpose | Required |
|---------|---------|----------|
| **Replicate** | Image/video generation | Yes |
| **Anthropic** or **OpenAI** | Shot planning, scene analysis | Yes |
| **ElevenLabs** | Text-to-speech, voice cloning | For audio |
| **WaveSpeed** | Audio-driven animation | For dialogue |
| **Google Cloud** | Veo, Gemini | For AI Director |

---

## Stack & Integrations

| Modality | Provider | Purpose |
|----------|----------|---------|
| **Video Generation** | [Google Vertex AI](https://cloud.google.com/vertex-ai), [Replicate](https://replicate.com) | Video synthesis |
| **Image Generation** | [Replicate](https://replicate.com) | Multi-reference image synthesis |
| **Orchestration** | [Anthropic](https://anthropic.com), [OpenAI](https://openai.com) | Shot planning, scene analysis |
| **Vision Analysis** | [Google Gemini](https://deepmind.google/technologies/gemini/) | AI Director—video continuity |
| **Voice/TTS** | [ElevenLabs](https://elevenlabs.io) | Character voices |
| **Animation** | [WaveSpeed AI](https://wavespeed.ai) | Audio-driven facial animation |

---

## Key Capabilities

### Hierarchical State Injection

Every shot inherits from parent state objects:

```typescript
interface ShotState {
  // Scene-level state (immutable per scene)
  scene_master_images: string[];     // Setting/location lock
  scene_character_refs: string[];    // Wardrobe/appearance lock
  visual_style: string;              // Color palette, camera style

  // Shot-level continuity
  previous_shot_end_frame: string;   // Frame chain anchor
  previous_shot_id: string;          // Graph linkage

  // Character-level identity (fallback hierarchy)
  global_character_refs: string[];   // Identity baseline
  voice_id: string;                  // Voice profile
}
```

### AI Director: Video-Aware Planning

```mermaid
graph LR
    A[Previous Shot Video] -->|Vision Analysis| B[Character Positions]
    A -->|Frame-by-Frame| C[Scene Geography]
    B --> D[Next Shot Plan]
    C --> D
    D -->|Image Prompt| E[Exact Positioning]
    D -->|Video Prompt| F[Motion Continuity]
```

Send multiple prior shots for narrative understanding—the AI sees visual flow, not just text.

### Audio-Driven Animation

```
Text ──► TTS ──► Audio Track
                     │
Character Image ─────┼──► WaveSpeed ──► Animated Video
                     │
Scene Context ───────┘
```

---

## Data Model

### Scene State

```python
class Scene:
    scene_id: str
    title: str
    description: str

    # Visual State Lock
    master_image_ids: List[str]
    visual_style: str
    color_palette: str
    camera_style: str

    # Character State
    cast: List[SceneCast]

    # Shot Graph
    shots: List[Shot]
```

### Shot (Generation Unit)

```python
class Shot:
    shot_id: str
    shot_number: int

    # Planning
    camera_angle: str
    subject: str
    action: str
    characters_in_shot: List[str]
    dialogue: Optional[str]
    prompt: str

    # Continuity (the key to zero drift)
    start_frame_path: Optional[str]  # Previous shot's end frame
    scene_id: str                    # Links to parent Scene

    # Outputs
    image_path: Optional[str]
    audio_path: Optional[str]
    file_path: Optional[str]
    status: Literal["planned", "image_ready", "audio_ready", "video_ready"]
```

---

## Project Structure

```
openfilmai/
├── frontend/                    # React + TypeScript UI
│   └── src/App.tsx             # Main application
├── backend/
│   ├── main.py                 # FastAPI server
│   ├── ai/
│   │   ├── cinematographer.py  # Shot planning
│   │   ├── vertex_client.py    # Google AI integration
│   │   └── replicate_client.py # Replicate integration
│   ├── video/
│   │   └── ffmpeg.py           # Frame extraction
│   └── storage/
│       └── files.py            # Metadata persistence
├── project_data/               # User projects (runtime)
├── electron.js                 # Desktop shell
└── requirements.txt
```

---

## Environment Variables

```bash
# API Keys (or configure in Settings UI)
export REPLICATE_API_TOKEN="..."
export ANTHROPIC_API_KEY="..."
export OPENAI_API_KEY="..."
export ELEVENLABS_API_KEY="..."
export WAVESPEED_API_KEY="..."

# Google Cloud (for Vertex AI)
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
export GOOGLE_CLOUD_PROJECT="your-project-id"
export VERTEX_LOCATION="us-central1"
```

---

## Roadmap

- [ ] Batch generation — Queue multiple shots for overnight rendering
- [ ] Version control — Track shot iterations, revert to previous takes
- [ ] Multi-scene projects — Scene graph with cross-scene character consistency
- [ ] Export presets — Direct export to Premiere XML, DaVinci

---

## Contributing

Contributions welcome.

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

---

## License

MIT

---

<div align="center">

**OpenFilm AI** — State injection for AI filmmaking. Zero drift. Infinite runtime.

</div>
