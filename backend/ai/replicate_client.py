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
        """Generate video using Replicate. Supports various video models."""
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

    def generate_image(
        self,
        model: str,
        prompt: str,
        reference_images: Optional[list] = None,
        aspect_ratio: Optional[str] = None,
        num_outputs: Optional[int] = None,
        **kwargs,
    ) -> list:
        """
        Generate image(s) using Replicate. Supports various image models.
        Returns a list of image URLs.
        
        For Seedream-4:
        - aspect_ratio: "4:3", "16:9", "21:9", "1:1", "2:3", "3:2", "9:16", "9:21"
        - num_outputs: number of images to generate (default 1)
        """
        owner, name = model.split("/", 1) if "/" in model else ("bytedance", "seedream-4")
        url = f"https://api.replicate.com/v1/models/{owner}/{name}/predictions"

        inputs: Dict[str, object] = {"prompt": prompt}
        
        # Model-specific handling
        if "seedream" in model.lower() or model == "bytedance/seedream-4":
            # Seedream-4 specific parameters
            if aspect_ratio:
                inputs["aspect_ratio"] = aspect_ratio
            if num_outputs is not None:
                inputs["num_outputs"] = num_outputs
            # Reference images for Seedream-4 (if supported)
            if reference_images:
                # Seedream-4 may support reference images, check model docs
                # For now, we'll add them if provided
                inputs["reference_image"] = self._to_data_url(reference_images[0]) if reference_images else None
        else:
            # Generic image model handling
            if aspect_ratio:
                inputs["aspect_ratio"] = aspect_ratio
            if reference_images:
                if len(reference_images) == 1:
                    inputs["image"] = self._to_data_url(reference_images[0])
                else:
                    inputs["reference_images"] = [self._to_data_url(p) for p in reference_images]
        
        # Add any additional kwargs
        inputs.update(kwargs)

        r = requests.post(url, headers=self._headers(), json={"input": inputs}, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        pred_id = data.get("id")
        if not pred_id:
            raise RuntimeError(f"Replicate did not return a prediction id: {data}")
        return self._poll_for_output_images(pred_id)

    def _poll_for_output(self, prediction_id: str, max_wait: int = 900, poll_interval: int = 5) -> str:
        """Poll for a single output (video or single image)."""
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

    def _poll_for_output_images(self, prediction_id: str, max_wait: int = 900, poll_interval: int = 5) -> list:
        """Poll for multiple image outputs (e.g., Seedream-4 can return multiple images)."""
        status_url = f"{self.base_predictions}/{prediction_id}"
        start = time.time()
        while time.time() - start < max_wait:
            rr = requests.get(status_url, headers=self._headers(), timeout=self.timeout)
            rr.raise_for_status()
            pj = rr.json()
            status = pj.get("status")
            if status == "succeeded":
                outputs = pj.get("output")
                if isinstance(outputs, list):
                    # Handle list of outputs - could be URLs or file objects
                    urls = []
                    for item in outputs:
                        if isinstance(item, str):
                            urls.append(item)
                        elif isinstance(item, dict):
                            # If it's a dict, try to get URL
                            urls.append(item.get("url", str(item)))
                        else:
                            urls.append(str(item))
                    return urls
                if isinstance(outputs, str):
                    return [outputs]
                raise RuntimeError(f"Replicate output missing: {pj}")
            if status in ("failed", "canceled"):
                raise RuntimeError(f"Replicate prediction {prediction_id} {status}: {pj.get('error') or pj}")
            time.sleep(poll_interval)
        raise RuntimeError("Replicate prediction timed out")


