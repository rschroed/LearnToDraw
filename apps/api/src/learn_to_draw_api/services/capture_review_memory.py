from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional

from pydantic import BaseModel, Field

from learn_to_draw_api.models import NormalizationCorners, PlotRun, PlotterWorkspace


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

    def build_scope_key_for_workspace(
        self,
        *,
        workspace: PlotterWorkspace,
        camera_driver: str,
        camera_device_id: Optional[str],
    ) -> Optional[str]:
        if camera_device_id is None:
            return None
        return self.build_scope_key(
            camera_driver=camera_driver,
            camera_device_id=camera_device_id,
            page_width_mm=workspace.page_size_mm.width_mm,
            page_height_mm=workspace.page_size_mm.height_mm,
            margin_left_mm=workspace.margins_mm.left_mm,
            margin_top_mm=workspace.margins_mm.top_mm,
            margin_right_mm=workspace.margins_mm.right_mm,
            margin_bottom_mm=workspace.margins_mm.bottom_mm,
        )

    def build_scope_key_for_run(
        self,
        *,
        run: PlotRun,
        camera_driver: str,
        camera_device_id: Optional[str],
    ) -> Optional[str]:
        if camera_device_id is None:
            return None
        workspace = run.plotter_run_details.get("workspace")
        if not isinstance(workspace, dict):
            return None
        page_size = workspace.get("page_size_mm")
        margins = workspace.get("margins_mm")
        if not isinstance(page_size, dict) or not isinstance(margins, dict):
            return None
        return self.build_scope_key(
            camera_driver=camera_driver,
            camera_device_id=camera_device_id,
            page_width_mm=float(page_size["width_mm"]),
            page_height_mm=float(page_size["height_mm"]),
            margin_left_mm=float(margins["left_mm"]),
            margin_top_mm=float(margins["top_mm"]),
            margin_right_mm=float(margins["right_mm"]),
            margin_bottom_mm=float(margins["bottom_mm"]),
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
