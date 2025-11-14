"""
WaveSpeed InfiniteTalk provider
"""

import base64
import mimetypes
import os
import time

try:
    from classes.logger import log  # type: ignore
except Exception:
    import logging
    _logger = logging.getLogger("openfilmai")
    _logger.setLevel(logging.INFO)
    if not _logger.handlers:
        _h = logging.StreamHandler()
        _h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        _logger.addHandler(_h)
    class _Log:
        def info(self, *args, **kwargs): _logger.info(*args, **kwargs)
        def warning(self, *args, **kwargs): _logger.warning(*args, **kwargs)
        def error(self, *args, **kwargs): _logger.error(*args, **kwargs)
    log = _Log()
from .base import AIProvider, AIProviderError


class WaveSpeedProvider(AIProvider):
    """Client for WaveSpeed InfiniteTalk REST API"""

    SUBMIT_URL = "https://api.wavespeed.ai/api/v3/wavespeed-ai/infinitetalk"
    RESULT_URL = "https://api.wavespeed.ai/api/v3/predictions/{request_id}/result"

    def __init__(self, api_key: str):
        super().__init__(api_key=api_key)
        if not self.api_key:
            raise AIProviderError("WaveSpeed API key not set")

    def _file_to_data_url(self, path, fallback_mime):
        if not path or not os.path.exists(path):
            raise AIProviderError(f"File not found: {path}")
        mime = mimetypes.guess_type(path)[0] or fallback_mime
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")
        return f"data:{mime};base64,{data}"

    def _poll_result(self, request_id, headers, timeout=600, direct_url=None):
        start = time.time()
        while time.time() - start < timeout:
            time.sleep(5)
            url = direct_url or self.RESULT_URL.format(request_id=request_id)
            resp = self._make_request("GET", url, headers=headers, timeout=60)
            data = resp.json()
            status = (data.get("status") or data.get("state") or "").lower()
            log.info(f"WaveSpeed status {status} for request {request_id}")
            if status in {"completed", "success", "succeeded", "finished"}:
                result = data.get("result") or data
                video_url = result.get("videoUrl") or result.get("video_url") or result.get("video") or result.get("url")
                if not video_url:
                    raise AIProviderError(f"WaveSpeed: completed but no video url in response: {data}")
                return video_url
            if status in {"failed", "error"}:
                raise AIProviderError(f"WaveSpeed request failed: {data}")
        raise AIProviderError("WaveSpeed request timed out")

    def generate(self, prompt, image_path=None, audio_path=None, video_path=None, resolution="720p", seed=-1, output_path=None, **kwargs) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "audio": self._file_to_data_url(audio_path, "audio/mpeg") if audio_path else None,
            "image": self._file_to_data_url(image_path, "image/jpeg") if image_path else None,
            "video": self._file_to_data_url(video_path, "video/mp4") if video_path else None,
            "prompt": prompt or "",
            "resolution": resolution or "720p",
            "seed": seed if seed is not None else -1,
        }
        # Remove None keys
        payload = {k: v for k, v in payload.items() if v is not None}
        log.info(f"WaveSpeed submit payload: prompt len={len(payload['prompt'])}, resolution={payload['resolution']}")
        submit_resp = self._make_request("POST", self.SUBMIT_URL, headers=headers, json=payload, timeout=120)
        submit_data = submit_resp.json()
        data_block = submit_data.get("data") or {}
        request_id = submit_data.get("requestId") or submit_data.get("id") or data_block.get("id")
        result_url = (
            submit_data.get("resultUrl")
            or data_block.get("urls", {}).get("get")
            or submit_data.get("urls", {}).get("get")
        )
        if not request_id:
            raise AIProviderError(f"WaveSpeed response missing request id: {submit_data}")
        log.info(f"WaveSpeed request id: {request_id}")
        video_url = self._poll_result(request_id, headers, direct_url=result_url)
        log.info(f"WaveSpeed video url: {video_url}")
        if not output_path:
            output_path = os.path.join("/tmp", f"wavespeed_{int(time.time())}.mp4")
        self.download_file(video_url, output_path, headers=headers)
        return output_path


