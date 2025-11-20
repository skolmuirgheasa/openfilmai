# Multi-Character Lip-Sync Implementation Guide

## Overview
The Multi-Character Lip-Sync feature allows you to precisely assign audio tracks to specific characters in a single image, preventing multiple characters from mouthing the same words simultaneously.

## Current Implementation Status

### ✅ Completed (UI Layer)
1. **Multi-Character Lip-Sync Dialog**
   - Button added to main toolbar
   - Image selection with thumbnail grid
   - Character bounding box management
   - Audio track assignment per character
   - Visual bounding box overlay on image
   - Input fields for X, Y, Width, Height (as % of image)
   - Audio preview for each assigned track
   - Validation (all characters must have audio assigned)

2. **Data Structure**
   ```typescript
   type CharacterBoundingBox = {
     character_id: string;
     character_name: string;
     x: number;              // percentage 0-100
     y: number;              // percentage 0-100
     width: number;          // percentage 0-100
     height: number;         // percentage 0-100
     audio_track_id: string; // media ID of assigned audio
   };
   ```

3. **API Payload Format**
   ```json
   {
     "project_id": "vampyre",
     "image_path": "project_data/vampyre/media/images/scene.png",
     "characters": [
       {
         "character_id": "char_1",
         "character_name": "Ruthven",
         "audio_path": "project_data/vampyre/media/audio/ruthven_line1.mp3",
         "bounding_box": {
           "x": 25,
           "y": 20,
           "width": 20,
           "height": 30
         }
       },
       {
         "character_id": "char_2",
         "character_name": "Aubrey",
         "audio_path": "project_data/vampyre/media/audio/aubrey_line1.mp3",
         "bounding_box": {
           "x": 60,
           "y": 25,
           "width": 18,
           "height": 28
         }
       }
     ],
     "prompt": "subtle mouth movements, natural expressions",
     "filename": "scene_01_dialogue"
   }
   ```

### ⚠️ Needs Implementation (Backend/API Layer)

The backend endpoint `/ai/lipsync/multi-character` is currently a **placeholder** that returns an error. To fully implement this feature, you need to:

## Implementation Options

### Option 1: WaveSpeed InfiniteTalk Multi-Person API (Recommended if available)
If WaveSpeed supports multi-person lip-sync natively:

1. **Research WaveSpeed API Documentation**
   - Check if `https://api.wavespeed.ai/api/v3/wavespeed-ai/infinitetalk/multi-person` exists
   - Look for parameters like `masks`, `bounding_boxes`, or `speaker_mapping`
   - Understand how to pass multiple audio tracks

2. **Update `ai_porting_bundle/providers/wavespeed.py`**
   ```python
   def generate_multi_person(self, image_path, characters, prompt=None, **kwargs):
       """
       Generate multi-person lip-sync with character-specific audio mapping
       
       Args:
           image_path: Path to reference image
           characters: List of dicts with character_id, audio_path, bounding_box
           prompt: Optional prompt for lip-sync style
       """
       # Build payload according to WaveSpeed multi-person API spec
       payload = {
           "image": self._file_to_data_url(image_path, "image/jpeg"),
           "characters": [
               {
                   "audio": self._file_to_data_url(char["audio_path"], "audio/mpeg"),
                   "mask": char["bounding_box"],  # or however WaveSpeed expects it
                   "character_id": char["character_id"]
               }
               for char in characters
           ],
           "prompt": prompt or ""
       }
       # Submit and poll for result
   ```

3. **Update Backend Endpoint**
   Replace the placeholder in `backend/main.py` with actual implementation:
   ```python
   def _run_multi_character_job(job_id: str, req: MultiCharacterLipSyncRequest):
       try:
           update_job(job_id, status="running", progress=10, message="Processing multi-character lip-sync...")
           prov = _wavespeed_provider()
           
           img = Path(req.image_path)
           if not img.is_absolute():
               img = Path.cwd() / req.image_path
           
           # Prepare character data with absolute paths
           characters = []
           for char in req.characters:
               aud = Path(char["audio_path"])
               if not aud.is_absolute():
                   aud = Path.cwd() / char["audio_path"]
               characters.append({
                   "character_id": char["character_id"],
                   "character_name": char["character_name"],
                   "audio_path": str(aud),
                   "bounding_box": char["bounding_box"]
               })
           
           update_job(job_id, progress=20, message="Uploading to WaveSpeed (may take 10-45 min)...")
           tmp = prov.generate_multi_person(
               image_path=str(img),
               characters=characters,
               prompt=req.prompt
           )
           
           update_job(job_id, progress=90, message="Saving result...")
           item = _save_video_to_media(req.project_id, tmp, req.filename)
           
           update_job(job_id, status="completed", progress=100, result=item)
       except Exception as e:
           logger.error(f"Multi-character lip-sync error: {e}")
           update_job(job_id, status="failed", error=str(e))
   ```

