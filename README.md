# OpenFilm AI – Porting Bundle (Python)

A self-contained bundle of AI features (providers + PyQt5 UI widgets) ready to embed in your Python application. It includes production-ready wrappers for popular AI services and modular UI components for model/key management, character storage, and multimodal generation flows.

## What’s inside

- Providers (`ai_porting_bundle/providers/`)
  - `ElevenLabsProvider` – text-to-speech and speech-to-speech
  - `WaveSpeedProvider` – lip-sync: image + audio → video
  - `ReplicateProvider` – video/image models (e.g., Veo 3.1)
  - `VertexVeoProvider` – Google Vertex AI Veo via GCS
- UI (`ai_porting_bundle/ui/`)
  - `ModelsWidget` – manage and persist provider API keys
  - `CharactersWidget` – manage characters, reference images, voice IDs
  - `AIGenerationDialog` – end-to-end generation workflow
- Utils (`ai_porting_bundle/utils/`)
  - `SimpleSettings` – JSON-backed settings store
  - `CharacterStorage` – JSON-backed character store

Refer to the detailed bundle docs in `ai_porting_bundle/README.md` for API-by-API examples and migration notes.

## Requirements

- Python 3.9+
- System dependency: `ffmpeg` (for recording/processing audio used by some flows)

Python dependencies (install via requirements file):

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r ai_porting_bundle/requirements.txt
```

The requirements currently include:

- PyQt5
- requests
- google-auth
- google-cloud-storage

You’ll also need provider-specific credentials (see “Provider setup” below).

## Quick start

### Use providers directly (no UI)

See `ai_porting_bundle/example_standalone.py` for a minimal, headless usage of:

- ElevenLabs (TTS and voice conversion)
- WaveSpeed (talking avatar video from image + audio)
- Replicate (e.g., Veo 3.1 video)

Import paths are exposed via `ai_porting_bundle/providers/__init__.py`, e.g.:

```python
from ai_porting_bundle.providers import (
    ElevenLabsProvider,
    WaveSpeedProvider,
    ReplicateProvider,
    VertexVeoProvider,
)
```

### Use the PyQt5 UI widgets

Embed the widgets in your PyQt5 app. The UI expects a simple settings and character store:

```python
from ai_porting_bundle.utils.settings import SimpleSettings, CharacterStorage
from ai_porting_bundle.ui.ai_generation_dialog import AIGenerationDialog
```

- Replace any app-specific settings store with `SimpleSettings()`
- Replace project-bound character persistence with `CharacterStorage()`
- Wire `AIGenerationDialog` into your window and handle the accepted result (`generated_file_path`)

Find concrete snippets and migration notes in `ai_porting_bundle/README.md`.

## Provider setup

- ElevenLabs
  - Requirement: ElevenLabs API key
  - Capabilities: TTS, speech-to-speech; model selection supported
- WaveSpeed
  - Requirement: WaveSpeed API key
  - Capabilities: talking avatar video; job polling; 480p/720p
- Replicate
  - Requirement: Replicate API key
  - Capabilities: Veo 3.1 video, image models, reference images
- Google Vertex AI (Veo via GCS)
  - Requirements: Service account JSON, `project_id`, `location`
  - Capabilities: long-running operations, GCS upload/download

Store provider keys in your app using `SimpleSettings` or your own secure store. The included `ModelsWidget` provides a ready-made UI for entering and persisting keys.

## Project structure

```
openfilmai/
├── ai_porting_bundle/
│   ├── README.md
│   ├── requirements.txt
│   ├── example_standalone.py
│   ├── providers/
│   ├── ui/
│   └── utils/
├── blueprint.txt
└── technicalinstructions.txt
```

## Development

- Create/activate a virtual environment and install dependencies (see “Requirements”).
- Run and iterate on your integration (providers or UI) within your app.
- If you need to test provider calls in isolation, adapt `example_standalone.py` with your keys and inputs.

## Troubleshooting

- Missing `ffmpeg`: install via your package manager (e.g., `brew install ffmpeg` on macOS).
- Google Vertex AI: ensure the service account has required permissions for Vertex AI and the configured GCS bucket.
- Network issues: many providers return async jobs; ensure polling intervals/timeouts are set reasonably for your environment.

## License

TBD by repository owner.


