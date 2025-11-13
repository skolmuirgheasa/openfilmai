"""
Google Vertex AI provider for Veo 3.1

Uses the predictLongRunning API with proper instances/parameters structure.
Supports text-to-video, image-to-video, first+last frame interpolation, and reference images.
"""
import os
import json
import time
import base64
from .base import AIProvider, AIProviderError
from classes.logger import log


class VertexVeoProvider(AIProvider):
    DEFAULT_MODEL = "veo-3.1-generate-preview"
    BASE_URL = "https://us-central1-aiplatform.googleapis.com/v1"

    def __init__(self, credentials_path: str, project_id: str, location: str = "us-central1", model: str = None):
        super().__init__(api_key=None)
        self.credentials_path = (credentials_path or "").strip()
        self.project_id = (project_id or "").strip()
        self.location = (location or "us-central1").strip()
        self.model = (model or self.DEFAULT_MODEL).strip()
        self._credentials = None
        self._token = None
        self._token_expiry = 0

    def _get_access_token(self) -> str:
        """Get OAuth2 access token from service account credentials"""
        try:
            from google.oauth2 import service_account
            from google.auth.transport.requests import Request
        except ImportError:
            raise AIProviderError("Missing dependency: google-auth. Please install with: pip install google-auth")

        if not self.credentials_path or not os.path.exists(self.credentials_path):
            raise AIProviderError(f"Vertex AI credentials file not found: {self.credentials_path}")

        # Refresh token if expired or not yet loaded
        if not self._credentials or time.time() >= self._token_expiry:
            log.info(f"Loading Vertex AI credentials from: {self.credentials_path}")
            self._credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=['https://www.googleapis.com/auth/cloud-platform']
            )
            self._credentials.refresh(Request())
            self._token = self._credentials.token
            # Refresh 5 minutes before expiry
            self._token_expiry = time.time() + 3000
            log.info("Vertex AI access token refreshed")

        return self._token

    def generate(
        self,
        prompt,
        first_frame_image=None,
        last_frame_image=None,
        reference_images=None,
        duration=8,
        resolution="1080p",
        aspect_ratio="16:9",
        generate_audio=True,
        output_path=None,
        **kwargs,
    ):
        """
        Generate video using Vertex AI Veo 3.1 API
        
        Uses the predictLongRunning endpoint with instances/parameters structure.
        """
        if not self.project_id or not self.credentials_path:
            raise AIProviderError("Vertex AI Project ID and Credentials Path must be set.")

        access_token = self._get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        # Build the instance object (what to generate)
        instance = {
            "prompt": prompt
        }

        # Add first frame (image) if provided
        if first_frame_image:
            log.info(f"Adding first frame: {first_frame_image}")
            instance["image"] = {
                "gcsUri": self._upload_to_gcs_or_base64(first_frame_image),
                "mimeType": "image/jpeg"
            }

        # Add last frame if provided (for interpolation)
        if last_frame_image:
            log.info(f"Adding last frame: {last_frame_image}")
            instance["lastFrame"] = {
                "gcsUri": self._upload_to_gcs_or_base64(last_frame_image),
                "mimeType": "image/jpeg"
            }

        # Add reference images if provided (for subject consistency)
        if reference_images:
            log.info(f"Adding {len(reference_images)} reference images")
            instance["referenceImages"] = []
            for ref_img in reference_images:
                instance["referenceImages"].append({
                    "gcsUri": self._upload_to_gcs_or_base64(ref_img),
                    "mimeType": "image/jpeg"
                })

        # Build parameters (how to generate)
        parameters = {
            "sampleCount": 1,  # Number of videos to generate
        }

        # Build the request body
        body = {
            "instances": [instance],
            "parameters": parameters
        }

        # Construct the API URL
        # If model already includes publishers/google/models/, don't duplicate it
        if self.model.startswith("publishers/"):
            model_path = self.model
        else:
            model_path = f"publishers/google/models/{self.model}"
        url = f"{self.BASE_URL}/projects/{self.project_id}/locations/{self.location}/{model_path}:predictLongRunning"

        log.info(f"Sending request to Vertex AI: {url}")
        log.info(f"Request body: {json.dumps(body, indent=2)}")

        try:
            # Start the long-running operation
            resp = self._make_request("POST", url, headers=headers, json=body, timeout=30)
            data = resp.json()
            
            if "name" not in data:
                raise AIProviderError(f"Vertex AI: No operation name in response: {data}")
            
            operation_name = data["name"]
            log.info(f"Vertex AI operation started: {operation_name}")
            
            # Poll for completion
            return self._poll_operation(operation_name, access_token, output_path)

        except AIProviderError:
            raise
        except Exception as e:
            raise AIProviderError(f"Vertex AI generation failed: {e}")

    def _upload_to_gcs_or_base64(self, image_path):
        """
        Upload image to GCS and return gs:// URI.
        Creates a temporary bucket if needed.
        """
        try:
            from google.cloud import storage
            from google.oauth2 import service_account
        except ImportError:
            raise AIProviderError("Missing dependency: google-cloud-storage. Install with: pip install google-cloud-storage")
        
        try:
            # Load credentials
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=['https://www.googleapis.com/auth/cloud-platform']
            )
            
            # Initialize GCS client
            client = storage.Client(project=self.project_id, credentials=credentials)
            
            # Use or create a bucket for temporary uploads
            bucket_name = f"{self.project_id}-openshot-temp"
            try:
                bucket = client.get_bucket(bucket_name)
            except Exception:
                # Bucket doesn't exist, create it
                log.info(f"Creating GCS bucket: {bucket_name}")
                bucket = client.create_bucket(bucket_name, location=self.location)
            
            # Upload the image with a unique name
            blob_name = f"frames/{int(time.time())}_{os.path.basename(image_path)}"
            blob = bucket.blob(blob_name)
            
            log.info(f"Uploading {image_path} to gs://{bucket_name}/{blob_name}")
            blob.upload_from_filename(image_path)
            
            # Return the GCS URI
            gcs_uri = f"gs://{bucket_name}/{blob_name}"
            log.info(f"Uploaded to: {gcs_uri}")
            return gcs_uri
            
        except Exception as e:
            raise AIProviderError(f"Failed to upload image to GCS: {e}")

    def _poll_operation(self, operation_name, access_token, output_path):
        """Poll the long-running operation until complete"""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        # Extract operation ID from full name
        # Format: projects/PROJECT_ID/locations/LOCATION/publishers/google/models/MODEL/operations/OPERATION_ID
        operation_id = operation_name.split("/")[-1]
        
        # Use same model_path logic
        if self.model.startswith("publishers/"):
            model_path = self.model
        else:
            model_path = f"publishers/google/models/{self.model}"
        fetch_url = f"{self.BASE_URL}/projects/{self.project_id}/locations/{self.location}/{model_path}:fetchPredictOperation"
        
        body = {
            "operationName": operation_name
        }

        max_polls = 120  # 10 minutes max (5 second intervals)
        for i in range(max_polls):
            time.sleep(5)
            log.info(f"Polling Vertex AI operation ({i+1}/{max_polls})...")
            
            try:
                resp = self._make_request("POST", fetch_url, headers=headers, json=body, timeout=30)
                data = resp.json()
                
                if data.get("done"):
                    log.info("Vertex AI operation complete")
                    
                    # Check for errors
                    if "error" in data:
                        error_msg = data["error"].get("message", str(data["error"]))
                        raise AIProviderError(f"Vertex AI operation failed: {error_msg}")
                    
                    # Extract video from response
                    if "response" in data and "videos" in data["response"]:
                        videos = data["response"]["videos"]
                        if videos and len(videos) > 0:
                            video = videos[0]
                            
                            # Check for GCS URI
                            if "gcsUri" in video:
                                video_uri = video["gcsUri"]
                                log.info(f"Video generated at GCS: {video_uri}")
                                if not output_path:
                                    output_path = os.path.join("/tmp", f"vertex_veo_{int(time.time())}.mp4")
                                return self._download_from_gcs(video_uri, output_path, access_token)
                            
                            # Check for inline base64 data
                            elif "bytesBase64Encoded" in video:
                                log.info("Video returned as inline base64 data")
                                if not output_path:
                                    output_path = os.path.join("/tmp", f"vertex_veo_{int(time.time())}.mp4")
                                video_data = base64.b64decode(video["bytesBase64Encoded"])
                                with open(output_path, "wb") as f:
                                    f.write(video_data)
                                log.info(f"Video decoded and saved to: {output_path} ({len(video_data)} bytes)")
                                return output_path
                    
                    raise AIProviderError(f"Vertex AI: No video data in response")
                
                # Still processing
                if "metadata" in data:
                    progress = data["metadata"].get("progressPercentage", 0)
                    log.info(f"Progress: {progress}%")
                    
            except AIProviderError:
                raise
            except Exception as e:
                log.warning(f"Error polling operation: {e}")
                continue
        
        raise AIProviderError("Vertex AI: Operation timed out after 10 minutes")

    def _download_from_gcs(self, gcs_uri, output_path, access_token):
        """Download video from GCS bucket"""
        # Convert gs://bucket/path to HTTP URL
        if gcs_uri.startswith("gs://"):
            # gs://bucket/path -> https://storage.googleapis.com/bucket/path
            path = gcs_uri[5:]  # Remove gs://
            http_url = f"https://storage.googleapis.com/{path}"
            
            headers = {
                "Authorization": f"Bearer {access_token}"
            }
            
            log.info(f"Downloading video from: {http_url}")
            return self.download_file(http_url, output_path, headers=headers)
        else:
            raise AIProviderError(f"Invalid GCS URI: {gcs_uri}")
