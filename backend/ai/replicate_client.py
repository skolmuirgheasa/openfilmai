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
        """
        Generate video using Replicate. Supports various video models.
        
        Supported models:
        - google/veo-3.1: Start/end frames, no reference images
        - kwaivgi/kling-v2.5-turbo-pro: Start/end frames, no reference images
        """
        owner, name = model.split("/", 1) if "/" in model else ("google", "veo-3.1")
        url = f"https://api.replicate.com/v1/models/{owner}/{name}/predictions"

        inputs: Dict[str, object] = {"prompt": prompt}
        
        # Model-specific parameter handling
        if "kling" in model.lower():
            # Kling models (v1.6, v2.1, v2.5) use specific parameter names
            # Based on API docs: https://replicate.com/kwaivgi/kling-v1.6-pro/api/schema
            if first_frame_image:
                inputs["image"] = self._to_data_url(first_frame_image)
                print(f"[REPLICATE] Kling: Added image (start frame)")
            if last_frame_image:
                inputs["last_frame"] = self._to_data_url(last_frame_image)
                print(f"[REPLICATE] Kling: Added last_frame")
            # Kling v1.6 params - being conservative with what we send
            # Only duration is confirmed to work across Kling models
            if duration:
                inputs["duration"] = duration
            # Note: aspect_ratio and mode parameters may vary by model version
            # Only add them if we're sure the model supports them
            print(f"[REPLICATE] Kling model: {model}, duration: {duration}")
        elif "seedance" in model.lower():
            # ByteDance Seedance-1-Pro
            # API: https://replicate.com/bytedance/seedance-1-pro/api/schema
            if first_frame_image:
                inputs["image"] = self._to_data_url(first_frame_image)
                print(f"[REPLICATE] Seedance: Added image (start frame)")
            if last_frame_image:
                inputs["last_frame_image"] = self._to_data_url(last_frame_image)
                print(f"[REPLICATE] Seedance: Added last_frame_image")
            # Seedance params
            inputs["duration"] = duration  # 2-12 seconds, default 5
            inputs["resolution"] = resolution  # Default "1080p"
            inputs["aspect_ratio"] = aspect_ratio  # Default "16:9"
            inputs["fps"] = 24  # Default frame rate
            print(f"[REPLICATE] Seedance model: {model}, duration: {duration}, resolution: {resolution}")
        else:
            # Generic video model (Veo, etc)
            if first_frame_image:
                inputs["image"] = self._to_data_url(first_frame_image)
            if last_frame_image:
                inputs["last_frame"] = self._to_data_url(last_frame_image)
            # Note: reference_images ignored for models that don't support them
            inputs["duration"] = duration
            inputs["resolution"] = resolution
            inputs["aspect_ratio"] = aspect_ratio
            inputs["generate_audio"] = bool(generate_audio)

        # Log the full request for debugging
        request_payload = {"input": inputs}
        print(f"[REPLICATE] Full video request payload: {request_payload}")
        print(f"[REPLICATE] URL: {url}")
        
        try:
            r = requests.post(url, headers=self._headers(), json=request_payload, timeout=self.timeout)
            r.raise_for_status()
        except requests.exceptions.HTTPError as http_err:
            # Capture and log the full error response from Replicate
            error_body = r.text if hasattr(r, 'text') else str(http_err)
            print(f"[REPLICATE] HTTP Error {r.status_code}: {error_body}")
            try:
                error_json = r.json()
                print(f"[REPLICATE] Error JSON: {error_json}")
                if 'detail' in error_json:
                    raise RuntimeError(f"Replicate API Error: {error_json['detail']}")
            except:
                pass
            raise RuntimeError(f"Replicate API HTTP {r.status_code}: {error_body}")
        
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
            # Seedream-4 specific parameters (from actual API docs)
            if aspect_ratio:
                inputs["aspect_ratio"] = aspect_ratio
            if num_outputs is not None:
                # Seedream-4 uses "max_images" not "num_outputs"
                inputs["max_images"] = num_outputs
            # Reference images for Seedream-4
            # API uses "image_input" (array) not "reference_images"
            if reference_images and len(reference_images) > 0:
                inputs["image_input"] = [self._to_data_url(p) for p in reference_images]
                print(f"[REPLICATE] Sending {len(reference_images)} reference image(s) to Seedream-4 via 'image_input'")
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

        # Log the full request for debugging
        request_payload = {"input": inputs}
        print(f"[REPLICATE] Full request payload: {request_payload}")
        
        r = requests.post(url, headers=self._headers(), json=request_payload, timeout=self.timeout)
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


