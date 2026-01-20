import os
import time
import base64
import json
import requests
from typing import Optional, Dict, Any, List


class VertexClient:
    """Minimal Vertex Veo 3.1 client using predictLongRunning + polling."""

    def __init__(
        self,
        credentials_path: str,
        project_id: str,
        location: str = "us-central1",
        model: str = "veo-3.1-fast-generate-preview",
        temp_bucket: str | None = None,
        timeout: int = 60,
    ):
        self.credentials_path = credentials_path
        self.project_id = project_id
        self.location = location
        self.model = model
        self.temp_bucket = temp_bucket
        self.timeout = timeout

    def _access_token(self) -> str:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
        creds = service_account.Credentials.from_service_account_file(
            self.credentials_path, scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        creds.refresh(Request())
        return creds.token

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token()}", "Content-Type": "application/json"}

    def _model_path(self) -> str:
        if self.model.startswith("publishers/"):
            return self.model
        # Strip google/ prefix if present (frontend sends google/veo-3.1, but API wants just veo-3.1-...)
        model_id = self.model
        if model_id.startswith("google/"):
            model_id = model_id[7:]  # Remove "google/" prefix
        # Map friendly names to actual Vertex model IDs
        model_map = {
            "veo-3.1": "veo-3.1-fast-generate-preview",
            "veo-3": "veo-3.1-fast-generate-preview",
            "veo-2": "veo-2.0-generate-001",
        }
        model_id = model_map.get(model_id, model_id)
        return f"publishers/google/models/{model_id}"

    def _upload_image_to_gcs(self, image_path: str) -> str:
        from google.cloud import storage
        from google.oauth2 import service_account
        credentials = service_account.Credentials.from_service_account_file(
            self.credentials_path, scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        client = storage.Client(project=self.project_id, credentials=credentials)
        # Use provided bucket if set; otherwise auto-provision a temp bucket
        bucket_name = self.temp_bucket or f"{self.project_id}-openfilmai-temp"
        try:
            bucket = client.get_bucket(bucket_name)
        except Exception:
            # Create bucket if missing (best-effort)
            bucket = client.bucket(bucket_name)
            bucket.location = self.location
            bucket = client.create_bucket(bucket)
        blob_name = f"frames/{int(time.time())}_{os.path.basename(image_path)}"
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(image_path)
        return f"gs://{bucket_name}/{blob_name}"

    def generate_video(
        self,
        prompt: str,
        first_frame_image: Optional[str] = None,
        last_frame_image: Optional[str] = None,
        reference_images: Optional[List[str]] = None,
        duration: int = 8,
        resolution: str = "1080p",
        aspect_ratio: str = "16:9",
        generate_audio: bool = False,
    ) -> str:
        base = "https://us-central1-aiplatform.googleapis.com/v1"
        url = f"{base}/projects/{self.project_id}/locations/{self.location}/{self._model_path()}:predictLongRunning"

        instance: Dict[str, Any] = {"prompt": prompt}

        # Veo 3.1 only supports start frame (image) and optionally end frame (lastFrame)
        # It does NOT support general reference images like NanoBanana does
        # If reference_images are provided but no start frame, use the FIRST ref as start frame
        actual_start_frame = first_frame_image
        if not actual_start_frame and reference_images and len(reference_images) > 0:
            actual_start_frame = reference_images[0]
            print(f"[VERTEX] No start_frame provided, using first reference image: {actual_start_frame}")

        if actual_start_frame:
            print(f"[VERTEX] Uploading start frame to GCS: {actual_start_frame}")
            gcs_uri = self._upload_image_to_gcs(actual_start_frame)
            instance["image"] = {"gcsUri": gcs_uri, "mimeType": "image/jpeg"}
            print(f"[VERTEX] Start frame uploaded: {gcs_uri}")
        else:
            print("[VERTEX] WARNING: No start frame or reference images provided - generating from prompt only")

        if last_frame_image:
            print(f"[VERTEX] Uploading end frame to GCS: {last_frame_image}")
            gcs_uri = self._upload_image_to_gcs(last_frame_image)
            instance["lastFrame"] = {"gcsUri": gcs_uri, "mimeType": "image/jpeg"}
            print(f"[VERTEX] End frame uploaded: {gcs_uri}")

        params: Dict[str, Any] = {"sampleCount": 1}
        
        # Add aspect ratio (Vertex AI Veo supports: "16:9", "9:16")
        if aspect_ratio:
            instance["aspectRatio"] = aspect_ratio
        
        # Try to explicitly disable audio where supported; unknown keys are ignored by API
        params["addAudio"] = bool(generate_audio)
        params["enableAudio"] = bool(generate_audio)
        body = {"instances": [instance], "parameters": params}
        
        # Log the request for debugging
        import json as json_mod
        print(f"[VERTEX] Sending request to: {url}")
        print(f"[VERTEX] Request body: {json_mod.dumps(body, indent=2)}")
        
        r = requests.post(url, headers=self._headers(), json=body, timeout=self.timeout)
        try:
            r.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print(f"[VERTEX] HTTP Error: {r.status_code}")
            print(f"[VERTEX] Response: {r.text}")
            raise
        op_name = r.json().get("name")
        if not op_name:
            raise RuntimeError(f"Vertex: no operation name: {r.text}")
        return self._poll_and_download(op_name)

    def plan_shot_from_video(
        self,
        video_path: str,
        scene_context: str,
        next_shot_info: Dict[str, Any],
        available_characters: List[Dict[str, Any]],
        visual_style: Optional[str] = None,
        character_ref_images: Optional[Dict[str, List[str]]] = None,
        scene_cast_ids: Optional[List[str]] = None,
        prior_shots_summary: Optional[List[str]] = None,
        additional_video_paths: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Watch a video and plan the complete next shot - refs, prompts, everything.

        This is the "AI Director" feature - Gemini watches the previous shot's video,
        understands the scene context, and plans exactly how to execute the next shot.

        Args:
            video_path: Path to the previous shot's video
            scene_context: Overall scene description
            next_shot_info: Dict with the planned shot's action, camera_angle, subject, dialogue, etc.
            available_characters: List of character dicts with name, reference_image_ids, style_tokens
            visual_style: Overall visual style notes
            character_ref_images: Dict mapping character names to their reference image paths
            scene_cast_ids: List of character IDs that are IN this scene's cast
            prior_shots_summary: List of summaries of prior shots for narrative context

        Returns:
            Complete shot execution plan
        """
        import mimetypes

        import os

        print("=" * 70)
        print("[GEMINI DIRECTOR] VIDEOS BEING SENT TO GEMINI FOR ANALYSIS")
        print("=" * 70)

        # Read and encode primary video (the immediately previous shot)
        print(f"\n--- PRIMARY VIDEO (immediately previous shot) ---")
        print(f"  Path: {video_path}")
        print(f"  Exists: {os.path.exists(video_path)}")
        if os.path.exists(video_path):
            file_size = os.path.getsize(video_path)
            print(f"  File size: {file_size} bytes ({file_size // 1024} KB)")
        mime_type = mimetypes.guess_type(video_path)[0] or "video/mp4"
        print(f"  MIME type: {mime_type}")
        with open(video_path, "rb") as f:
            video_data = base64.b64encode(f.read()).decode()
        print(f"  Base64 size: {len(video_data)} chars (~{len(video_data) * 3 // 4 // 1024} KB)")
        print(f"  Status: ✓ SUCCESSFULLY LOADED")

        # Read and encode additional context videos (earlier shots)
        additional_videos_data: List[Dict[str, str]] = []
        if additional_video_paths:
            print(f"\n--- ADDITIONAL CONTEXT VIDEOS ({len(additional_video_paths)}) ---")
            for idx, add_path in enumerate(additional_video_paths):
                print(f"\n  Context Video #{idx + 1}:")
                print(f"    Path: {add_path}")
                print(f"    Exists: {os.path.exists(add_path)}")
                try:
                    if os.path.exists(add_path):
                        file_size = os.path.getsize(add_path)
                        print(f"    File size: {file_size} bytes ({file_size // 1024} KB)")
                    add_mime = mimetypes.guess_type(add_path)[0] or "video/mp4"
                    print(f"    MIME type: {add_mime}")
                    with open(add_path, "rb") as f:
                        add_data = base64.b64encode(f.read()).decode()
                    print(f"    Base64 size: {len(add_data)} chars (~{len(add_data) * 3 // 4 // 1024} KB)")
                    print(f"    Status: ✓ SUCCESSFULLY LOADED")
                    additional_videos_data.append({"mime": add_mime, "data": add_data, "path": add_path})
                except Exception as e:
                    print(f"    Status: ✗ FAILED - {e}")
        else:
            print(f"\n  No additional context videos requested")

        # Use Gemini 2.0 Flash for video analysis
        url = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{self.project_id}/locations/{self.location}/publishers/google/models/gemini-2.0-flash-001:generateContent"

        # Build character info string with scene cast indication
        char_info = []
        scene_cast_ids = scene_cast_ids or []
        character_ref_images = character_ref_images or {}
        for c in available_characters:
            char_name = c.get('name', 'Unknown')
            char_id = c.get('character_id', '')
            in_scene = char_id in scene_cast_ids
            char_str = f"- {char_name}"
            if in_scene:
                char_str += " [IN THIS SCENE]"
            if c.get('style_tokens'):
                char_str += f": {c['style_tokens']}"
            # Note if we have reference images for this character
            if char_name in character_ref_images:
                char_str += f" (REFERENCE IMAGES PROVIDED BELOW - study them carefully!)"
            char_info.append(char_str)
        characters_str = "\n".join(char_info) if char_info else "No characters defined"

        # Build prior shots summary string
        prior_shots_str = ""
        if prior_shots_summary:
            prior_shots_str = "\n\nPRIOR SHOTS IN THIS SCENE (for narrative context):\n" + "\n".join(prior_shots_summary)

        system_prompt = """You are an expert AI film director writing prompts for AI image and video generation.

## CRITICAL: AI Models Have NO MEMORY
The image generator and video generator are SEPARATE AI models with NO shared context.
- They don't know character names
- They don't remember previous shots
- They ONLY see: your text prompt + reference images

EVERY prompt you write must be COMPLETELY SELF-CONTAINED with full visual descriptions.

## CRITICAL: Understanding Reference Images
Reference images STRONGLY influence the output. The AI will try to recreate elements from them.

**PROBLEM**: If a reference image shows a character in a SPECIFIC LOCATION (by a window, in a bedroom),
the AI will try to put them in that same location, FIGHTING against your prompt's positioning.

**SOLUTION**: When writing prompts, be aware of what's in the reference images:
- If the ref shows a character in a location, acknowledge it but OVERRIDE it in your prompt
- Be EXTRA explicit about the NEW position: "NOW standing in the center of the room" (not near the window as in ref)
- Describe the character's appearance and costume, then place them in the SHOT's location

**IDEAL REFERENCE IMAGES**: Show only the character's appearance/costume on a NEUTRAL background.
If the user needs to generate new character reference images, suggest prompts like:
"Full body portrait of [character description] wearing [costume], standing against a plain neutral gray studio background, soft even lighting, no background elements, costume reference photograph"

## MOST IMPORTANT: EXACT SPATIAL POSITIONING
The #1 goal is CONTINUITY. Watch the video carefully and note:
- WHERE exactly is each character in frame? (left third, center, right side, foreground, background)
- What direction are they facing? (toward camera, away, profile left/right, 3/4 view)
- What are their body positions? (standing, sitting, leaning, distance from each other)
- What are they next to? (door, window, furniture, other characters)
- Scene geography: if someone was at the window, they should still be near the window

Your prompts MUST specify exact positions like:
"standing on the left side of frame, facing right toward the door"
"seated in the foreground left, turned 3/4 toward camera"
"in the background center, near the bookshelf"

## How to Write Prompts

BAD (model doesn't know who "John" is or where he should be):
"John walks to the door"

GOOD (full visual description WITH EXACT POSITION):
"A tall man in his 30s with short brown hair, wearing a gray suit (matching the person in the reference images), positioned in the right third of frame near a wooden door. He faces the door with his back partially to camera. His expression is neutral, mouth closed."

For EVERY character mentioned, include:
- Age/build description
- Hair color/style
- Current clothing/costume
- EXACT POSITION in frame (left/center/right, foreground/background)
- FACING DIRECTION (toward camera, away, profile, etc.)
- "(matching the appearance in reference images)" - focus on APPEARANCE, not location
- Current expression (mouth closed - no speaking)

## Shot Types (This is a CUT, not a continuation)
- The previous video shows where characters ARE
- Your prompts describe a NEW CAMERA ANGLE viewing the same moment
- Think: wide shot → cut to close-up → cut to reaction shot
- CHARACTERS STAY IN THE SAME RELATIVE POSITIONS even when camera angle changes

## No Lip Movement
- ALL characters must have CLOSED MOUTHS
- Never describe speaking or talking
- Dialogue is added via lip-sync AFTER video generation
- Characters can react, gesture, move - but mouths stay closed

## Image vs Video Prompts
- IMAGE PROMPT: Describe a single frozen moment - composition, lighting, character positions WITH EXACT PLACEMENT
- VIDEO PROMPT: Describe the motion/action - but still include full character descriptions AND their starting positions!"""

        # Build context about videos being provided
        video_context_note = ""
        if additional_videos_data:
            video_context_note = f"\nIMPORTANT: You have been provided {len(additional_videos_data)} earlier shot video(s) for additional narrative context, followed by the immediately previous shot (Shot N). Watch all videos to understand the scene's flow."

        user_content = f"""Watch the video clip(s) carefully, analyzing them frame by frame.
Note: The LAST video shown is SHOT N. You are planning SHOT N+1, which is typically a CUT to a DIFFERENT ANGLE.{video_context_note}

SCENE CONTEXT:
{scene_context}

VISUAL STYLE:
{visual_style or 'Not specified'}

AVAILABLE CHARACTERS:
{characters_str}
{prior_shots_str}

PLANNED NEXT SHOT (Shot N+1):
- Camera Angle: {next_shot_info.get('camera_angle', 'Not specified')}
- Subject: {next_shot_info.get('subject', 'Not specified')}
- Action: {next_shot_info.get('action', 'Not specified')}
- Dialogue: {next_shot_info.get('dialogue', 'None')} (NOTE: Do NOT show lip movement - dialogue added via lip-sync later)
- Original Prompt: {next_shot_info.get('prompt', next_shot_info.get('prompt_suggestion', 'Not specified'))}

Based on watching this video, create a SHOT EXECUTION PLAN.
Remember: Shot N+1 is a CUT to "{next_shot_info.get('camera_angle', 'new angle')}" - NOT a continuation of Shot N.

Return a JSON object with these exact fields:
{{
  "video_end_state": "Detailed description of final frames - WHERE EXACTLY are characters positioned (left/center/right, foreground/background)? What direction are they facing? What are they next to? What's the lighting?",

  "character_positions": [
    {{"name": "Character Name", "position": "left third of frame, foreground", "facing": "toward the door on the right", "near": "standing beside the wooden table"}}
  ],

  "characters_in_shot": ["Array of character names that should appear in Shot N+1"],

  "use_prev_last_frame": false,

  "image_prompt": "COMPLETE standalone prompt. MUST include for EACH character: (1) full appearance description, (2) EXACT position in frame (left/center/right, foreground/background), (3) facing direction, (4) what they're near, (5) '(as shown in reference images)'. Example: 'Medium shot of a Victorian bedroom. On the left side of frame, a young woman in her 20s with auburn wavy hair, fair complexion, wearing a cream-colored Victorian nightgown (as shown in reference images), sits in a wooden chair facing right toward the bed. In the center-right of frame, a pale young man lies in the ornate bed, facing toward her. Soft golden morning light streams through a window on the left. Photorealistic, 35mm film, cinematic lighting.'",

  "video_prompt": "COMPLETE standalone prompt. MUST REPEAT full character descriptions WITH POSITIONS - the video model has NO memory! Include starting positions and movement. Example: 'In a Victorian bedroom, on the left side of frame a young woman in her 20s with auburn hair, cream nightgown (as shown in reference images), sits in a chair. She slowly leans forward and reaches her right hand toward a pale young man lying in the bed on the right side of frame. Her expression shifts from concern to hope, mouth remaining closed. Soft morning light. Cinematic, smooth motion.'",

  "continuity_notes": "What MUST match: exact character positions (who is where in frame), facing directions, wardrobe, lighting direction, time of day, scene geography",

  "reasoning": "Brief explanation - what type of cut is this? Why this angle?"
}}

CRITICAL REMINDERS:
1. image_prompt and video_prompt go to DIFFERENT AI models with NO shared memory
2. BOTH prompts must include: appearance + EXACT POSITION + facing direction + nearby objects
3. Never use just a character name - always describe their appearance AND where they are
4. Include "(as shown in reference images)" for each character
5. POSITIONS ARE CRITICAL: if someone was "on the left side near the window" they must still be "on the left side near the window" """

        # Build parts array: context videos first (oldest to newest), then character reference images, then text prompt
        parts = []

        # Add additional context videos first (earlier shots for narrative context)
        if additional_videos_data:
            for i, vid_info in enumerate(additional_videos_data):
                parts.append({"text": f"\n--- EARLIER SHOT VIDEO #{i+1} (for narrative context) ---"})
                parts.append({"inlineData": {"mimeType": vid_info["mime"], "data": vid_info["data"]}})

        # Add the primary video (immediately previous shot - this is what Shot N+1 follows)
        parts.append({"text": "\n--- IMMEDIATELY PREVIOUS SHOT (Shot N) - Your new shot follows this ---"})
        parts.append({"inlineData": {"mimeType": mime_type, "data": video_data}})

        # Add character reference images with labels
        print(f"\n--- CHARACTER REFERENCE IMAGES ---")
        if not character_ref_images:
            print("  No character reference images provided")
        ref_image_count = 0
        for char_name, image_paths in character_ref_images.items():
            print(f"\n  Character: {char_name}")
            for i, img_path in enumerate(image_paths):
                print(f"    Ref #{i+1}: {img_path}")
                print(f"      Exists: {os.path.exists(img_path)}")
                try:
                    if os.path.exists(img_path):
                        file_size = os.path.getsize(img_path)
                        print(f"      File size: {file_size} bytes ({file_size // 1024} KB)")
                    img_mime = mimetypes.guess_type(img_path)[0] or "image/jpeg"
                    with open(img_path, "rb") as f:
                        img_data = base64.b64encode(f.read()).decode()
                    print(f"      Base64 size: {len(img_data)} chars (~{len(img_data) * 3 // 4 // 1024} KB)")
                    print(f"      Status: ✓ LOADED")
                    # Add label text before image
                    parts.append({"text": f"\n--- REFERENCE IMAGE for {char_name} (#{i+1}) ---"})
                    parts.append({"inlineData": {"mimeType": img_mime, "data": img_data}})
                    ref_image_count += 1
                except Exception as e:
                    print(f"      Status: ✗ FAILED - {e}")

        # Add the main text prompt at the end
        parts.append({"text": user_content})

        body = {
            "contents": [
                {
                    "role": "user",
                    "parts": parts
                }
            ],
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "generationConfig": {
                "temperature": 0.4,
                "maxOutputTokens": 4096
            }
        }

        total_videos = 1 + len(additional_videos_data)
        total_video_kb = (len(video_data) * 3 // 4 // 1024) + sum(len(v["data"]) * 3 // 4 // 1024 for v in additional_videos_data)

        print("\n" + "=" * 70)
        print("[GEMINI DIRECTOR] SUMMARY - SENDING TO GEMINI API")
        print("=" * 70)
        print(f"  Total videos: {total_videos}")
        print(f"    - Primary video: {video_path}")
        for v in additional_videos_data:
            print(f"    - Context video: {v['path']}")
        print(f"  Total video data: ~{total_video_kb} KB")
        print(f"  Character reference images: {ref_image_count}")
        for char_name, paths in character_ref_images.items():
            print(f"    - {char_name}: {len(paths)} image(s)")
        print(f"  API URL: {url}")
        print("=" * 70)
        print(f"[GEMINI DIRECTOR] Total video size: ~{total_video_kb} KB")

        # DUMP THE EXACT REQUEST STRUCTURE TO FILE (without base64 data)
        debug_body = {
            "contents": [{
                "role": "user",
                "parts": []
            }],
            "systemInstruction": body["systemInstruction"],
            "generationConfig": body["generationConfig"]
        }
        for part in parts:
            if "text" in part:
                debug_body["contents"][0]["parts"].append({"text": part["text"][:500] + "..." if len(part.get("text", "")) > 500 else part["text"]})
            elif "inlineData" in part:
                data_size = len(part["inlineData"]["data"])
                debug_body["contents"][0]["parts"].append({
                    "inlineData": {
                        "mimeType": part["inlineData"]["mimeType"],
                        "data": f"<BASE64 DATA: {data_size} chars, ~{data_size * 3 // 4 // 1024} KB>"
                    }
                })

        import json as json_mod
        debug_file = "/tmp/gemini_request_debug.json"
        with open(debug_file, "w") as f:
            json_mod.dump(debug_body, f, indent=2)
        print(f"\n[GEMINI DIRECTOR] FULL REQUEST DUMPED TO: {debug_file}")
        print(f"[GEMINI DIRECTOR] Run: cat {debug_file}")

        r = requests.post(url, headers=self._headers(), json=body, timeout=180)
        try:
            r.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print(f"[GEMINI DIRECTOR] HTTP Error: {r.status_code}")
            print(f"[GEMINI DIRECTOR] Response: {r.text}")
            raise RuntimeError(f"Gemini API error: {r.status_code} - {r.text}")

        data = r.json()

        # Extract the text response
        try:
            text_response = data["candidates"][0]["content"]["parts"][0]["text"]
            print(f"[GEMINI DIRECTOR] Response: {text_response[:1000]}...")

            # Parse JSON from response
            if "```json" in text_response:
                json_str = text_response.split("```json")[1].split("```")[0].strip()
            elif "```" in text_response:
                json_str = text_response.split("```")[1].split("```")[0].strip()
            else:
                json_str = text_response.strip()

            result = json.loads(json_str)
            return {
                "status": "ok",
                "video_end_state": result.get("video_end_state", ""),
                "characters_in_shot": result.get("characters_in_shot", []),
                "use_prev_last_frame": result.get("use_prev_last_frame", False),
                "image_prompt": result.get("image_prompt", ""),
                "video_prompt": result.get("video_prompt", ""),
                "continuity_notes": result.get("continuity_notes", ""),
                "reasoning": result.get("reasoning", "")
            }
        except (KeyError, json.JSONDecodeError, IndexError) as e:
            print(f"[GEMINI DIRECTOR] Parse error: {e}")
            print(f"[GEMINI DIRECTOR] Raw response: {data}")
            return {
                "status": "error",
                "error": f"Failed to parse Gemini response: {e}"
            }

    def _poll_and_download(self, operation_name: str) -> str:
        base = "https://us-central1-aiplatform.googleapis.com/v1"
        fetch_url = f"{base}/projects/{self.project_id}/locations/{self.location}/{self._model_path()}:fetchPredictOperation"
        headers = self._headers()
        for _ in range(120):
            time.sleep(5)
            rr = requests.post(fetch_url, headers=headers, json={"operationName": operation_name}, timeout=self.timeout)
            rr.raise_for_status()
            data = rr.json()
            if data.get("done"):
                if "error" in data:
                    raise RuntimeError(f"Vertex error: {data['error']}")
                resp = data.get("response", {})
                videos = resp.get("videos", [])
                if videos:
                    v = videos[0]
                    if "gcsUri" in v:
                        # Download with authorization and return a local file path
                        http_url = v["gcsUri"].replace("gs://", "https://storage.googleapis.com/")
                        out = f"/tmp/vertex_{int(time.time())}.mp4"
                        rr = requests.get(http_url, headers=self._headers(), stream=True, timeout=self.timeout)
                        rr.raise_for_status()
                        with open(out, "wb") as f:
                            for chunk in rr.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                        return out
                    if "bytesBase64Encoded" in v:
                        out = f"/tmp/vertex_{int(time.time())}.mp4"
                        with open(out, "wb") as f:
                            f.write(base64.b64decode(v["bytesBase64Encoded"]))
                        return out
                raise RuntimeError("Vertex: no video in response")
        raise RuntimeError("Vertex: operation timed out")


