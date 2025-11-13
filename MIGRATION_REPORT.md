# Migration Report: ai_porting_bundle ➜ OpenFilmAI Architecture

This report identifies reusable components in `ai_porting_bundle/` and how they map to the new OpenFilmAI architecture. Do not integrate directly yet; reuse selectively when implementing corresponding backend features.

## Reusable Assets

- Providers (`ai_porting_bundle/providers/`)
  - `ElevenLabsProvider`: TTS and speech-to-speech; clear API surface; good error handling.
  - `WaveSpeedProvider`: talking avatar video from image+audio; handles job polling.
  - `ReplicateProvider`: Veo 3.1 and image models; supports reference images, frames.
  - `VertexVeoProvider`: Veo via Google Vertex AI with GCS upload/download and LRO polling.
  - `base.py`: base classes and `AIProviderError` exception – keep as common provider interface.

- Utils (`ai_porting_bundle/utils/`)
  - `SimpleSettings`: JSON-backed key-value store – suitable for desktop local config.
  - `CharacterStorage`: JSON-backed character profiles – can seed `backend/storage/` layer.

- UI (`ai_porting_bundle/ui/`)
  - `ModelsWidget`, `CharactersWidget`, `AIGenerationDialog`: Reference-only for flows and fields; do not port PyQt UI. Reimplement in React + Radix UI.

## Recommended Reuse Strategy

- Backend-first reuse:
  - Extract provider call logic from `ai_porting_bundle/providers/*` into `backend/ai/providers/` as HTTP-bound service modules. Keep request building, polling, and error translation.
  - Use MoviePy/FFmpeg operations under `backend/video/` for frame extraction and smoothing.
  - Persist project/scene/shot/character metadata using JSON files under `project_data/` via `backend/storage/` helpers.

- Frontend reimplementation:
  - Recreate settings and character forms in React + Radix UI (Tailwind for styling).
  - Build the scene-shot timeline with simple sequential playback and drag ordering (not a full NLE).

## Notes and Caveats

- Remove OpenShot-specific hooks (e.g., `get_app()`, timeline references) when reusing code.
- Avoid any tight coupling to PyQt events; convert to stateless Python functions in the backend.
- Adopt consistent logging and error contracts for REST responses.

## Next Steps

1) Scaffold Electron + React + TS frontend and FastAPI backend (done in this repo).
2) Implement basic health and stub endpoints.
3) Port provider wrappers incrementally into `backend/ai/providers/`.
4) Implement frame extraction and optical-flow smoothing in `backend/video/`.
5) Design metadata schemas and CRUD in `backend/storage/`.


