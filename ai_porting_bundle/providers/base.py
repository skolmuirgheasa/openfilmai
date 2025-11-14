import os
import requests
try:
    # Optional external logger used in original project
    from classes.logger import log  # type: ignore
except Exception:
    # Minimal fallback logger
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


class AIProviderError(Exception):
    pass


class AIProvider:
    def __init__(self, api_key=None):
        self.api_key = api_key or ""
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "OpenShot-AI"})

    def _make_request(self, method, url, **kwargs):
        try:
            resp = self.session.request(method, url, timeout=kwargs.pop("timeout", 60), **kwargs)
            resp.raise_for_status()
            return resp
        except requests.exceptions.HTTPError as e:
            body = ""
            try:
                body = e.response.text if e.response is not None else ""
            except Exception:
                pass
            log.error(f"HTTP error from {url}: {e}")
            if body:
                log.error(f"Response body: {body}")
            code = e.response.status_code if e.response is not None else "error"
            raise AIProviderError(f"HTTP error: {code} {body or str(e)}")
        except requests.exceptions.RequestException as e:
            log.error(f"Request error to {url}: {e}")
            raise AIProviderError(f"Request failed: {e}")

    def download_file(self, url, output_path, headers=None):
        kwargs = {"stream": True}
        if headers:
            kwargs["headers"] = headers
        r = self._make_request("GET", url, **kwargs)
        os.makedirs(os.path.dirname(output_path) or "/tmp", exist_ok=True)
        with open(output_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return output_path


