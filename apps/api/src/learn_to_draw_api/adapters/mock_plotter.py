from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Optional

from learn_to_draw_api.models import (
    DeviceStatus,
    HardwareBusyError,
    HardwareOperationError,
    PlotDocument,
    PlotResult,
    PlotterTestAction,
    HardwareUnavailableError,
)


class MockPlotter:
    def __init__(
        self,
        *,
        driver: str = "mock-plotter",
        available: bool = True,
        origin_delay_s: float = 0.35,
        fail_on_return_to_origin: bool = False,
        plot_delay_s: float = 0.9,
        fail_on_plot: bool = False,
        test_action_delay_s: float = 0.25,
        fail_on_test_action: bool = False,
    ) -> None:
        self.driver = driver
        self.available = available
        self._connected = False
        self._busy = False
        self._error: Optional[str] = None
        self._origin_delay_s = origin_delay_s
        self._fail_on_return_to_origin = fail_on_return_to_origin
        self._plot_delay_s = plot_delay_s
        self._fail_on_plot = fail_on_plot
        self._test_action_delay_s = test_action_delay_s
        self._fail_on_test_action = fail_on_test_action
        self._details = {
            "model": "mock-pen-plotter",
            "workspace": "A4",
            "position": "unknown",
            "api_surface": "mock",
            "pen_tuning": {
                "pen_pos_up": 60,
                "pen_pos_down": 30,
                "pen_rate_raise": 75,
                "pen_rate_lower": 50,
                "pen_delay_up": 0,
                "pen_delay_down": 0,
                "penlift": 1,
            },
            "last_plotted_asset_id": None,
            "last_test_action": None,
            "last_test_action_status": None,
        }
        self._last_updated = datetime.now(timezone.utc)

    def connect(self) -> None:
        if not self.available:
            self._connected = False
            self._error = "Plotter is unavailable."
            self._touch()
            raise HardwareUnavailableError(self._error)
        self._connected = True
        self._error = None
        self._details["connection"] = "mock-usb"
        self._touch()

    def disconnect(self) -> None:
        self._connected = False
        self._touch()

    def get_status(self) -> DeviceStatus:
        return DeviceStatus(
            available=self.available,
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
            time.sleep(self._origin_delay_s)
            if self._fail_on_return_to_origin:
                self._error = "Mock plotter failed to return to origin."
                self._details["last_action_status"] = "failed"
                raise HardwareOperationError(self._error)
            self._details["position"] = "origin"
            self._details["last_action_status"] = "succeeded"
        finally:
            self._busy = False
            self._touch()

    def set_pen_heights(self, *, pen_pos_up: int, pen_pos_down: int) -> None:
        if pen_pos_down >= pen_pos_up:
            raise HardwareOperationError("pen_pos_down must be lower than pen_pos_up.")
        pen_tuning = dict(self._details["pen_tuning"])
        pen_tuning["pen_pos_up"] = pen_pos_up
        pen_tuning["pen_pos_down"] = pen_pos_down
        self._details["pen_tuning"] = pen_tuning
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
            time.sleep(self._test_action_delay_s)
            if self._fail_on_test_action:
                self._error = f"Mock plotter failed to run test action '{action}'."
                self._details["last_action_status"] = "failed"
                self._details["last_test_action_status"] = "failed"
                raise HardwareOperationError(self._error)
            self._details["position"] = action
            self._details["last_action_status"] = "succeeded"
            self._details["last_test_action_status"] = "succeeded"
        finally:
            self._busy = False
            self._touch()

    def _ensure_ready(self) -> None:
        if not self.available:
            raise HardwareUnavailableError("Plotter is unavailable.")
        if not self._connected:
            self.connect()
        if self._busy:
            raise HardwareBusyError("Plotter is busy.")

    def plot(self, document: PlotDocument) -> PlotResult:
        self._ensure_ready()
        self._busy = True
        self._error = None
        self._details["last_action"] = "plotting"
        self._details["last_action_status"] = "in_progress"
        self._details["last_plotted_asset_id"] = document.asset_id
        started_at = datetime.now(timezone.utc)
        self._touch()
        try:
            time.sleep(self._plot_delay_s)
            if self._fail_on_plot:
                self._error = "Mock plotter failed while plotting."
                self._details["last_action_status"] = "failed"
                raise HardwareOperationError(self._error)
            self._details["position"] = "plot_complete"
            self._details["last_action"] = "plot"
            self._details["last_action_status"] = "succeeded"
            completed_at = datetime.now(timezone.utc)
            self._touch()
            return PlotResult(
                started_at=started_at,
                completed_at=completed_at,
                document_id=document.asset_id,
                details={
                    "driver": self.driver,
                    "svg_width": document.width,
                    "svg_height": document.height,
                },
            )
        finally:
            self._busy = False
            self._touch()

    def _touch(self) -> None:
        self._last_updated = datetime.now(timezone.utc)
