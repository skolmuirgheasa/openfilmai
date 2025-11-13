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
        model: str = "veo-3.1-generate-preview",
        timeout: int = 60,
    ):
        self.credentials_path = credentials_path
        self.project_id = project_id
        self.location = location
        self.model = model
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
        bucket_name = f"{self.project_id}-openfilmai-temp"
        try:
            bucket = client.get_bucket(bucket_name)
        except Exception:
            bucket = client.create_bucket(bucket_name, location=self.location)
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
    ) -> str:
        base = "https://us-central1-aiplatform.googleapis.com/v1"
        url = f"{base}/projects/{self.project_id}/locations/{self.location}/{self._model_path()}:predictLongRunning"

        instance: Dict[str, Any] = {"prompt": prompt}
        if first_frame_image:
            instance["image"] = {"gcsUri": self._upload_image_to_gcs(first_frame_image), "mimeType": "image/jpeg"}
        if last_frame_image:
            instance["lastFrame"] = {"gcsUri": self._upload_image_to_gcs(last_frame_image), "mimeType": "image/jpeg"}
        if reference_images:
            instance["referenceImages"] = [
                {"gcsUri": self._upload_image_to_gcs(p), "mimeType": "image/jpeg"} for p in reference_images
            ]

        body = {"instances": [instance], "parameters": {"sampleCount": 1}}
        r = requests.post(url, headers=self._headers(), json=body, timeout=self.timeout)
        r.raise_for_status()
        op_name = r.json().get("name")
        if not op_name:
            raise RuntimeError(f"Vertex: no operation name: {r.text}")
        return self._poll_and_download(op_name)

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
                        # Convert GCS to public https for download via storage.googleapis.com
                        path = v["gcsUri"].replace("gs://", "")
                        return f"https://storage.googleapis.com/{path}"
                    if "bytesBase64Encoded" in v:
                        out = f"/tmp/vertex_{int(time.time())}.mp4"
                        with open(out, "wb") as f:
                            f.write(base64.b64decode(v["bytesBase64Encoded"]))
                        return out
                raise RuntimeError("Vertex: no video in response")
        raise RuntimeError("Vertex: operation timed out")


