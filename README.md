# OpenFilm AI

A professional scene orchestrator and shot planner for AI filmmaking. Design complete scenes with an AI cinematographer, lock character appearances per scene, and generate shot lists with automatic visual consistency.

Built with Electron, React, and Python, featuring scene-based editing, character management, and integration with leading AI providers.

---

## Scene Orchestration Workflow

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

## Features

- **AI Video Generation**: Generate videos using Replicate (Veo 3.1) or Google Vertex AI
- **AI Shot Planning**: Claude or GPT-4 analyzes scenes and generates comprehensive shot lists
- **Text-to-Speech & Voice Conversion**: ElevenLabs integration for natural voice generation
- **Lip-Sync**: WaveSpeed InfiniteTalk for talking avatar videos
- **Scene-Based Editing**: Organize your project into scenes and shots
- **Character Management**: Store character profiles with reference images and voice IDs
- **Progressive Consistency**: Wide shots anchor the look, each shot references the previous
- **Media Library**: Manage all your generated assets in one place
- **Smooth Transitions**: Optical flow smoothing between clips for seamless continuity

---

## Prerequisites

Before you begin, make sure you have the following installed:

- **Node.js** (v18 or higher) - [Download](https://nodejs.org/)
- **Python** (3.9 or higher) - [Download](https://www.python.org/downloads/)
- **ffmpeg** - Required for audio/video processing (including ffprobe for metadata)

### Installing ffmpeg

**macOS:**
```bash
brew install ffmpeg
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install ffmpeg
```

**Windows:**
Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to your PATH.

Verify installation:
```bash
ffmpeg -version
ffprobe -version
```

---

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd openfilmai
```

### 2. Install Node.js Dependencies

```bash
npm install
```

This installs all frontend dependencies including Electron, React, and build tools.

### 3. Set Up Python Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 4. Install Python Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- FastAPI (backend server)
- Uvicorn (ASGI server)
- MoviePy (video editing)
- Google Cloud libraries (for Vertex AI)
- Other required packages

---

## Running the Application

### Development Mode (One Command)

```bash
npm run dev
```

This single command starts everything:
1. Python backend server on `http://127.0.0.1:8000`
2. Vite frontend dev server on `http://localhost:5173`
3. Electron desktop window (opens automatically when servers are ready)

The app will automatically reload when you make code changes.

### Production Build

```bash
npm run build
npm start
```

---

## API Setup

OpenFilm AI integrates with multiple AI providers. You'll need API keys or credentials for the services you want to use. All credentials are stored locally and never shared.

### Accessing Settings

1. Launch the application
2. Click the **Settings** button (gear icon) in the top-right corner
3. Enter your API keys and credentials in the settings dialog
4. Click **Save** to store your credentials

### Replicate API

**What it's used for:**
- Video generation (Veo 3.1, etc.)
- Image generation (Seedream-4, etc.)

**Setup:**
1. Sign up at [replicate.com](https://replicate.com)
2. Go to your account settings
3. Copy your API token
4. Paste it into the "Replicate API Token" field in Settings

### Anthropic / OpenAI API (AI Cinematographer)

**What it's used for:**
- Scene analysis and shot planning
- Auto-generating shot lists from scene descriptions
- Character appearance proposals

**Setup:**
1. Sign up at [anthropic.com](https://anthropic.com) or [openai.com](https://openai.com)
2. Get your API key
3. Paste it into the appropriate field in Settings
4. Select your preferred LLM provider

### ElevenLabs API

**What it's used for:** Text-to-speech and voice-to-voice conversion

**Setup:**
1. Sign up at [elevenlabs.io](https://elevenlabs.io)
2. Navigate to your profile settings
3. Copy your API key
4. Paste it into the "ElevenLabs API Key" field in Settings

### WaveSpeed API

**What it's used for:** Lip-sync generation (talking avatar videos from image + audio)

**Setup:**
1. Sign up at [wavespeed.ai](https://wavespeed.ai)
2. Get your API key from the dashboard
3. Paste it into the "Wavespeed API Key" field in Settings

### Google Vertex AI (Optional)

**What it's used for:** Google Cloud Veo 3.1 video generation with GCS storage

**Setup:**

1. **Create a Google Cloud Project:**
   - Go to [Google Cloud Console](https://console.cloud.google.com)
   - Create a new project or select an existing one
   - Note your Project ID

2. **Enable Required APIs:**
   - Enable "Vertex AI API"
   - Enable "Cloud Storage API"

3. **Create a Service Account:**
   - Go to IAM & Admin → Service Accounts
   - Click "Create Service Account"
   - Give it a name (e.g., "openfilmai-service")
   - Grant roles: "Vertex AI User" and "Storage Admin"
   - Click "Done"

4. **Download Service Account Key:**
   - Click on the service account you just created
   - Go to the "Keys" tab
   - Click "Add Key" → "Create new key"
   - Choose JSON format
   - Save the JSON file to a secure location on your computer

5. **Create a GCS Bucket (Optional but Recommended):**
   - Go to Cloud Storage → Buckets
   - Click "Create Bucket"
   - Choose a unique name
   - Select a location (e.g., `us-central1`)
   - Choose "Standard" storage class

6. **Configure in OpenFilm AI:**
   - **Vertex Service Account JSON Path**: Full path to the JSON key file
   - **Vertex Project ID**: Your Google Cloud project ID
   - **Vertex Location**: Usually `us-central1`
   - **Vertex Temp GCS Bucket**: The bucket name you created

---

## Usage Guide

### Scene Setup Workflow

1. **Create scene** — Add title and description
2. **AI Assist** — Click to analyze scene and auto-fill:
   - Visual style, color palette, camera approach
   - Character appearances and wardrobe for this scene
   - Establishing shot prompts
3. **Generate scene image** — Create master reference, accept/reject until satisfied
4. **Generate character refs** — For each cast member, generate scene-locked appearance
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

### Managing Characters

Characters help maintain consistency across your project:

1. Create a character with a name
2. Upload 1-3 reference images (global identity)
3. Set a voice ID (from ElevenLabs)
4. In each scene, generate scene-specific character refs for wardrobe/appearance

### How Smoothing Works

OpenFilm AI includes a smoothing feature to create seamless transitions between clips.

**How to use it:**
1. On the timeline, you'll see a small arrow `→` between two adjacent clips
2. Click the **"Smooth"** checkbox in the transition bar
3. Click **"Apply"**

**What happens under the hood:**
1. The app takes the last few frames of Clip A and the first few frames of Clip B
2. It uses OpenCV's DIS optical flow algorithm to analyze the motion
3. It generates intermediate frames to blend the motion seamlessly
4. The result is a merged video file that replaces the original two clips

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

## Project Structure

```
openfilmai/
├── frontend/              # React + TypeScript frontend
│   ├── src/
│   │   ├── App.tsx       # Main application component
│   │   └── ...
│   └── vite.config.ts    # Vite configuration
├── backend/              # Python FastAPI backend
│   ├── main.py          # Main server file
│   ├── ai/              # AI provider clients
│   │   └── cinematographer.py  # Shot planning AI
│   ├── video/           # Video processing (FFmpeg, OpenCV)
│   └── storage/         # File and metadata management
├── project_data/        # User projects and media (created at runtime)
├── electron.js          # Electron main process
├── package.json         # Node.js dependencies
└── requirements.txt     # Python dependencies
```

---

## Integrating Custom Models

### Adding a Replicate Model

For simple integrations, add the model ID string (e.g., `owner/model-name`) to the frontend dropdown — the Replicate client is generic.

### Adding a Local Model (Advanced)

1. **Backend Integration:**
   - Navigate to `backend/ai/`
   - Create a new client file (e.g., `my_model_client.py`)
   - Look at `replicate_client.py` for reference
   - Register your new client in `backend/main.py`

2. **Frontend UI:**
   - In `frontend/src/App.tsx`, add your model to the dropdown
   - Ensure the backend `generate_shot` endpoint handles the new model

---

## Data Model Reference

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

### Backend Won't Start

- Make sure Python virtual environment is activated: `source .venv/bin/activate`
- Check if port 8000 is already in use: `lsof -i :8000` (macOS/Linux)
- Verify all Python dependencies are installed: `pip install -r requirements.txt`
- Check Python version: `python3 --version` (should be 3.9+)

### Frontend Won't Load

- Make sure the backend is running first (check `http://127.0.0.1:8000/health`)
- Check if port 5173 is available: `lsof -i :5173`
- Check the Electron console for errors (View → Toggle Developer Tools)

### ffmpeg Not Found

- Verify ffmpeg is installed: `ffmpeg -version`
- Verify `ffprobe` is also installed: `ffprobe -version`
- Make sure ffmpeg is in your PATH

### API Generation Fails

- **Check API Keys:** Verify your API keys are correct in Settings
- **Check Credits:** Some APIs have usage limits or require payment
- **Check Logs:** Look at the backend console for detailed error messages

### Vertex AI / GCS Errors

- **Service Account:** Verify the JSON file path is correct and the file exists
- **Permissions:** Ensure the service account has "Vertex AI User" and "Storage Admin" roles
- **APIs Enabled:** Check that Vertex AI API and Cloud Storage API are enabled

### Port Already in Use

```bash
# macOS/Linux
kill -9 $(lsof -t -i:8000)
kill -9 $(lsof -t -i:5173)

# Windows
taskkill /PID <process_id> /F
```

---

## Environment Variables

You can set API keys via environment variables:

```bash
export REPLICATE_API_TOKEN="your-token"
export ELEVENLABS_API_KEY="your-key"
export WAVESPEED_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"
export OPENAI_API_KEY="your-key"
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
export GOOGLE_CLOUD_PROJECT="your-project-id"
export VERTEX_LOCATION="us-central1"
export VERTEX_TEMP_BUCKET="your-bucket-name"
```

---

## Contributing

This is an open-source project. Contributions are welcome.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

## License

TBD

---

Built for filmmakers who need systematic control over AI-generated visual consistency.
