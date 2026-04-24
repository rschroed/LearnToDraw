from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from learn_to_draw_api.adapters.camera import CameraAdapter
from learn_to_draw_api.adapters.plotter import PlotterAdapter
from learn_to_draw_api.models import (
    CaptureReview,
    ObservedResultRecord,
    PlotRun,
    PlotStageState,
    PlotterDeviceSettings,
    PlotterWorkspace,
)
from learn_to_draw_api.services.capture_normalization import (
    LOW_CONFIDENCE_THRESHOLD,
    target_from_page_size,
)
from learn_to_draw_api.services.capture_service import CaptureService
from learn_to_draw_api.services.capture_review_memory import CaptureReviewMemoryStore
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
        capture_service: CaptureService,
        review_memory_store: CaptureReviewMemoryStore,
        run_store: PlotRunStore,
        calibration_service: PlotterCalibrationService,
        device_settings_service: PlotterDeviceSettingsService,
        workspace_service: PlotterWorkspaceService,
    ) -> None:
        self._plotter = plotter
        self._camera = camera
        self._capture_service = capture_service
        self._review_memory_store = review_memory_store
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
                normalization_target = target_from_page_size(
                    page_width_mm=preparation.page_width_mm,
                    page_height_mm=preparation.page_height_mm,
                    source="prepared_svg",
                )
                capture_metadata = self._capture_service.persist_raw_capture(capture_artifact)
                proposal = self._capture_service.inspect_capture(
                    content=capture_artifact.content,
                    normalization_target=normalization_target,
                )
                scope_key = self._review_memory_store.build_scope_key_for_workspace(
                    workspace=workspace,
                    camera_driver=self._camera.driver,
                    camera_device_id=self._camera_device_id(),
                )
                reuse_last_available = (
                    self._review_memory_store.get(scope_key) is not None
                    if scope_key is not None
                    else False
                )
                review_required = (
                    proposal.method == "fallback_full_frame"
                    or proposal.confidence < LOW_CONFIDENCE_THRESHOLD
                )
                review = CaptureReview(
                    review_required=review_required,
                    review_status="pending" if review_required else "confirmed",
                    proposed_corners=proposal.corners,
                    confirmed_corners=None if review_required else proposal.corners,
                    confirmation_source=None if review_required else "auto",
                    detector_method=proposal.method,
                    detector_confidence=proposal.confidence,
                    reuse_last_available=reuse_last_available,
                )
                capture_metadata = self._capture_service.save_capture_review(
                    capture_metadata.id,
                    review=review,
                )
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
                if review_required:
                    run.status = "awaiting_capture_review"
                    run.updated_at = datetime.now(timezone.utc)
                    run.camera_run_details = {
                        **run.camera_run_details,
                        "capture_review_required": True,
                    }
                    run = self._set_stage_state(
                        run,
                        stage="capture_review",
                        status="in_progress",
                        message="Review the detected page corners before normalization.",
                    )
                    return

                run = self._set_stage_state(
                    run,
                    stage="capture_review",
                    status="in_progress",
                    message="Finalizing normalized capture.",
                )
                run = self._finalize_capture_review(
                    run,
                    normalization_target=normalization_target,
                    persist_review_memory=False,
                )

            if run.status != "completed":
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

    def finalize_capture_review(self, run_id: str, *, persist_review_memory: bool = True) -> PlotRun:
        run = self._run_store.get(run_id)
        preparation = run.plotter_run_details.get("preparation", {})
        normalization_target = target_from_page_size(
            page_width_mm=float(preparation["page_width_mm"]),
            page_height_mm=float(preparation["page_height_mm"]),
            source="prepared_svg",
        )
        return self._finalize_capture_review(
            run,
            normalization_target=normalization_target,
            persist_review_memory=persist_review_memory,
        )

    def _finalize_capture_review(
        self,
        run: PlotRun,
        *,
        normalization_target,
        persist_review_memory: bool,
    ) -> PlotRun:
        if run.capture is None or run.capture.review is None:
            raise ValueError("Capture review is not available for this run.")
        review = run.capture.review
        confirmed_corners = review.confirmed_corners
        if confirmed_corners is None:
            raise ValueError("Capture review has not been confirmed.")
        content = Path(run.capture.file_path).read_bytes()
        updated_capture = self._capture_service.finalize_capture_with_review(
            capture_id=run.capture.id,
            content=content,
            normalization_target=normalization_target,
            corners=confirmed_corners,
            method=review.detector_method,
            confidence=review.detector_confidence,
            diagnostics=None,
            review=review,
        )
        run.capture = updated_capture
        if run.observed_result is not None:
            run.observed_result = run.observed_result.model_copy(
                update={"capture": updated_capture}
            )
        if persist_review_memory and review.confirmation_source in {"adjusted", "reused_last"}:
            scope_key = self._review_memory_store.build_scope_key_for_run(
                run=run,
                camera_driver=self._camera.driver,
                camera_device_id=self._camera_device_id(),
            )
            if scope_key is not None:
                workspace = run.plotter_run_details["workspace"]
                self._review_memory_store.save(
                    self._review_memory_store.create_record(
                        scope_key=scope_key,
                        camera_driver=self._camera.driver,
                        camera_device_id=self._camera_device_id(),
                        page_width_mm=float(workspace["page_size_mm"]["width_mm"]),
                        page_height_mm=float(workspace["page_size_mm"]["height_mm"]),
                        margin_left_mm=float(workspace["margins_mm"]["left_mm"]),
                        margin_top_mm=float(workspace["margins_mm"]["top_mm"]),
                        margin_right_mm=float(workspace["margins_mm"]["right_mm"]),
                        margin_bottom_mm=float(workspace["margins_mm"]["bottom_mm"]),
                        capture_id=updated_capture.id,
                        confirmed_corners=confirmed_corners,
                    )
                )
        run = self._set_stage_state(
            run,
            stage="capture_review",
            status="completed",
            message="Capture review confirmed.",
        )
        run.status = "completed"
        run.error = None
        run.updated_at = datetime.now(timezone.utc)
        self._run_store.save(run)
        return run

    def _camera_device_id(self) -> Optional[str]:
        details = self._camera.get_status().details
        if not isinstance(details, dict):
            return None
        for key in (
            "effective_selected_device_id",
            "active_device_id",
            "persisted_selected_device_id",
        ):
            value = details.get(key)
            if isinstance(value, str) and value:
                return value
        return self._camera.driver

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