### Option 2: Composite Approach (If WaveSpeed doesn't support multi-person)
If WaveSpeed only supports single-person lip-sync:

1. **Generate Each Character Separately**
   - For each character, generate lip-sync video with their audio
   - Use the bounding box to crop the result

2. **Composite Using FFmpeg**
   - Start with the original image
   - Overlay each character's lip-synced video at their bounding box coordinates
   - Blend/mask to make it seamless

3. **Implementation Steps**
   ```python
   def _run_multi_character_job(job_id: str, req: MultiCharacterLipSyncRequest):
       # 1. Generate lip-sync for each character separately
       character_videos = []
       for i, char in enumerate(req.characters):
           update_job(job_id, progress=10 + (i * 60 // len(req.characters)), 
                     message=f"Processing {char['character_name']}...")
           
           # Generate single-character lip-sync
           tmp_video = prov.generate(
               image_path=req.image_path,
               audio_path=char["audio_path"],
               prompt=req.prompt
           )
           character_videos.append({
               "video": tmp_video,
               "bbox": char["bounding_box"]
           })
       
       # 2. Composite all characters using FFmpeg
       update_job(job_id, progress=80, message="Compositing characters...")
       final_video = composite_character_videos(
           base_image=req.image_path,
           character_videos=character_videos
       )
       
       # 3. Save result
       item = _save_video_to_media(req.project_id, final_video, req.filename)
       update_job(job_id, status="completed", result=item)
   ```

### Option 3: Speaker Separation + Masks
If you have a single audio file with multiple speakers:

1. **Use Audio Separation**
   - Use a tool like Spleeter or Demucs to separate speakers
   - Or manually provide pre-separated audio tracks

2. **Apply Masks**
   - Create masks for each character region
   - Apply lip-sync only to masked regions

## Required Research

Before implementing, you need to:

1. **Check WaveSpeed Documentation**
   - Visit https://wavespeed.ai/docs or https://api.wavespeed.ai/docs
   - Look for "multi-person", "multiple characters", "speaker separation", or "bounding box" features
   - Check if there's a `/infinitetalk/multi-person` endpoint

2. **Test WaveSpeed API**
   - Make a test request with multiple bounding boxes
   - See if the API accepts arrays of audio tracks
   - Verify the response format

3. **Alternative APIs**
   - If WaveSpeed doesn't support multi-person, consider:
     - Wav2Lip with custom masking
     - SadTalker with region control
     - Custom FFmpeg compositing pipeline

## Usage Workflow

Once implemented, users will:

1. **Open Multi-Character Lip-Sync dialog**
2. **Select reference image** (group shot with multiple characters)
3. **For each character:**
   - Click "+ Add Character" (with character selected)
   - Adjust bounding box coordinates (X, Y, Width, Height as %)
   - Assign audio track to that character
4. **Add optional prompt** for lip-sync style
5. **Click "Generate Multi-Character Lip-Sync"**
6. **Wait for processing** (10-45 minutes depending on complexity)
7. **Result**: Single video with all characters lip-synced to their respective audio

## Benefits

- **Prevents cross-talk**: Each character only mouths their own words
- **Precise control**: Exact bounding boxes for each character
- **Organized workflow**: Clear visual mapping of audio to characters
- **Reusable**: Save character positions for multiple takes

## Next Steps

1. Research WaveSpeed InfiniteTalk multi-person API capabilities
2. If supported: Implement Option 1 (native multi-person)
3. If not supported: Implement Option 2 (composite approach)
4. Test with 2-3 character scenes
5. Optimize for performance and quality
6. Add visual bounding box drawing tool (drag to create boxes on image)

## Notes

- Current UI is fully functional and ready to use once backend is implemented
- Bounding boxes are stored as percentages (0-100) for resolution independence
- All validation is in place (image required, all characters need audio)
- Job tracking and progress updates are already wired up

