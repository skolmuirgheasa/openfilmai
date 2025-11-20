# Video Generation Model Parameters

This document lists all supported parameters for each video generation model in OpenFilm AI.

## Replicate Models

### Google Veo 3.1 (`google/veo-3.1`)
- **Duration**: 2-10 seconds (default: 8)
- **Resolution**: 1080p
- **Aspect Ratio**: 16:9, 9:16
- **Start Frame**: ✅ Supported (image input)
- **End Frame**: ✅ Supported (last_frame input)
- **Reference Images**: ❌ Not supported (mutually exclusive with start/end frames)
- **Generate Audio**: ✅ Supported (costs extra)
- **Character Integration**: Via start/end frames only

**API Parameters**:
```json
{
  "prompt": "string",
  "image": "data:image/jpeg;base64,...",  // start frame
  "last_frame": "data:image/jpeg;base64,...",  // end frame
  "duration": 8,
  "resolution": "1080p",
  "aspect_ratio": "16:9",
  "generate_audio": false
}
```

---

### Kling v1.6 Pro (`kwaivgi/kling-v1.6-pro`)
- **Duration**: 2-10 seconds (default: 8)
- **Resolution**: 1080p
- **Aspect Ratio**: 16:9, 9:16
- **Start Frame**: ✅ Supported (image input)
- **End Frame**: ✅ Supported (last_frame input)
- **Reference Images**: ❌ Not supported
- **Generate Audio**: ❌ Not supported
- **Character Integration**: Via start frame only

**API Parameters**:
```json
{
  "prompt": "string",
  "image": "data:image/jpeg;base64,...",  // start frame
  "last_frame": "data:image/jpeg;base64,...",  // end frame
  "duration": 8
}
```

**Notes**:
- Kling models are conservative with parameters
- Only duration is confirmed across all Kling versions
- Aspect ratio and mode parameters may vary by version

---

### ByteDance Seedance-1-Pro (`bytedance/seedance-1-pro`)
- **Duration**: 2-12 seconds (default: 5) ⭐ **Longest duration support**
- **Resolution**: 1080p
- **Aspect Ratio**: 16:9, 9:16
- **Start Frame**: ✅ Supported (image input)
- **End Frame**: ✅ Supported (last_frame_image input)
- **Reference Images**: ❌ Not supported
- **Generate Audio**: ❌ Not supported
- **FPS**: 24 (default)
- **Character Integration**: Via start frame only

**API Parameters**:
```json
{
  "prompt": "string",
  "image": "data:image/jpeg;base64,...",  // start frame
  "last_frame_image": "data:image/jpeg;base64,...",  // end frame
  "duration": 5,
  "resolution": "1080p",
  "aspect_ratio": "16:9",
  "fps": 24
}
```

**Notes**:
- **Best for longer videos** (up to 12 seconds)
- Uses `last_frame_image` instead of `last_frame`
- Fixed 24 FPS output

---

## Vertex AI Models

### Vertex Veo 3.1 Fast (`veo-3.1-fast-generate-preview`)
- **Duration**: 2-10 seconds (default: 8)
- **Resolution**: 1080p
- **Aspect Ratio**: 16:9, 9:16
- **Start Frame**: ✅ Supported (image.gcsUri)
- **End Frame**: ✅ Supported (lastFrame.gcsUri)
- **Reference Images**: ⚠️ Mutually exclusive with start/end frames
- **Generate Audio**: ✅ Supported (addAudio parameter)
- **Character Integration**: Via reference images OR start/end frames (not both)

**API Parameters**:
```json
{
  "instance": {
    "prompt": "string",
    "image": {
      "gcsUri": "gs://bucket/start.jpg",
      "mimeType": "image/jpeg"
    },
    "lastFrame": {
      "gcsUri": "gs://bucket/end.jpg",
      "mimeType": "image/jpeg"
    },
    "aspectRatio": "16:9"
  },
  "parameters": {
    "sampleCount": 1,
    "addAudio": false
  }
}
```

**Important Rules**:
1. **Mutual Exclusivity**: Cannot use reference images AND start/end frames together
2. **Frame Interpolation**: End frame requires start frame (cannot use end frame alone)
3. **GCS Bucket Required**: Must configure `vertex_temp_bucket` in settings
4. **Service Account**: Needs `storage.objectAdmin` role on the bucket

---

## Image Generation Models

### ByteDance Seedream-4 (`bytedance/seedream-4`)
- **Aspect Ratios**: 4:3, 16:9, 21:9, 1:1, 2:3, 3:2, 9:16, 9:21
- **Num Outputs**: 1-4 images per request
- **Reference Images**: ✅ Supported (for character consistency)
- **Character Integration**: Via reference images

**API Parameters**:
```json
{
  "prompt": "string",
  "aspect_ratio": "16:9",
  "num_outputs": 1
}
```

---

## Parameter Comparison Table

| Model | Duration Range | Audio | Start Frame | End Frame | Ref Images | Best For |
|-------|---------------|-------|-------------|-----------|------------|----------|
| **Veo 3.1** (Replicate) | 2-10s | ✅ | ✅ | ✅ | ❌ | High quality, audio |
| **Veo 3.1** (Vertex) | 2-10s | ✅ | ✅ | ✅ | ⚠️ | Enterprise, GCP integration |
| **Kling v1.6 Pro** | 2-10s | ❌ | ✅ | ✅ | ❌ | Fast generation |
| **Seedance-1-Pro** | **2-12s** | ❌ | ✅ | ✅ | ❌ | **Longest videos** |
| **Seedream-4** | N/A (image) | N/A | ❌ | ❌ | ✅ | Character portraits |

---

## Backend Implementation

All models are handled in `backend/ai/replicate_client.py` and `backend/ai/vertex_client.py`:

### Replicate Client
```python
def generate_video(
    model: str,
    prompt: str,
    first_frame_image: Optional[str] = None,
    last_frame_image: Optional[str] = None,
    reference_images: Optional[list] = None,
    duration: int = 8,  # ✅ Custom duration support
    resolution: str = "1080p",
    aspect_ratio: str = "16:9",
    generate_audio: bool = True,
) -> str:
```

### Vertex Client
```python
def generate_video(
    prompt: str,
    first_frame_image: Optional[str] = None,
    last_frame_image: Optional[str] = None,
    reference_images: Optional[List[str]] = None,
    duration: int = 8,  # ✅ Custom duration support
    resolution: str = "1080p",
    aspect_ratio: str = "16:9",
    generate_audio: bool = False,
) -> str:
```

---

## Frontend UI

Duration field is in the Generate Shot dialog:
- **Input Type**: Number
- **Default**: 8 seconds
- **Min**: 2 seconds
- **Max**: 10 seconds (12 for Seedance)
- **Tooltip**: Shows model-specific limits

---

## Testing Recommendations

1. **Test Seedance for long videos** (10-12 seconds)
2. **Test Veo for audio generation** (enable "Generate audio")
3. **Test continuity** with start/end frames across models
4. **Test character integration** with reference images (Vertex only)
5. **Verify duration limits** are enforced per model

---

## Future Enhancements

- [ ] Add resolution options (720p, 4K)
- [ ] Add FPS control for Seedance
- [ ] Add style parameters for Kling
- [ ] Add seed parameter for reproducibility
- [ ] Add negative prompts support
- [ ] Add motion control parameters
- [ ] Add camera movement presets

