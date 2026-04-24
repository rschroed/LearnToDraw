from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Optional
from urllib.parse import quote

from learn_to_draw_api.adapters.camera import CaptureArtifact
from learn_to_draw_api.models import CaptureMetadata, CaptureReview, NormalizedCaptureArtifacts


class CaptureStore:
    def __init__(self, captures_dir: Path, capture_url_prefix: str) -> None:
        self._captures_dir = captures_dir
        normalized_prefix = capture_url_prefix.strip() or "/captures"
        if not normalized_prefix.startswith("/"):
            normalized_prefix = f"/{normalized_prefix}"
        self._capture_url_prefix = normalized_prefix.rstrip("/") or "/captures"
        self._captures_dir.mkdir(parents=True, exist_ok=True)
        self._latest: Optional[CaptureMetadata] = None
        self._lock = Lock()

    def save(self, artifact: CaptureArtifact) -> CaptureMetadata:
        safe_filename = Path(artifact.filename).name
        file_path = self._captures_dir / safe_filename
        metadata = CaptureMetadata(
            id=artifact.capture_id,
            timestamp=artifact.timestamp,
            file_path=str(file_path),
            public_url=self.public_url_for_filename(safe_filename),
            width=artifact.width,
            height=artifact.height,
            mime_type=artifact.media_type,
        )
        with self._lock:
            file_path.write_bytes(artifact.content)
            self._write_metadata(metadata)
            self._latest = metadata
        return metadata

    def get(self, capture_id: str) -> Optional[CaptureMetadata]:
        metadata_path = self._metadata_path(capture_id)
        if not metadata_path.exists():
            return None
        return CaptureMetadata.model_validate_json(metadata_path.read_text(encoding="utf-8"))

    def save_normalized(
        self,
        capture_id: str,
        *,
        rectified_color: bytes,
        rectified_grayscale: bytes,
        debug_overlay: bytes,
        normalized: NormalizedCaptureArtifacts,
        review: Optional[CaptureReview] = None,
    ) -> CaptureMetadata:
        with self._lock:
            metadata = self.get(capture_id)
            if metadata is None:
                raise FileNotFoundError(f"Capture '{capture_id}' was not found.")
            (self._captures_dir / f"{capture_id}-rectified-color.png").write_bytes(rectified_color)
            (self._captures_dir / f"{capture_id}-rectified-grayscale.png").write_bytes(
                rectified_grayscale
            )
            (self._captures_dir / f"{capture_id}-debug-overlay.png").write_bytes(debug_overlay)
            update_fields: dict[str, object] = {"normalized": normalized}
            if review is not None:
                update_fields["review"] = review
            updated = metadata.model_copy(update=update_fields)
            self._write_metadata(updated)
            if self._latest is not None and self._latest.id == capture_id:
                self._latest = updated
            return updated

    def save_review(self, capture_id: str, review: CaptureReview) -> CaptureMetadata:
        with self._lock:
            metadata = self.get(capture_id)
            if metadata is None:
                raise FileNotFoundError(f"Capture '{capture_id}' was not found.")
            updated = metadata.model_copy(update={"review": review})
            self._write_metadata(updated)
            if self._latest is not None and self._latest.id == capture_id:
                self._latest = updated
            return updated

    def latest(self) -> Optional[CaptureMetadata]:
        with self._lock:
            if self._latest is None:
                self._latest = self._load_latest()
            return self._latest

    def public_url_for_filename(self, filename: str) -> str:
        return f"{self._capture_url_prefix}/{quote(filename)}"

    def _load_latest(self) -> Optional[CaptureMetadata]:
        latest: Optional[CaptureMetadata] = None
        for metadata_path in sorted(self._captures_dir.glob("*.json")):
            candidate = CaptureMetadata.model_validate_json(
                metadata_path.read_text(encoding="utf-8")
            )
            if latest is None or candidate.timestamp > latest.timestamp:
                latest = candidate
        return latest

    def _metadata_path(self, capture_id: str) -> Path:
        return self._captures_dir / f"{capture_id}.json"

    def _write_metadata(self, metadata: CaptureMetadata) -> None:
        self._metadata_path(metadata.id).write_text(
            metadata.model_dump_json(indent=2),
            encoding="utf-8",
        )
