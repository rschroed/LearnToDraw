from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Optional
from uuid import uuid4

from learn_to_draw_api.adapters.camera import CaptureArtifact
from learn_to_draw_api.models import (
    DeviceStatus,
    HardwareBusyError,
    HardwareOperationError,
    HardwareUnavailableError,
)


class MockCamera:
    def __init__(
        self,
        *,
        driver: str = "mock-camera",
        available: bool = True,
        capture_delay_s: float = 0.45,
        fail_on_capture: bool = False,
        width: int = 1280,
        height: int = 960,
    ) -> None:
        self.driver = driver
        self.available = available
        self._connected = False
        self._busy = False
        self._error: Optional[str] = None
        self._capture_delay_s = capture_delay_s
        self._fail_on_capture = fail_on_capture
        self._width = width
        self._height = height
        self._last_capture_id: Optional[str] = None
        self._last_updated = datetime.now(timezone.utc)

    def connect(self) -> None:
        if not self.available:
            self._connected = False
            self._error = "Camera is unavailable."
            self._touch()
            raise HardwareUnavailableError(self._error)
        self._connected = True
        self._error = None
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
            details={
                "resolution": f"{self._width}x{self._height}",
                "last_capture_id": self._last_capture_id,
                "last_action": "idle" if not self._busy else "capturing",
            },
        )

    def capture(self) -> CaptureArtifact:
        self._ensure_ready()
        self._busy = True
        self._error = None
        self._touch()
        capture_id = uuid4().hex
        timestamp = datetime.now(timezone.utc)
        try:
            time.sleep(self._capture_delay_s)
            if self._fail_on_capture:
                self._error = "Mock camera failed to capture."
                raise HardwareOperationError(self._error)
            self._last_capture_id = capture_id
            self._touch()
            return CaptureArtifact(
                capture_id=capture_id,
                timestamp=timestamp,
                filename=f"{capture_id}.svg",
                content=self._build_svg(capture_id, timestamp).encode("utf-8"),
                media_type="image/svg+xml",
                width=self._width,
                height=self._height,
            )
        finally:
            self._busy = False
            self._touch()

    def _build_svg(self, capture_id: str, timestamp: datetime) -> str:
        stamp = timestamp.isoformat()
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{self._width}" height="{self._height}" viewBox="0 0 {self._width} {self._height}">
  <rect width="100%" height="100%" fill="#f6f1e8" />
  <g stroke="#1f2933" stroke-width="6" fill="none">
    <path d="M 120 760 C 360 280, 620 280, 860 760" />
    <path d="M 240 700 C 420 420, 560 420, 740 700" />
    <line x1="950" y1="120" x2="1140" y2="310" />
    <line x1="950" y1="310" x2="1140" y2="120" />
  </g>
  <g fill="#8b5e34" font-family="Menlo, monospace" font-size="32">
    <text x="120" y="120">Mock Capture</text>
    <text x="120" y="170">ID: {capture_id[:12]}</text>
    <text x="120" y="220">Time: {stamp}</text>
  </g>
</svg>"""

    def _ensure_ready(self) -> None:
        if not self.available:
            raise HardwareUnavailableError("Camera is unavailable.")
        if not self._connected:
            self.connect()
        if self._busy:
            raise HardwareBusyError("Camera is busy.")

    def _touch(self) -> None:
        self._last_updated = datetime.now(timezone.utc)
