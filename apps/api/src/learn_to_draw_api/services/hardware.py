from __future__ import annotations

from threading import Lock

from learn_to_draw_api.adapters.camera import CameraAdapter
from learn_to_draw_api.adapters.plotter import PlotterAdapter
from learn_to_draw_api.models import (
    CameraCaptureResponse,
    CameraCommandResponse,
    CameraDeviceSelectionRequest,
    HardwareBusyError,
    HardwareStatus,
    LatestCaptureResponse,
    PlotterCalibration,
    PlotterCalibrationRequest,
    PlotterCalibrationResponse,
    PlotterCommandResponse,
    PlotterDeviceSettings,
    PlotterDeviceSettingsResponse,
    PlotterPenHeightsRequest,
    PlotterSafeBoundsRequest,
    PlotterTestAction,
    PlotterWorkspace,
    PlotterWorkspaceRequest,
    PlotterWorkspaceResponse,
)
from learn_to_draw_api.services.capture_normalization import target_from_page_size
from learn_to_draw_api.services.capture_service import CaptureService
from learn_to_draw_api.services.captures import CaptureStore
from learn_to_draw_api.services.plotter_calibration import PlotterCalibrationService
from learn_to_draw_api.services.plotter_device_settings import PlotterDeviceSettingsService
from learn_to_draw_api.services.plotter_workspace import PlotterWorkspaceService


class HardwareService:
    def __init__(
        self,
        *,
        plotter: PlotterAdapter,
        camera: CameraAdapter,
        capture_store: CaptureStore,
        capture_service: CaptureService,
        calibration_service: PlotterCalibrationService,
        device_settings_service: PlotterDeviceSettingsService,
        workspace_service: PlotterWorkspaceService,
    ) -> None:
        self._plotter = plotter
        self._camera = camera
        self._capture_store = capture_store
        self._capture_service = capture_service
        self._calibration_service = calibration_service
        self._device_settings_service = device_settings_service
        self._workspace_service = workspace_service
        self._plotter_lock = Lock()
        self._camera_lock = Lock()

    def startup(self) -> None:
        for adapter in (self._plotter, self._camera):
            try:
                adapter.connect()
            except Exception:
                # Device status should preserve its own error state for the UI.
                continue

    def shutdown(self) -> None:
        for adapter in (self._plotter, self._camera):
            try:
                adapter.disconnect()
            except Exception:
                continue

    def get_hardware_status(self) -> HardwareStatus:
        return HardwareStatus(
            plotter=self._plotter.get_status(),
            camera=self._camera.get_status(),
        )

    def walk_plotter_home(self) -> PlotterCommandResponse:
        if not self._plotter_lock.acquire(blocking=False):
            raise HardwareBusyError("Plotter is busy.")
        try:
            self._plotter.walk_home()
            return PlotterCommandResponse(
                message="Plotter walked home.",
                status=self._plotter.get_status(),
            )
        finally:
            self._plotter_lock.release()

    def run_plotter_test_action(self, action: PlotterTestAction) -> PlotterCommandResponse:
        if not self._plotter_lock.acquire(blocking=False):
            raise HardwareBusyError("Plotter is busy.")
        try:
            self._plotter.run_test_action(action)
            return PlotterCommandResponse(
                message=f"Plotter test action '{action}' completed.",
                status=self._plotter.get_status(),
            )
        finally:
            self._plotter_lock.release()

    def set_plotter_pen_heights(
        self,
        request: PlotterPenHeightsRequest,
    ) -> PlotterCommandResponse:
        if not self._plotter_lock.acquire(blocking=False):
            raise HardwareBusyError("Plotter is busy.")
        try:
            self._plotter.set_pen_heights(
                pen_pos_up=request.pen_pos_up,
                pen_pos_down=request.pen_pos_down,
            )
            return PlotterCommandResponse(
                message="Plotter pen heights updated.",
                status=self._plotter.get_status(),
            )
        finally:
            self._plotter_lock.release()

    def get_plotter_calibration(self) -> PlotterCalibration:
        return self._calibration_service.current()

    def get_plotter_device_settings(self) -> PlotterDeviceSettings:
        return self._device_settings_service.current()

    def set_plotter_safe_bounds(
        self,
        request: PlotterSafeBoundsRequest,
    ) -> PlotterDeviceSettingsResponse:
        if not self._plotter_lock.acquire(blocking=False):
            raise HardwareBusyError("Plotter is busy.")
        try:
            device = self._device_settings_service.save_safe_bounds_override(
                width_mm=request.width_mm,
                height_mm=request.height_mm,
            )
            return PlotterDeviceSettingsResponse(
                message=(
                    "Operational safe bounds reset to the default clearance."
                    if request.width_mm is None
                    else "Operational safe bounds updated."
                ),
                device=device,
            )
        finally:
            self._plotter_lock.release()

    def set_plotter_calibration(
        self,
        request: PlotterCalibrationRequest,
    ) -> PlotterCalibrationResponse:
        if not self._plotter_lock.acquire(blocking=False):
            raise HardwareBusyError("Plotter is busy.")
        try:
            persisted = self._calibration_service.save_axidraw_native_res_factor(request)
            apply_calibration = getattr(self._plotter, "apply_persisted_calibration", None)
            if callable(apply_calibration):
                apply_calibration(
                    native_res_factor=persisted.driver_calibration["native_res_factor"],
                    motion_scale=persisted.motion_scale,
                )
            return PlotterCalibrationResponse(
                message="Plotter calibration updated.",
                calibration=self._calibration_service.current(),
            )
        finally:
            self._plotter_lock.release()

    def get_plotter_workspace(self) -> PlotterWorkspace:
        return self._workspace_service.current()

    def set_plotter_workspace(
        self,
        request: PlotterWorkspaceRequest,
    ) -> PlotterWorkspaceResponse:
        if not self._plotter_lock.acquire(blocking=False):
            raise HardwareBusyError("Plotter is busy.")
        try:
            workspace = self._workspace_service.save(request)
            return PlotterWorkspaceResponse(
                message="Plotter workspace updated.",
                workspace=workspace,
            )
        finally:
            self._plotter_lock.release()

    def capture_image(self) -> CameraCaptureResponse:
        if not self._camera_lock.acquire(blocking=False):
            raise HardwareBusyError("Camera is busy.")
        try:
            artifact = self._camera.capture()
            workspace = self._workspace_service.current()
            normalization_target = None
            page_width = workspace.page_size_mm.width_mm
            page_height = workspace.page_size_mm.height_mm
            if page_width > 0 and page_height > 0:
                normalization_target = target_from_page_size(
                    page_width_mm=page_width,
                    page_height_mm=page_height,
                    source="workspace_drawable_area",
                )
            metadata = self._capture_service.persist_capture(
                artifact,
                normalization_target=normalization_target,
                background=True,
            )
            return CameraCaptureResponse(
                message="Image captured.",
                status=self._camera.get_status(),
                capture=metadata,
            )
        finally:
            self._camera_lock.release()

    def set_camera_device(
        self,
        request: CameraDeviceSelectionRequest,
    ) -> CameraCommandResponse:
        if not self._camera_lock.acquire(blocking=False):
            raise HardwareBusyError("Camera is busy.")
        try:
            status = self._camera.set_selected_device(request.device_id)
            return CameraCommandResponse(
                message=(
                    "Camera device preference cleared."
                    if request.device_id is None
                    else "Camera device preference updated."
                ),
                status=status,
            )
        finally:
            self._camera_lock.release()

    def latest_capture(self) -> LatestCaptureResponse:
        return LatestCaptureResponse(capture=self._capture_store.latest())
