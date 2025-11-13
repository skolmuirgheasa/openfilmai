# AI Features Porting Bundle

This bundle contains all the AI features built for OpenShot, ready to be integrated into a new application.

## Contents

### `/providers/` - AI Provider Implementations
- **`base.py`** - Base class for all AI providers (HTTP requests, error handling)
- **`elevenlabs.py`** - ElevenLabs text-to-speech and speech-to-speech conversion
- **`wavespeed.py`** - WaveSpeed InfiniteTalk lip-sync (image + audio → video)
- **`replicate.py`** - Replicate API (Veo 3.1, image models)
- **`vertex.py`** - Google Vertex AI (Veo 3.1 via GCS)

### `/ui/` - PyQt5 UI Components
- **`models_widget.py`** - Settings panel for managing API keys (Replicate, ElevenLabs, WaveSpeed, Vertex)
- **`characters_widget.py`** - Character management (name, reference images, voice IDs)
- **`ai_generation_dialog.py`** - Main AI generation modal with provider selection, character selection, prompts, frame inputs

### `/utils/` - Utility Classes
- **`settings.py`** - Simple settings storage (replaces OpenShot's SettingStore)
- **`characters.py`** - Character data persistence (replaces project file storage)

## Dependencies

```bash
pip install PyQt5 requests google-auth google-cloud-storage
```

## Quick Start

### 1. Settings Integration

Replace OpenShot's `get_app().get_settings()` with:

```python
from utils.settings import SimpleSettings

settings = SimpleSettings()  # Stores in ~/.ai_app/settings.json
```

### 2. Character Storage

Replace OpenShot's project data storage with:

```python
from utils.settings import CharacterStorage

char_storage = CharacterStorage()  # Stores in ~/.ai_app/characters.json
characters = char_storage.get_all()
```

### 3. Provider Usage

All providers follow the same pattern:

```python
from providers.elevenlabs import ElevenLabsProvider
from providers.wavespeed import WaveSpeedProvider
from providers.replicate import ReplicateProvider
from providers.vertex import VertexVeoProvider

# ElevenLabs
el = ElevenLabsProvider(api_key="your_key")
audio_path = el.generate(text="Hello world", voice_id="voice_id_here")
converted_audio = el.speech_to_speech("input.wav", voice_id="voice_id")

# WaveSpeed
ws = WaveSpeedProvider(api_key="your_key")
video_path = ws.generate(
    prompt="emotion description",
    image_path="character.jpg",
    audio_path="audio.mp3",
    resolution="720p"
)

# Replicate
rep = ReplicateProvider(api_key="your_key")
video_path = rep.generate(
    prompt="video description",
    model="google/veo-3.1",
    first_frame_image="start.jpg",
    reference_images=["ref1.jpg", "ref2.jpg"],
    duration=8
)

# Vertex AI
vertex = VertexVeoProvider(
    credentials_path="path/to/service-account.json",
    project_id="your-project",
    location="us-central1"
)
video_path = vertex.generate(
    prompt="video description",
    first_frame_image="start.jpg",
    reference_images=["ref1.jpg"]
)
```

### 4. UI Components

#### Models Widget (API Key Management)

```python
from ui.models_widget import ModelsWidget
from PyQt5.QtWidgets import QMainWindow

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Replace get_app().get_settings() with SimpleSettings
        # You'll need to modify ModelsWidget.__init__ to accept settings
        self.models_widget = ModelsWidget(self)
```

**Required modifications:**
- Replace `get_app().get_settings()` with `SimpleSettings()` instance
- Replace `get_app()._tr()` with your translation function or remove

#### Characters Widget

```python
from ui.characters_widget import CharactersWidget
from utils.settings import CharacterStorage

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Modify CharactersWidget to use CharacterStorage instead of project._data
        self.char_storage = CharacterStorage()
        self.characters_widget = CharactersWidget(self, self.char_storage)
```

**Required modifications:**
- Replace `app.project._data.get("characters")` with `character_storage.get_all()`
- Replace `app.project._data["characters"] = ...` with `character_storage.add/update/delete()`
- Replace `app.project.save()` with `character_storage.save()`

#### AI Generation Dialog

```python
from ui.ai_generation_dialog import AIGenerationDialog

dialog = AIGenerationDialog(parent_window, track_id=None, track_label="Video")
if dialog.exec_() == QDialog.Accepted:
    generated_file = dialog.generated_file_path
    # Import generated file into your app
```

**Required modifications:**
- Replace `get_app().get_settings()` with `SimpleSettings()` instance
- Replace `FrameExtractor.extract_last_frame_from_track()` with your frame extraction logic (or remove if not needed)
- Replace `get_app().project._data.get("characters")` with `CharacterStorage().get_all()`
- Remove timeline-specific logic (track_id, track_label can be None/empty)

## Key Features

### 1. API Key Management
- Secure storage of API keys (Replicate, ElevenLabs, WaveSpeed, Vertex)
- Enable/disable providers
- Persistent storage in JSON

### 2. Character Management
- Create/edit/delete characters
- Store up to 3 reference images per character
- Store ElevenLabs voice ID per character
- Auto-populate in generation dialog

### 3. AI Generation Dialog
- Provider selection (based on enabled providers)
- Character selection (auto-fills reference images and voice ID)
- Prompt input (saved per track type)
- Start frame / End frame / Reference images
- Audio source selection (for WaveSpeed):
  - Text-to-speech via ElevenLabs
  - Record voice + convert to character
  - Upload audio file + convert to character
- Progress tracking
- Background generation (QThread worker)

### 4. Provider Features

**ElevenLabs:**
- Text-to-speech with voice selection
- Speech-to-speech voice conversion
- Model selection (eleven_multilingual_v2, eleven_multilingual_sts_v2)

**WaveSpeed:**
- Image + audio → talking avatar video
- Base64 data URL uploads
- Job polling with status updates
- Resolution selection (480p, 720p)

**Replicate:**
- Veo 3.1 video generation
- Image model support
- Reference image support (1-3 images)
- Start/end frame interpolation

**Vertex AI:**
- Veo 3.1 via Google Cloud
- GCS upload/download
- OAuth2 service account auth
- Long-running operation polling

## File Structure

```
ai_porting_bundle/
├── README.md (this file)
├── providers/
│   ├── base.py
│   ├── elevenlabs.py
│   ├── wavespeed.py
│   ├── replicate.py
│   └── vertex.py
├── ui/
│   ├── models_widget.py
│   ├── characters_widget.py
│   └── ai_generation_dialog.py
└── utils/
    └── settings.py
```

## Migration Checklist

- [ ] Replace `get_app().get_settings()` with `SimpleSettings()`
- [ ] Replace `app.project._data["characters"]` with `CharacterStorage()`
- [ ] Remove OpenShot-specific imports (`classes.app`, `classes.logger`, etc.)
- [ ] Replace `classes.logger.log` with Python's `logging` module
- [ ] Remove timeline-specific logic from `ai_generation_dialog.py`
- [ ] Update `FrameExtractor` calls or remove if not needed
- [ ] Replace `get_app()._tr()` with your translation system or remove
- [ ] Test all providers with your API keys
- [ ] Update file paths for generated media to match your app's structure

## Example: Minimal Integration

```python
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton
from ui.ai_generation_dialog import AIGenerationDialog
from utils.settings import SimpleSettings, CharacterStorage

class MyApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = SimpleSettings()
        self.char_storage = CharacterStorage()
        
        btn = QPushButton("Generate AI Clip")
        btn.clicked.connect(self.show_generation_dialog)
        self.setCentralWidget(btn)
    
    def show_generation_dialog(self):
        # You'll need to modify AIGenerationDialog to accept settings/char_storage
        dialog = AIGenerationDialog(self, track_id=None, track_label="Video")
        if dialog.exec_():
            print(f"Generated: {dialog.generated_file_path}")

app = QApplication([])
window = MyApp()
window.show()
app.exec_()
```

## Notes

- All providers handle errors gracefully with `AIProviderError` exceptions
- File paths use `/tmp` for temporary files (adjust for your OS)
- Audio recording uses `ffmpeg` (ensure it's in PATH)
- Vertex AI requires Google Cloud service account JSON
- All providers support timeout and retry logic
- UI components use PyQt5 (compatible with PyQt6 with minor changes)

## Support

The code is well-commented and follows a consistent pattern. Each provider is self-contained and can be used independently. The UI components are modular and can be adapted to any PyQt application.

