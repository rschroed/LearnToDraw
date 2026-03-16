from __future__ import annotations

from threading import Lock

from learn_to_draw_api.adapters.camera import CameraAdapter
from learn_to_draw_api.adapters.plotter import PlotterAdapter
from learn_to_draw_api.models import (
    CameraCaptureResponse,
    HardwareBusyError,
    HardwareStatus,
    LatestCaptureResponse,
    PlotterCommandResponse,
    PlotterPenHeightsRequest,
    PlotterTestAction,
)
from learn_to_draw_api.services.captures import CaptureStore


class HardwareService:
    def __init__(
        self,
        *,
        plotter: PlotterAdapter,
        camera: CameraAdapter,
        capture_store: CaptureStore,
    ) -> None:
        self._plotter = plotter
        self._camera = camera
        self._capture_store = capture_store
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

    def return_plotter_to_origin(self) -> PlotterCommandResponse:
        if not self._plotter_lock.acquire(blocking=False):
            raise HardwareBusyError("Plotter is busy.")
        try:
            self._plotter.return_to_origin()
            return PlotterCommandResponse(
                message="Plotter returned to origin.",
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

    def capture_image(self) -> CameraCaptureResponse:
        if not self._camera_lock.acquire(blocking=False):
            raise HardwareBusyError("Camera is busy.")
        try:
            artifact = self._camera.capture()
            metadata = self._capture_store.save(artifact)
            return CameraCaptureResponse(
                message="Image captured.",
                status=self._camera.get_status(),
                capture=metadata,
            )
        finally:
            self._camera_lock.release()

    def latest_capture(self) -> LatestCaptureResponse:
        return LatestCaptureResponse(capture=self._capture_store.latest())
