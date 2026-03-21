from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from learn_to_draw_api.adapters.camera import CameraAdapter
from learn_to_draw_api.adapters.plotter import PlotterAdapter
from learn_to_draw_api.models import (
    ObservedResultRecord,
    PlotRun,
    PlotStageState,
    PlotterDeviceSettings,
    PlotterWorkspace,
)
from learn_to_draw_api.services.captures import CaptureStore
from learn_to_draw_api.services.plotter_calibration import PlotterCalibrationService
from learn_to_draw_api.services.plotter_device_settings import PlotterDeviceSettingsService
from learn_to_draw_api.services.plotter_workspace import PlotterWorkspaceService

from .plot_workflow_preparation import PreparationValidationError, load_document
from .plot_workflow_runs import PlotRunStore


class PlotRunExecutor:
    def __init__(
        self,
        *,
        plotter: PlotterAdapter,
        camera: CameraAdapter,
        capture_store: CaptureStore,
        run_store: PlotRunStore,
        calibration_service: PlotterCalibrationService,
        device_settings_service: PlotterDeviceSettingsService,
        workspace_service: PlotterWorkspaceService,
    ) -> None:
        self._plotter = plotter
        self._camera = camera
        self._capture_store = capture_store
        self._run_store = run_store
        self._calibration_service = calibration_service
        self._device_settings_service = device_settings_service
        self._workspace_service = workspace_service

    def execute_run(self, run_id: str) -> None:
        current_stage: Optional[str] = None
        workspace: Optional[PlotterWorkspace] = None
        device_settings: Optional[PlotterDeviceSettings] = None
        run = self._run_store.get(run_id)
        try:
            current_stage = "prepare"
            run = self._set_stage_state(
                run,
                stage="prepare",
                status="in_progress",
                message="Preparing SVG document.",
            )
            workspace = self._workspace_service.current_validated()
            device_settings = self._device_settings_service.current()
            document, preparation = load_document(
                run.asset,
                purpose=run.purpose,
                workspace=workspace,
                device_settings=device_settings,
            )
            prepared_artifact = self._run_store.save_prepared_svg(run.id, document.svg_text)
            run.prepared_artifact = prepared_artifact
            run = self._set_stage_state(
                run,
                stage="prepare",
                status="completed",
                message="SVG document prepared.",
            )

            current_stage = "plot"
            run.status = "plotting"
            run.updated_at = datetime.now(timezone.utc)
            run = self._set_stage_state(
                run,
                stage="plot",
                status="in_progress",
                message="Sending SVG to plotter.",
            )
            plot_result = self._plotter.plot(document)
            effective_calibration = self._calibration_service.current()
            run.plotter_run_details = {
                "driver": self._plotter.driver,
                "document_id": plot_result.document_id,
                "prepared_svg_path": prepared_artifact.file_path,
                "preparation": preparation.model_dump(mode="json"),
                "calibration": effective_calibration.model_dump(mode="json"),
                "device": device_settings.model_dump(mode="json"),
                "workspace": workspace.model_dump(mode="json"),
                "duration_ms": duration_ms(
                    plot_result.started_at,
                    plot_result.completed_at,
                ),
                "details": plot_result.details,
            }
            run = self._set_stage_state(
                run,
                stage="plot",
                status="completed",
                message="Plot completed.",
            )

            current_stage = "capture"
            if run.capture_mode == "skip":
                run.camera_run_details = {
                    "capture_mode": "skip",
                }
                run = self._set_stage_state(
                    run,
                    stage="capture",
                    status="completed",
                    message="Capture skipped for diagnostic run.",
                )
            else:
                run.status = "capturing"
                run.updated_at = datetime.now(timezone.utc)
                run = self._set_stage_state(
                    run,
                    stage="capture",
                    status="in_progress",
                    message="Capturing plotted page.",
                )
                capture_started = datetime.now(timezone.utc)
                capture_artifact = self._camera.capture()
                capture_completed = datetime.now(timezone.utc)
                capture_metadata = self._capture_store.save(capture_artifact)
                run.capture = capture_metadata
                capture_duration_ms = duration_ms(capture_started, capture_completed)
                run.observed_result = ObservedResultRecord(
                    capture=capture_metadata,
                    camera_driver=self._camera.driver,
                    captured_at=capture_metadata.timestamp,
                    duration_ms=capture_duration_ms,
                )
                run.camera_run_details = {
                    "driver": self._camera.driver,
                    "capture_id": capture_metadata.id,
                    "resolution": f"{capture_metadata.width}x{capture_metadata.height}",
                    "duration_ms": capture_duration_ms,
                }
                run = self._set_stage_state(
                    run,
                    stage="capture",
                    status="completed",
                    message="Capture completed.",
                )

            run.status = "completed"
            run.error = None
            run.updated_at = datetime.now(timezone.utc)
            self._run_store.save(run)
        except Exception as exc:
            if (
                current_stage == "prepare"
                and isinstance(exc, PreparationValidationError)
                and exc.preparation is not None
            ):
                run.plotter_run_details = {
                    "driver": self._plotter.driver,
                    "preparation": exc.preparation.model_dump(mode="json"),
                    "device": (
                        device_settings.model_dump(mode="json")
                        if device_settings is not None
                        else {}
                    ),
                    "workspace": (
                        workspace.model_dump(mode="json")
                        if workspace is not None
                        else {}
                    ),
                }
            run.status = "failed"
            run.error = str(exc)
            run.updated_at = datetime.now(timezone.utc)
            if current_stage is not None:
                run = self._set_stage_state(
                    run,
                    stage=current_stage,
                    status="failed",
                    message=str(exc),
                )
            else:
                self._run_store.save(run)

    def _set_stage_state(
        self,
        run: PlotRun,
        *,
        stage: str,
        status: str,
        message: str,
    ) -> PlotRun:
        previous = run.stage_states[stage]
        now = datetime.now(timezone.utc)
        run.stage_states[stage] = PlotStageState(
            status=status,
            started_at=previous.started_at or (now if status == "in_progress" else None),
            completed_at=now if status in {"completed", "failed"} else None,
            message=message,
        )
        run.updated_at = now
        self._run_store.save(run)
        return run


def duration_ms(started_at: datetime, completed_at: datetime) -> int:
    return int((completed_at - started_at).total_seconds() * 1000)
