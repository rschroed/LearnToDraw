from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Any, Optional
from uuid import uuid4

from learn_to_draw_api.adapters.camera import CaptureArtifact
from learn_to_draw_api.models import (
    DeviceStatus,
    HardwareBusyError,
    HardwareOperationError,
    HardwareUnavailableError,
)

try:
    import cv2
except ImportError:  # pragma: no cover - exercised via mocked selection paths
    cv2 = None


class OpenCVCamera:
    driver = "opencv-camera"

    def __init__(
        self,
        *,
        camera_index: int = 0,
        warmup_ms: int = 150,
        discard_frames: int = 2,
    ) -> None:
        self._camera_index = camera_index
        self._warmup_ms = max(0, warmup_ms)
        self._discard_frames = max(0, discard_frames)
        self._capture: Any = None
        self._connected = False
        self._busy = False
        self._available = False
        self._initialized = False
        self._state = "uninitialized"
        self._error: Optional[str] = None
        self._last_capture_id: Optional[str] = None
        self._last_resolution: Optional[str] = None
        self._last_updated = datetime.now(timezone.utc)

    def connect(self) -> None:
        self._ensure_cv2_available()
        self._error = None
        if not self._initialized:
            self._state = "uninitialized"
        self._touch()

    def disconnect(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        self._connected = False
        if self._initialized:
            self._available = True
            self._state = "ready"
        self._touch()

    def get_status(self) -> DeviceStatus:
        return DeviceStatus(
            available=self._available,
            connected=self._connected,
            busy=self._busy,
            error=self._error,
            driver=self.driver,
            last_updated=self._last_updated,
            details={
                "camera_index": self._camera_index,
                "initialization_state": self._initialization_state(),
                "last_capture_id": self._last_capture_id,
                "resolution": self._last_resolution,
                "last_action": "idle" if not self._busy else "capturing",
            },
        )

    def capture(self) -> CaptureArtifact:
        if self._busy:
            raise HardwareBusyError("Camera is busy.")
        self._busy = True
        self._error = None
        self._touch()
        try:
            newly_opened = self._ensure_open()
            if newly_opened:
                self._warm_up_camera()
            frame = self._read_frame()
            encoded = self._encode_frame(frame)
            height, width = self._frame_dimensions(frame)
            capture_id = uuid4().hex
            self._last_capture_id = capture_id
            self._last_resolution = f"{width}x{height}"
            self._touch()
            return CaptureArtifact(
                capture_id=capture_id,
                timestamp=datetime.now(timezone.utc),
                filename=f"{capture_id}.jpg",
                content=encoded,
                media_type="image/jpeg",
                width=width,
                height=height,
            )
        finally:
            self._busy = False
            self._touch()

    def _ensure_open(self) -> bool:
        if self._capture is not None and self._connected:
            return False
        self._ensure_cv2_available()
        self._open_camera()
        return True

    def _open_camera(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        capture = cv2.VideoCapture(self._camera_index)
        if not capture.isOpened():
            capture.release()
            self._connected = False
            self._available = False
            self._state = "unavailable"
            self._error = (
                f"OpenCV camera index {self._camera_index} is unavailable or permission "
                "was denied."
            )
            self._touch()
            raise HardwareUnavailableError(self._error)
        self._capture = capture
        self._connected = True
        self._available = True
        self._initialized = True
        self._state = "ready"
        self._error = None
        self._touch()

    def _warm_up_camera(self) -> None:
        if self._warmup_ms > 0:
            time.sleep(self._warmup_ms / 1000)
        for _ in range(self._discard_frames):
            self._read_frame()

    def _read_frame(self) -> Any:
        if self._capture is None:
            raise HardwareUnavailableError("Camera is unavailable.")
        ok, frame = self._capture.read()
        if not ok or frame is None:
            self._capture.release()
            self._capture = None
            self._error = f"OpenCV camera index {self._camera_index} failed to read a frame."
            self._available = False
            self._connected = False
            self._state = "unavailable"
            self._touch()
            raise HardwareOperationError(self._error)
        return frame

    def _encode_frame(self, frame: Any) -> bytes:
        ok, encoded = cv2.imencode(".jpg", frame)
        if not ok:
            self._error = "OpenCV camera failed to encode a JPEG capture."
            self._touch()
            raise HardwareOperationError(self._error)
        return encoded.tobytes()

    def _frame_dimensions(self, frame: Any) -> tuple[int, int]:
        shape = getattr(frame, "shape", None)
        if not shape or len(shape) < 2:
            raise HardwareOperationError("Captured frame does not expose image dimensions.")
        return int(shape[0]), int(shape[1])

    def _ensure_cv2_available(self) -> None:
        if cv2 is None:
            self._error = (
                "OpenCV support is not installed. Run 'make api-install' in the repo root "
                "or install apps/api with its dependencies."
            )
            self._available = False
            self._state = "unavailable"
            self._touch()
            raise HardwareUnavailableError(self._error)

    def _initialization_state(self) -> str:
        return self._state

    def _touch(self) -> None:
        self._last_updated = datetime.now(timezone.utc)
