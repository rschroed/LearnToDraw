from __future__ import annotations

from pathlib import Path
from typing import Optional
from urllib.parse import quote

from learn_to_draw_api.adapters.camera import CaptureArtifact
from learn_to_draw_api.models import CaptureMetadata


class CaptureStore:
    def __init__(self, captures_dir: Path, capture_url_prefix: str) -> None:
        self._captures_dir = captures_dir
        normalized_prefix = capture_url_prefix.strip() or "/captures"
        if not normalized_prefix.startswith("/"):
            normalized_prefix = f"/{normalized_prefix}"
        self._capture_url_prefix = normalized_prefix.rstrip("/") or "/captures"
        self._captures_dir.mkdir(parents=True, exist_ok=True)
        self._latest: Optional[CaptureMetadata] = None

    def save(self, artifact: CaptureArtifact) -> CaptureMetadata:
        safe_filename = Path(artifact.filename).name
        file_path = self._captures_dir / safe_filename
        metadata_path = self._captures_dir / f"{artifact.capture_id}.json"
        file_path.write_bytes(artifact.content)

        metadata = CaptureMetadata(
            id=artifact.capture_id,
            timestamp=artifact.timestamp,
            file_path=str(file_path),
            public_url=f"{self._capture_url_prefix}/{quote(safe_filename)}",
            width=artifact.width,
            height=artifact.height,
            mime_type=artifact.media_type,
        )
        metadata_path.write_text(metadata.model_dump_json(indent=2), encoding="utf-8")
        self._latest = metadata
        return metadata

    def latest(self) -> Optional[CaptureMetadata]:
        if self._latest is None:
            self._latest = self._load_latest()
        return self._latest

    def _load_latest(self) -> Optional[CaptureMetadata]:
        latest: Optional[CaptureMetadata] = None
        for metadata_path in sorted(self._captures_dir.glob("*.json")):
            candidate = CaptureMetadata.model_validate_json(metadata_path.read_text())
            if latest is None or candidate.timestamp > latest.timestamp:
                latest = candidate
        return latest
