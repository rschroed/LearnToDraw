from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import Lock, Thread
from typing import Optional
from uuid import uuid4

from learn_to_draw_api.adapters.camera import CameraAdapter
from learn_to_draw_api.adapters.plotter import PlotterAdapter
from learn_to_draw_api.models import (
    AppConflictError,
    AppNotFoundError,
    InvalidArtifactError,
    PatternAssetCreateRequest,
    PlotAsset,
    PlotRun,
    PlotRunCaptureMode,
    PlotRunListResponse,
    PlotRunPurpose,
    PlotStageState,
)
from learn_to_draw_api.services.captures import CaptureStore
from learn_to_draw_api.services.plotter_calibration import PlotterCalibrationService
from learn_to_draw_api.services.plotter_device_settings import PlotterDeviceSettingsService
from learn_to_draw_api.services.plotter_workspace import PlotterWorkspaceService

from .plot_workflow_assets import PlotAssetStore
from .plot_workflow_execution import PlotRunExecutor
from .plot_workflow_preparation import parse_svg_root, pattern_definition
from .plot_workflow_runs import ACTIVE_RUN_STATUSES, PlotRunStore


class PlotWorkflowService:
    def __init__(
        self,
        *,
        plotter: PlotterAdapter,
        camera: CameraAdapter,
        capture_store: CaptureStore,
        asset_store: PlotAssetStore,
        run_store: PlotRunStore,
        calibration_service: PlotterCalibrationService,
        device_settings_service: PlotterDeviceSettingsService,
        workspace_service: PlotterWorkspaceService,
    ) -> None:
        self._plotter = plotter
        self._camera = camera
        self._capture_store = capture_store
        self._asset_store = asset_store
        self._run_store = run_store
        self._calibration_service = calibration_service
        self._device_settings_service = device_settings_service
        self._workspace_service = workspace_service
        self._lock = Lock()
        self._active_run_id: Optional[str] = None
        self._executor = PlotRunExecutor(
            plotter=plotter,
            camera=camera,
            capture_store=capture_store,
            run_store=run_store,
            calibration_service=calibration_service,
            device_settings_service=device_settings_service,
            workspace_service=workspace_service,
        )

    def create_uploaded_asset(
        self,
        *,
        filename: str,
        content: bytes,
        content_type: Optional[str],
    ) -> PlotAsset:
        if not filename:
            raise InvalidArtifactError("An SVG filename is required.")
        if content_type and "svg" not in content_type.lower() and not filename.lower().endswith(
            ".svg"
        ):
            raise InvalidArtifactError("Only SVG uploads are supported.")
        try:
            svg_text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InvalidArtifactError("Uploaded SVG must be valid UTF-8.") from exc
        parse_svg_root(svg_text)
        display_name = Path(filename).stem or filename
        return self._asset_store.save_svg(
            svg_text=svg_text,
            name=display_name,
            kind="uploaded_svg",
        )

    def create_pattern_asset(self, request: PatternAssetCreateRequest) -> PlotAsset:
        pattern = pattern_definition(request.pattern_id)
        if pattern is None:
            raise InvalidArtifactError(f"Unsupported pattern_id '{request.pattern_id}'.")
        return self._asset_store.save_svg(
            svg_text=pattern["svg_text"],
            name=pattern["name"],
            kind="built_in_pattern",
            pattern_id=request.pattern_id,
        )

    def get_asset(self, asset_id: str) -> PlotAsset:
        return self._asset_store.get(asset_id)

    def create_run(
        self,
        asset_id: str,
        *,
        purpose: PlotRunPurpose = "normal",
        capture_mode: PlotRunCaptureMode = "auto",
    ) -> PlotRun:
        asset = self._asset_store.get(asset_id)
        now = datetime.now(timezone.utc)
        run = PlotRun(
            id=uuid4().hex,
            status="pending",
            purpose=purpose,
            capture_mode=capture_mode,
            created_at=now,
            updated_at=now,
            asset=asset,
            stage_states={
                "prepare": PlotStageState(status="pending"),
                "plot": PlotStageState(status="pending"),
                "capture": PlotStageState(status="pending"),
            },
        )
        with self._lock:
            active_run = self._get_active_run_locked()
            if active_run is not None and active_run.status in ACTIVE_RUN_STATUSES:
                raise AppConflictError("A plot run is already active.")
            self._active_run_id = run.id
            self._run_store.save(run)
            worker = Thread(target=self._execute_run_in_thread, args=(run.id,), daemon=True)
            worker.start()
        return run

    def latest_run(self) -> Optional[PlotRun]:
        return self._run_store.latest()

    def list_runs(self) -> PlotRunListResponse:
        return self._run_store.list_summaries()

    def get_run(self, run_id: str) -> PlotRun:
        return self._run_store.get(run_id)

    def _execute_run_in_thread(self, run_id: str) -> None:
        try:
            self._executor.execute_run(run_id)
        finally:
            with self._lock:
                if self._active_run_id == run_id:
                    self._active_run_id = None

    def _get_active_run_locked(self) -> Optional[PlotRun]:
        if self._active_run_id is None:
            return None
        try:
            active_run = self._run_store.get(self._active_run_id)
        except AppNotFoundError:
            self._active_run_id = None
            return None
        if active_run.status not in ACTIVE_RUN_STATUSES:
            self._active_run_id = None
            return None
        return active_run


__all__ = ["PlotAssetStore", "PlotRunStore", "PlotWorkflowService"]
