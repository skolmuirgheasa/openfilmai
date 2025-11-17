# OpenFilm AI

An open-source desktop application for AI-powered video, image, and audio generation. Built with Electron, React, and Python, featuring scene-based editing, character management, and integration with leading AI providers.

## Features

- **AI Video Generation**: Generate videos using Replicate (Veo 3.1) or Google Vertex AI
- **Text-to-Speech & Voice Conversion**: ElevenLabs integration for natural voice generation
- **Lip-Sync**: WaveSpeed InfiniteTalk for talking avatar videos
- **Scene-Based Editing**: Organize your project into scenes and shots
- **Character Management**: Store character profiles with reference images and voice IDs
- **Media Library**: Manage all your generated assets in one place

## Prerequisites

Before you begin, make sure you have the following installed:

- **Node.js** (v18 or higher) - [Download](https://nodejs.org/)
- **Python** (3.9 or higher) - [Download](https://www.python.org/downloads/)
- **ffmpeg** - Required for audio/video processing

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
```

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

## Running the Application

### Development Mode

Run all services (backend, frontend, and Electron) simultaneously:

```bash
npm run dev
```

This command will:
1. Start the Python backend server on `http://127.0.0.1:8000`
2. Start the Vite dev server for the frontend on `http://localhost:5173`
3. Launch the Electron window once both servers are ready

The app will automatically reload when you make code changes.

### Production Build

To build the frontend for production:

```bash
npm run build
```

Then start the app:

```bash
npm start
```

## API Setup

OpenFilm AI integrates with multiple AI providers. You'll need API keys or credentials for the services you want to use. All credentials are stored locally and never shared.

### Accessing Settings

1. Launch the application
2. Click the **Settings** button (gear icon) in the top-right corner
3. Enter your API keys and credentials in the settings dialog
4. Click **Save** to store your credentials

### Replicate API

**What it's used for:** Video generation (Veo 3.1, NanoBanana, etc.) and image models

**Setup:**
1. Sign up at [replicate.com](https://replicate.com)
2. Go to your account settings
3. Copy your API token
4. Paste it into the "Replicate API Token" field in Settings

**Getting started:** Replicate offers free credits for new users. Check their pricing page for current rates.

### ElevenLabs API

**What it's used for:** Text-to-speech and voice-to-voice conversion

**Setup:**
1. Sign up at [elevenlabs.io](https://elevenlabs.io)
2. Navigate to your profile settings
3. Copy your API key
4. Paste it into the "ElevenLabs API Key" field in Settings

**Getting started:** ElevenLabs offers a free tier with limited characters per month. You can upgrade for more usage.

### WaveSpeed API

**What it's used for:** Lip-sync generation (talking avatar videos from image + audio)

**Setup:**
1. Sign up at [wavespeed.ai](https://wavespeed.ai) (or InfiniteTalk)
2. Get your API key from the dashboard
3. Paste it into the "Wavespeed API Key" field in Settings

**Note:** WaveSpeed may have different pricing tiers. Check their website for current plans.

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
   - Choose a unique name (e.g., `your-project-openfilmai-temp`)
   - Select a location (e.g., `us-central1`)
   - Choose "Standard" storage class
   - Click "Create"

6. **Configure in OpenFilm AI:**
   - **Vertex Service Account JSON Path**: Full path to the JSON key file you downloaded
   - **Vertex Project ID**: Your Google Cloud project ID
   - **Vertex Location**: Usually `us-central1` (or your preferred region)
   - **Vertex Temp GCS Bucket**: The bucket name you created (e.g., `your-project-openfilmai-temp`)
     - If left empty, the app will auto-create a bucket named `{project-id}-openfilmai-temp`

**Important Notes:**
- The service account JSON file contains sensitive credentials. Keep it secure and never commit it to version control.
- The GCS bucket is used for temporary storage of images during video generation. You'll be charged for storage and data transfer according to Google Cloud pricing.
- If you don't specify a bucket name, the app will attempt to create one automatically using your project ID.

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
│   ├── video/           # Video processing (FFmpeg)
│   └── storage/         # File and metadata management
├── ai_porting_bundle/   # Reusable AI provider bundle
│   ├── providers/       # AI provider implementations
│   ├── ui/              # PyQt5 UI components (for other apps)
│   └── utils/           # Utility classes
├── project_data/        # User projects and media (created at runtime)
├── electron.js          # Electron main process
├── package.json         # Node.js dependencies
└── requirements.txt     # Python dependencies
```

## Usage Guide

### Creating a Project

1. When you first launch the app, you'll see a project selector
2. Enter a project name (e.g., "my-film") and click "Create"
3. The app will create a new project directory in `project_data/`

### Adding Scenes

1. Click the "+" button next to "Scenes" in the sidebar
2. Enter a scene title (e.g., "Opening Scene")
3. Click "Add Scene"

### Generating Media

1. **Video Generation:**
   - Select a scene
   - Click "Generate Shot"
   - Choose a provider (Replicate or Vertex)
   - Enter a prompt describing your video
   - Optionally add start/end frames or reference images
   - Click "Generate"

2. **Voice Generation:**
   - Click "Generate Voice"
   - Choose TTS (text-to-speech) or Voice-to-Voice
   - Enter text or upload audio
   - Select a voice (if using ElevenLabs)
   - Click "Generate"

3. **Lip-Sync:**
   - Click "Generate Lip-Sync"
   - Upload an image or select a video
   - Upload or record audio
   - Click "Generate"

### Managing Characters

Characters help maintain consistency across your project:

1. Create a character with a name
2. Upload 1-3 reference images
3. Set a voice ID (from ElevenLabs)
4. When generating media, select the character to auto-fill images and voice

## Troubleshooting

### Backend Won't Start

**Problem:** The backend server fails to start or shows connection errors.

**Solutions:**
- Make sure Python virtual environment is activated: `source .venv/bin/activate`
- Check if port 8000 is already in use: `lsof -i :8000` (macOS/Linux) or `netstat -ano | findstr :8000` (Windows)
- Verify all Python dependencies are installed: `pip install -r requirements.txt`
- Check Python version: `python3 --version` (should be 3.9+)

### Frontend Won't Load

**Problem:** The Electron window shows a blank screen or connection errors.

**Solutions:**
- Make sure the backend is running first (check `http://127.0.0.1:8000/health`)
- Check if port 5173 is available: `lsof -i :5173`
- Try clearing browser cache or restarting the dev server
- Check the Electron console for errors (View → Toggle Developer Tools)

### ffmpeg Not Found

**Problem:** Errors about ffmpeg not being found.

**Solutions:**
- Verify ffmpeg is installed: `ffmpeg -version`
- Make sure ffmpeg is in your PATH
- On macOS, try: `brew install ffmpeg`
- On Windows, download from ffmpeg.org and add to PATH

### API Generation Fails

**Problem:** Video/voice generation fails with API errors.

**Solutions:**
- **Check API Keys:** Verify your API keys are correct in Settings
- **Check Credits:** Some APIs have usage limits or require payment
- **Check Logs:** Look at the backend console for detailed error messages
- **Replicate:** Check your account at replicate.com for credit balance
- **ElevenLabs:** Verify your character limit at elevenlabs.io
- **Vertex AI:** Ensure your service account has proper permissions and APIs are enabled

### Vertex AI / GCS Errors

**Problem:** Vertex AI generation fails with authentication or bucket errors.

**Solutions:**
- **Service Account:** Verify the JSON file path is correct and the file exists
- **Permissions:** Ensure the service account has "Vertex AI User" and "Storage Admin" roles
- **APIs Enabled:** Check that Vertex AI API and Cloud Storage API are enabled in Google Cloud Console
- **Bucket:** If you specified a bucket name, ensure it exists and is in the correct region
- **Project ID:** Verify your Project ID matches your Google Cloud project

### Port Already in Use

**Problem:** Error about ports 8000 or 5173 being in use.

**Solutions:**
- **Kill existing process:**
  - macOS/Linux: `kill -9 $(lsof -t -i:8000)` or `kill -9 $(lsof -t -i:5173)`
  - Windows: `taskkill /PID <process_id> /F` (find PID with `netstat -ano | findstr :8000`)
- **Or use different ports:** Modify `package.json` scripts and `backend/main.py` to use different ports

### Project Data Not Saving

**Problem:** Projects, scenes, or media aren't being saved.

**Solutions:**
- Check that `project_data/` directory exists and is writable
- Verify disk space is available
- Check file permissions on the `project_data/` directory
- Look for error messages in the backend console

## Development

### Project Structure

- **Frontend:** React + TypeScript + TailwindCSS, built with Vite
- **Backend:** FastAPI (Python), runs on Uvicorn
- **Desktop:** Electron wraps the frontend and communicates with backend via HTTP

### Making Changes

1. **Frontend changes:** Edit files in `frontend/src/` - changes hot-reload automatically
2. **Backend changes:** Edit files in `backend/` - Uvicorn auto-reloads on file changes
3. **Restart required:** Changes to `electron.js` or `package.json` require restarting `npm run dev`

### Environment Variables

You can set API keys via environment variables (useful for development):

```bash
export REPLICATE_API_TOKEN="your-token"
export ELEVENLABS_API_KEY="your-key"
export WAVESPEED_API_KEY="your-key"
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
export GOOGLE_CLOUD_PROJECT="your-project-id"
export VERTEX_LOCATION="us-central1"
export VERTEX_TEMP_BUCKET="your-bucket-name"
```

These will be automatically loaded if not set in the UI.

## Contributing

This is an open-source project. Contributions are welcome!

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

TBD by repository owner.

## Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Check existing issues for solutions
- Review the troubleshooting section above

---

**Note:** This application requires internet connectivity to use AI generation features. All API keys and credentials are stored locally on your machine and never transmitted except to the respective AI service providers.
