"""
Replicate API integration (Veo 3.1 and image models)
Docs: https://replicate.com/docs/reference/http#predictions.create
"""

import os
import time
from .base import AIProvider, AIProviderError
from classes.logger import log


class ReplicateProvider(AIProvider):
    """Replicate Predictions API"""

    BASE_URL = "https://api.replicate.com/v1/predictions"

    def generate(
        self,
        prompt,
        model="google/veo-3.1",
        first_frame_image=None,
        last_frame_image=None,
        reference_images=None,
        init_image=None,
        duration=8,
        resolution="1080p",
        aspect_ratio="16:9",
        generate_audio=True,
        output_path=None,
        **kwargs,
    ):
        if not self.api_key:
            raise AIProviderError("Replicate API key not set")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        inputs = {"prompt": prompt}
        if model.startswith("google/veo"):
            if first_frame_image:
                inputs["image"] = self._to_data_url_small(first_frame_image)
            if last_frame_image:
                inputs["last_frame"] = self._to_data_url_small(last_frame_image)
            if reference_images:
                refs = [self._to_data_url_small(p) for p in reference_images]
                if refs:
                    inputs["reference_images"] = refs
            inputs["resolution"] = resolution
            inputs["duration"] = duration
            inputs["aspect_ratio"] = aspect_ratio
            inputs["generate_audio"] = bool(generate_audio)

        if init_image:
            inputs["init_image"] = self._to_data_url_small(init_image)

        try:
            owner, name = model.split("/", 1)
            model_url = f"https://api.replicate.com/v1/models/{owner}/{name}/predictions"
        except Exception:
            model_url = self.BASE_URL
        body = {"input": inputs}
        try:
            resp = self._make_request("POST", model_url, headers=headers, json=body, timeout=60)
            data = resp.json()
            pred_id = data.get("id")
            if not pred_id:
                raise AIProviderError(f"No prediction id: {data}")
            return self._poll_and_download(pred_id, headers, output_path)
        except AIProviderError:
            raise

    def _poll_and_download(self, pred_id, headers, output_path, max_wait=900, poll_interval=5):
        url = f"{self.BASE_URL}/{pred_id}"
        start = time.time()
        last_status = None
        while time.time() - start < max_wait:
            r = self._make_request("GET", url, headers=headers)
            pj = r.json()
            status = pj.get("status")
            if status != last_status:
                log.info(f"Replicate prediction {pred_id} status: {status}")
                last_status = status
            if status == "succeeded":
                outputs = pj.get("output")
                if isinstance(outputs, list) and outputs:
                    file_url = outputs[-1]
                else:
                    file_url = outputs if isinstance(outputs, str) else None
                if not file_url:
                    raise AIProviderError(f"No output URL in response: {pj}")
                if not output_path:
                    ext = None
                    try:
                        head = self._make_request("HEAD", file_url, headers=headers)
                        ctype = (head.headers.get("Content-Type") or "").lower()
                        if "video" in ctype:
                            ext = ".mp4"
                        elif "image/png" in ctype:
                            ext = ".png"
                        elif "image/jpeg" in ctype or "image/jpg" in ctype:
                            ext = ".jpg"
                        elif "image/webp" in ctype:
                            ext = ".webp"
                    except Exception:
                        ext = None
                    if not ext:
                        ext = ".mp4" if "video" in str(pj.get("metrics", "")).lower() else ".png"
                    output_path = os.path.join("/tmp", f"replicate_{pred_id}{ext}")
                return self.download_file(file_url, output_path)
            if status in ("failed", "canceled"):
                err = pj.get("error") or pj
                raise AIProviderError(f"Prediction {pred_id} {status}: {err}")
            time.sleep(poll_interval)
        raise AIProviderError("Prediction timed out")

    @staticmethod
    def _to_data_url_small(image_path, max_kb=250, max_width=1280):
        try:
            from PyQt5.QtGui import QImage
            from PyQt5.QtCore import QByteArray, QBuffer, QIODevice
            import base64
            img = QImage(image_path)
            if img.isNull():
                return ReplicateProvider._to_data_url(image_path)
            if img.width() > max_width:
                img = img.scaledToWidth(max_width)
            data = None
            for quality in (85, 75, 65, 55, 45):
                ba = QByteArray()
                buf = QBuffer(ba)
                buf.open(QIODevice.WriteOnly)
                img.save(buf, "JPG", quality)
                buf.close()
                data = bytes(ba)
                if len(data) <= max_kb * 1024:
                    break
            if data is None:
                with open(image_path, "rb") as f:
                    data = f.read()
            b64 = base64.b64encode(data).decode()
            return f"data:image/jpeg;base64,{b64}"
        except Exception:
            return ReplicateProvider._to_data_url(image_path)

    @staticmethod
    def _to_data_url(path):
        import base64
        mime = "image/png"
        if path.lower().endswith((".jpg", ".jpeg")):
            mime = "image/jpeg"
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f"data:{mime};base64,{b64}"


