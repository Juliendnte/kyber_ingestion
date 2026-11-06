"""
Transformation — étape 2 du pipeline.
Soumet les vidéos à l'API KyberIA et rapatrie CSV + vidéo annotée.
"""
import time
from pathlib import Path
from typing import Callable, Optional

import requests


class KyberiaClient:
    """Client léger pour l'API KyberIA (FastAPI sur :8000)."""

    def __init__(self, api_url: str, api_token: str = ""):
        self.base = api_url.rstrip("/")
        self._session = requests.Session()
        if api_token:
            self._session.headers["Authorization"] = f"Bearer {api_token}"

    def ping(self) -> bool:
        try:
            r = self._session.get(f"{self.base}/health", timeout=5)
            return r.status_code == 200
        except requests.RequestException:
            return False

    def submit(self, video_path: Path) -> str:
        """Upload la vidéo, retourne le job_id."""
        with open(video_path, "rb") as fh:
            r = self._session.post(
                f"{self.base}/analyze",
                files={"video": (video_path.name, fh, "video/mp4")},
                timeout=600,
            )
        r.raise_for_status()
        return r.json()["job_id"]

    def status(self, job_id: str) -> dict:
        r = self._session.get(f"{self.base}/jobs/{job_id}", timeout=10)
        r.raise_for_status()
        return r.json()

    def wait(
        self,
        job_id: str,
        poll: int = 10,
        timeout: int = 14400,
        on_tick: Optional[Callable[[str, int], None]] = None,
    ) -> dict:
        """Poll jusqu'à done/failed. Timeout en secondes (défaut 4h)."""
        elapsed = 0
        while elapsed < timeout:
            s = self.status(job_id)
            state = s.get("status", "")
            if on_tick:
                on_tick(state, elapsed)
            if state == "done":
                return s
            if state in ("failed", "error"):
                raise RuntimeError(f"Job {job_id} échoué : {s.get('error', '?')}")
            time.sleep(poll)
            elapsed += poll
        raise TimeoutError(f"Job {job_id} toujours en cours après {timeout}s")

    def fetch_csv(self, job_id: str, dest: Path) -> Path:
        r = self._session.get(f"{self.base}/csv/{job_id}", timeout=60)
        r.raise_for_status()
        dest.write_bytes(r.content)
        return dest

    def fetch_video(self, job_id: str, dest: Path) -> Path:
        """Téléchargement streamé pour les grandes vidéos annotées."""
        r = self._session.get(
            f"{self.base}/video/{job_id}",
            timeout=600,
            stream=True,
        )
        r.raise_for_status()
        with open(dest, "wb") as fh:
            for chunk in r.iter_content(chunk_size=8 * 1024 * 1024):
                fh.write(chunk)
        return dest
