from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from learn_to_draw_api.models import (
    DeviceStatus,
    HardwareUnavailableError,
    PlotDocument,
    PlotResult,
    PlotterTestAction,
)


class UnavailablePlotter:
    def __init__(
        self,
        *,
        driver: str,
        message: str,
        details: Optional[dict[str, object]] = None,
    ) -> None:
        self.driver = driver
        self._message = message
        self._details = {
            "last_action": "idle",
            "last_action_status": None,
            **(details or {}),
        }
        self._connected = False
        self._last_updated = datetime.now(timezone.utc)

    def connect(self) -> None:
        self._connected = False
        self._details["last_action"] = "connect"
        self._details["last_action_status"] = "failed"
        self._touch()
        raise HardwareUnavailableError(self._message)

    def disconnect(self) -> None:
        self._connected = False
        self._details["last_action"] = "disconnect"
        self._details["last_action_status"] = "succeeded"
        self._touch()

    def get_status(self) -> DeviceStatus:
        return DeviceStatus(
            available=False,
            connected=self._connected,
            busy=False,
            error=self._message,
            driver=self.driver,
            last_updated=self._last_updated,
            details=dict(self._details),
        )

    def walk_home(self) -> None:
        raise HardwareUnavailableError(self._message)

    def set_pen_heights(self, *, pen_pos_up: int, pen_pos_down: int) -> None:
        raise HardwareUnavailableError(self._message)

    def run_test_action(self, action: PlotterTestAction) -> None:
        raise HardwareUnavailableError(self._message)

    def plot(self, document: PlotDocument) -> PlotResult:
        raise HardwareUnavailableError(self._message)

    def _touch(self) -> None:
        self._last_updated = datetime.now(timezone.utc)
