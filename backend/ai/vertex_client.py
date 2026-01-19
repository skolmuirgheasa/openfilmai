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
        return f"publishers/google/models/{self.model}"

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
        
        # Veo 3.1 fast only supports start and/or end frames, not general reference images
        # reference_images parameter is accepted for API compatibility but ignored
        if first_frame_image:
            instance["image"] = {"gcsUri": self._upload_image_to_gcs(first_frame_image), "mimeType": "image/jpeg"}
        if last_frame_image:
            instance["lastFrame"] = {"gcsUri": self._upload_image_to_gcs(last_frame_image), "mimeType": "image/jpeg"}

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
        visual_style: Optional[str] = None
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

        Returns:
            Complete shot execution plan
        """
        import mimetypes

        # Read and encode video
        mime_type = mimetypes.guess_type(video_path)[0] or "video/mp4"
        with open(video_path, "rb") as f:
            video_data = base64.b64encode(f.read()).decode()

        # Use Gemini 2.0 Flash for video analysis
        url = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{self.project_id}/locations/{self.location}/publishers/google/models/gemini-2.0-flash-001:generateContent"

        # Build character info string
        char_info = []
        for c in available_characters:
            char_str = f"- {c.get('name', 'Unknown')}"
            if c.get('style_tokens'):
                char_str += f": {c['style_tokens']}"
            num_refs = len(c.get('reference_image_ids', []))
            char_str += f" ({num_refs} reference images available)"
            char_info.append(char_str)
        characters_str = "\n".join(char_info) if char_info else "No characters defined"

        system_prompt = """You are an expert AI film director planning shots for a PROFESSIONAL FILM with Hollywood-style editing.

## CRITICAL UNDERSTANDING: This is a CUT, not a continuation
Each shot in our shot list represents a DIFFERENT CAMERA ANGLE - like a Hollywood film edit.
- The next shot is typically a CUT TO a new angle (close-up, wide, OTS, etc.)
- It is NOT simply extending what was happening in the previous shot
- Think of classic film editing: wide shot → cut to close-up → cut to reaction shot
- The previous video's END STATE tells you WHERE characters are, but the NEXT SHOT shows them from a NEW ANGLE

## When to use prev_last_frame vs generate new:
- use_prev_last_frame=TRUE: Only when the SAME camera angle continues (rare)
- use_prev_last_frame=FALSE (DEFAULT): When cutting to a NEW angle (most cases)
  - Generate a fresh start frame showing the NEW camera angle
  - Characters should be in consistent positions/poses but viewed differently

## CRITICAL: No Lip Movement / No Dialogue
- ALL characters must have CLOSED MOUTHS or neutral expressions
- NEVER describe characters speaking, talking, or mouthing words
- Dialogue is added via lip-sync technology AFTER video generation
- Even if the shot plan mentions dialogue, show characters LISTENING or REACTING, not speaking

## How to Write Prompts for Reference Images
The AI will receive CHARACTER REFERENCE IMAGES. Your prompts MUST:
1. Describe the character visually (not just their name)
2. Reference their appearance from ref images
3. Include their current costume/state for this scene

GOOD: "A young man (Aubrey, as shown in reference images - pale, gaunt, dark curly hair) lies in bed..."
BAD: "Aubrey lies in bed..."

Be extremely specific and visual. Describe a SINGLE FROZEN MOMENT for images."""

        user_content = f"""Watch this video clip carefully, especially the FINAL FRAMES.
Note: This video is SHOT N. You are planning SHOT N+1, which is typically a CUT to a DIFFERENT ANGLE.

SCENE CONTEXT:
{scene_context}

VISUAL STYLE:
{visual_style or 'Not specified'}

AVAILABLE CHARACTERS:
{characters_str}

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
  "video_end_state": "Detailed description of final frames - WHERE are characters positioned? What are they doing? What's the lighting?",

  "characters_in_shot": ["Array of character names that should appear in Shot N+1"],

  "use_prev_last_frame": false (Usually false - we're cutting to a new angle. Only true if same angle continues),

  "image_prompt": "Complete prompt for the START FRAME of Shot N+1. This is a NEW CAMERA ANGLE showing the scene. Describe: the camera angle, the setting, each character's full appearance (for ref image matching), their pose (CLOSED MOUTH - no speaking), wardrobe, lighting. Example: 'Close-up of a young woman (as shown in reference images - auburn hair, fair complexion) sitting by a bed, her face showing concern, mouth closed in a neutral expression, soft window light from the left, photorealistic, 35mm film'",

  "video_prompt": "What motion/action happens in this shot. Remember: NO lip movement or speaking - characters react, move, gesture but mouths stay closed",

  "continuity_notes": "What MUST match between shots: character positions, wardrobe, lighting direction, time of day, background elements",

  "reasoning": "Brief explanation - what type of cut is this? Why this angle?"
}}"""

        body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"inlineData": {"mimeType": mime_type, "data": video_data}},
                        {"text": user_content}
                    ]
                }
            ],
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "generationConfig": {
                "temperature": 0.4,
                "maxOutputTokens": 4096
            }
        }

        print(f"[GEMINI DIRECTOR] Analyzing video: {video_path}")
        print(f"[GEMINI DIRECTOR] Video size: {len(video_data)} base64 chars (~{len(video_data) * 3 // 4 // 1024} KB)")

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
                "use_prev_last_frame": result.get("use_prev_last_frame", True),
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


