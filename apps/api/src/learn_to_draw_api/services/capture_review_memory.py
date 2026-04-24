from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional

from pydantic import BaseModel, Field

from learn_to_draw_api.models import NormalizationCorners


class CaptureReviewMemoryRecord(BaseModel):
    scope_key: str
    camera_driver: str
    camera_device_id: str
    page_width_mm: float = Field(gt=0)
    page_height_mm: float = Field(gt=0)
    margin_left_mm: float = Field(ge=0)
    margin_top_mm: float = Field(ge=0)
    margin_right_mm: float = Field(ge=0)
    margin_bottom_mm: float = Field(ge=0)
    capture_id: str
    confirmed_corners: NormalizationCorners
    updated_at: datetime


class CaptureReviewMemoryStore:
    def __init__(self, workspace_dir: Path) -> None:
        self._path = workspace_dir / "capture_review_memory.json"
        self._lock = Lock()

    def get(self, scope_key: str) -> Optional[CaptureReviewMemoryRecord]:
        with self._lock:
            payload = self._load()
            record = payload.get(scope_key)
            if record is None:
                return None
            return CaptureReviewMemoryRecord.model_validate(record)

    def save(self, record: CaptureReviewMemoryRecord) -> CaptureReviewMemoryRecord:
        with self._lock:
            payload = self._load()
            payload[record.scope_key] = record.model_dump(mode="json")
            self._path.write_text(
                CaptureReviewMemoryPayload(records=payload).model_dump_json(indent=2),
                encoding="utf-8",
            )
            return record

    def build_scope_key(
        self,
        *,
        camera_driver: str,
        camera_device_id: str,
        page_width_mm: float,
        page_height_mm: float,
        margin_left_mm: float,
        margin_top_mm: float,
        margin_right_mm: float,
        margin_bottom_mm: float,
    ) -> str:
        return "|".join(
            [
                camera_driver,
                camera_device_id,
                f"{page_width_mm:.3f}",
                f"{page_height_mm:.3f}",
                f"{margin_left_mm:.3f}",
                f"{margin_top_mm:.3f}",
                f"{margin_right_mm:.3f}",
                f"{margin_bottom_mm:.3f}",
            ]
        )

    def create_record(
        self,
        *,
        scope_key: str,
        camera_driver: str,
        camera_device_id: str,
        page_width_mm: float,
        page_height_mm: float,
        margin_left_mm: float,
        margin_top_mm: float,
        margin_right_mm: float,
        margin_bottom_mm: float,
        capture_id: str,
        confirmed_corners: NormalizationCorners,
    ) -> CaptureReviewMemoryRecord:
        return CaptureReviewMemoryRecord(
            scope_key=scope_key,
            camera_driver=camera_driver,
            camera_device_id=camera_device_id,
            page_width_mm=page_width_mm,
            page_height_mm=page_height_mm,
            margin_left_mm=margin_left_mm,
            margin_top_mm=margin_top_mm,
            margin_right_mm=margin_right_mm,
            margin_bottom_mm=margin_bottom_mm,
            capture_id=capture_id,
            confirmed_corners=confirmed_corners,
            updated_at=datetime.now(timezone.utc),
        )

    def _load(self) -> dict[str, dict]:
        if not self._path.exists():
            return {}
        return CaptureReviewMemoryPayload.model_validate_json(
            self._path.read_text(encoding="utf-8")
        ).records


class CaptureReviewMemoryPayload(BaseModel):
    records: dict[str, dict] = Field(default_factory=dict)

