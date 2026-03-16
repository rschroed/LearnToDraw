from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from learn_to_draw_api.adapters.axidraw_client import (
    AxiDrawActionResult,
    AxiDrawPlotExecution,
    AxiDrawProbeResult,
    PyAxiDrawClient,
    PyAxiDrawClientError,
)
from learn_to_draw_api.models import (
    DeviceStatus,
    HardwareBusyError,
    HardwareOperationError,
    HardwareUnavailableError,
    PlotDocument,
    PlotResult,
    PlotterTestAction,
)


class AxiDrawPlotter:
    driver = "axidraw-pyapi"

    def __init__(
        self,
        *,
        client: Optional[PyAxiDrawClient] = None,
        port: Optional[str] = None,
    ) -> None:
        self._client = client or PyAxiDrawClient(port=port)
        self._port = port
        self._connected = False
        self._busy = False
        self._error: Optional[str] = None
        self._last_updated = datetime.now(timezone.utc)
        self._details = {
            "model": "AxiDraw",
            "connection": "usb",
            "port": port or "auto",
            "firmware_version": None,
            "api_surface": None,
            "pen_tuning": self._client.pen_tuning(),
            "last_action": "idle",
            "last_action_status": None,
            "last_plotted_asset_id": None,
            "last_test_action": None,
            "last_test_action_status": None,
        }

    def connect(self) -> None:
        try:
            probe = self._client.probe_connection()
            self._apply_probe_result(probe)
            self._connected = True
            self._error = None
            self._touch()
        except PyAxiDrawClientError as exc:
            self._connected = False
            self._error = str(exc)
            self._details["last_action"] = "connect"
            self._details["last_action_status"] = "failed"
            self._touch()
            raise HardwareUnavailableError(self._error) from exc

    def disconnect(self) -> None:
        self._connected = False
        self._details["last_action"] = "disconnect"
        self._details["last_action_status"] = "succeeded"
        self._touch()

    def get_status(self) -> DeviceStatus:
        return DeviceStatus(
            available=self._error is None or self._connected,
            connected=self._connected,
            busy=self._busy,
            error=self._error,
            driver=self.driver,
            last_updated=self._last_updated,
            details=dict(self._details),
        )

    def return_to_origin(self) -> None:
        self._ensure_ready()
        self._busy = True
        self._error = None
        self._details["last_action"] = "return_to_origin"
        self._details["last_action_status"] = "in_progress"
        self._touch()
        try:
            result = self._client.return_to_origin()
            self._apply_action_result(result)
            self._details["position"] = "origin"
            self._details["last_action_status"] = "succeeded"
            self._touch()
        except PyAxiDrawClientError as exc:
            self._error = str(exc)
            self._details["last_action_status"] = "failed"
            self._touch()
            raise HardwareOperationError(self._error) from exc
        finally:
            self._busy = False
            self._touch()

    def set_pen_heights(self, *, pen_pos_up: int, pen_pos_down: int) -> None:
        if pen_pos_down >= pen_pos_up:
            raise HardwareOperationError("pen_pos_down must be lower than pen_pos_up.")
        self._client.set_pen_heights(pen_pos_up=pen_pos_up, pen_pos_down=pen_pos_down)
        self._details["pen_tuning"] = self._client.pen_tuning()
        self._details["last_action"] = "set_pen_heights"
        self._details["last_action_status"] = "succeeded"
        self._touch()

    def run_test_action(self, action: PlotterTestAction) -> None:
        self._ensure_ready()
        self._busy = True
        self._error = None
        self._details["last_action"] = "test_action"
        self._details["last_action_status"] = "in_progress"
        self._details["last_test_action"] = action
        self._details["last_test_action_status"] = "in_progress"
        self._touch()
        try:
            result = self._client.run_test_action(action)
            self._apply_action_result(result)
            self._details["last_action_status"] = "succeeded"
            self._details["last_test_action_status"] = "succeeded"
            self._touch()
        except PyAxiDrawClientError as exc:
            self._error = str(exc)
            self._details["last_action_status"] = "failed"
            self._details["last_test_action_status"] = "failed"
            self._touch()
            raise HardwareOperationError(self._error) from exc
        finally:
            self._busy = False
            self._touch()

    def plot(self, document: PlotDocument) -> PlotResult:
        self._ensure_ready()
        self._busy = True
        self._error = None
        self._details["last_action"] = "plot"
        self._details["last_action_status"] = "in_progress"
        self._details["last_plotted_asset_id"] = document.asset_id
        started_at = datetime.now(timezone.utc)
        self._touch()
        try:
            execution = self._client.run_plot_document(document.svg_text)
            completed_at = datetime.now(timezone.utc)
            self._apply_plot_execution(execution)
            self._details["last_action_status"] = "succeeded"
            self._touch()
            return PlotResult(
                started_at=started_at,
                completed_at=completed_at,
                document_id=document.asset_id,
                details={
                    "driver": self.driver,
                    "port": execution.port or self._details["port"],
                    **execution.details,
                },
            )
        except PyAxiDrawClientError as exc:
            self._error = str(exc)
            self._details["last_action_status"] = "failed"
            self._touch()
            raise HardwareOperationError(self._error) from exc
        finally:
            self._busy = False
            self._touch()

    def _ensure_ready(self) -> None:
        if self._busy:
            raise HardwareBusyError("Plotter is busy.")
        if not self._connected:
            self.connect()

    def _apply_probe_result(self, probe: AxiDrawProbeResult) -> None:
        if probe.firmware_version is not None:
            self._details["firmware_version"] = probe.firmware_version
        if probe.port is not None:
            self._details["port"] = probe.port
        self._details["api_surface"] = probe.api_surface
        self._details["last_action"] = "connect"
        self._details["last_action_status"] = "succeeded"

    def _apply_action_result(self, result: AxiDrawActionResult) -> None:
        if result.port is not None:
            self._details["port"] = result.port
        self._details["api_surface"] = result.api_surface

    def _apply_plot_execution(self, execution: AxiDrawPlotExecution) -> None:
        if execution.port is not None:
            self._details["port"] = execution.port
        self._details["api_surface"] = execution.api_surface

    def _touch(self) -> None:
        self._last_updated = datetime.now(timezone.utc)
