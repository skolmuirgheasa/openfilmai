import os
import time
import base64
import requests
from typing import Dict, Optional


class ReplicateClient:
    """Minimal Replicate Predictions client using model aliases (no version IDs)."""

    def __init__(self, api_token: Optional[str] = None, timeout: int = 60):
        self.api_token = api_token or os.environ.get("REPLICATE_API_TOKEN") or os.environ.get("REPLICATE_API_KEY")
        self.timeout = timeout
        self.base_predictions = "https://api.replicate.com/v1/predictions"

    def _headers(self) -> Dict[str, str]:
        if not self.api_token:
            raise RuntimeError("Replicate API token not configured (set REPLICATE_API_TOKEN).")
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _to_data_url(path: str) -> str:
        mime = "image/png"
        low = path.lower()
        if low.endswith((".jpg", ".jpeg")):
            mime = "image/jpeg"
        elif low.endswith(".webp"):
            mime = "image/webp"
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f"data:{mime};base64,{b64}"

    def generate_video(
        self,
        model: str,
        prompt: str,
        first_frame_image: Optional[str] = None,
        last_frame_image: Optional[str] = None,
        reference_images: Optional[list] = None,
        duration: int = 8,
        resolution: str = "1080p",
        aspect_ratio: str = "16:9",
        generate_audio: bool = True,
    ) -> str:
        owner, name = model.split("/", 1) if "/" in model else ("google", "veo-3.1")
        url = f"https://api.replicate.com/v1/models/{owner}/{name}/predictions"

        inputs: Dict[str, object] = {"prompt": prompt}
        if first_frame_image:
            inputs["image"] = self._to_data_url(first_frame_image)
        if last_frame_image:
            inputs["last_frame"] = self._to_data_url(last_frame_image)
        if reference_images:
            inputs["reference_images"] = [self._to_data_url(p) for p in reference_images]
        inputs["duration"] = duration
        inputs["resolution"] = resolution
        inputs["aspect_ratio"] = aspect_ratio
        inputs["generate_audio"] = bool(generate_audio)

        r = requests.post(url, headers=self._headers(), json={"input": inputs}, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        pred_id = data.get("id")
        if not pred_id:
            raise RuntimeError(f"Replicate did not return a prediction id: {data}")
        return self._poll_for_output(pred_id)

    def _poll_for_output(self, prediction_id: str, max_wait: int = 900, poll_interval: int = 5) -> str:
        status_url = f"{self.base_predictions}/{prediction_id}"
        start = time.time()
        while time.time() - start < max_wait:
            rr = requests.get(status_url, headers=self._headers(), timeout=self.timeout)
            rr.raise_for_status()
            pj = rr.json()
            status = pj.get("status")
            if status == "succeeded":
                outputs = pj.get("output")
                if isinstance(outputs, list) and outputs:
                    return outputs[-1]
                if isinstance(outputs, str):
                    return outputs
                raise RuntimeError(f"Replicate output missing: {pj}")
            if status in ("failed", "canceled"):
                raise RuntimeError(f"Replicate prediction {prediction_id} {status}: {pj.get('error') or pj}")
            time.sleep(poll_interval)
        raise RuntimeError("Replicate prediction timed out")


