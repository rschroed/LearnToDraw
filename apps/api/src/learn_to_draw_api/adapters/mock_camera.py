from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Optional
from uuid import uuid4

import cv2
import numpy as np

from learn_to_draw_api.adapters.camera import CaptureArtifact
from learn_to_draw_api.models import (
    DeviceStatus,
    HardwareBusyError,
    HardwareOperationError,
    HardwareUnavailableError,
    InvalidArtifactError,
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

    def set_selected_device(self, device_id: str | None) -> DeviceStatus:
        raise InvalidArtifactError(
            f"Camera device selection is not supported for driver '{self.driver}'."
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
                filename=f"{capture_id}.png",
                content=self._build_png(capture_id, timestamp),
                media_type="image/png",
                width=self._width,
                height=self._height,
            )
        finally:
            self._busy = False
            self._touch()

    def _build_png(self, capture_id: str, timestamp: datetime) -> bytes:
        stamp = timestamp.isoformat()
        frame = np.full((self._height, self._width, 3), (28, 32, 30), dtype=np.uint8)
        paper_height = int(self._height * 0.72)
        paper_width = int(paper_height * 0.75)
        paper = np.full((paper_height, paper_width, 3), 244, dtype=np.uint8)
        cv2.rectangle(paper, (0, 0), (paper_width - 1, paper_height - 1), (224, 219, 209), 6)
        cv2.line(
            paper,
            (paper_width // 6, int(paper_height * 0.2)),
            (paper_width - (paper_width // 6), int(paper_height * 0.2)),
            (58, 66, 74),
            8,
        )
        cv2.putText(
            paper,
            "Mock Capture",
            (int(paper_width * 0.12), int(paper_height * 0.16)),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (78, 56, 33),
            3,
            cv2.LINE_AA,
        )
        cv2.putText(
            paper,
            capture_id[:12],
            (int(paper_width * 0.12), int(paper_height * 0.24)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (78, 56, 33),
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            paper,
            stamp[:19],
            (int(paper_width * 0.12), int(paper_height * 0.3)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (78, 56, 33),
            2,
            cv2.LINE_AA,
        )
        cv2.polylines(
            paper,
            [
                np.array(
                    [
                        (int(paper_width * 0.16), int(paper_height * 0.75)),
                        (int(paper_width * 0.32), int(paper_height * 0.42)),
                        (int(paper_width * 0.5), int(paper_height * 0.58)),
                        (int(paper_width * 0.68), int(paper_height * 0.34)),
                        (int(paper_width * 0.84), int(paper_height * 0.72)),
                    ],
                    dtype=np.int32,
                )
            ],
            isClosed=False,
            color=(31, 41, 51),
            thickness=8,
        )
        cv2.rectangle(
            paper,
            (int(paper_width * 0.14), int(paper_height * 0.36)),
            (int(paper_width * 0.82), int(paper_height * 0.84)),
            (32, 40, 48),
            6,
        )

        source = np.array(
            [
                [0.0, 0.0],
                [float(paper_width - 1), 0.0],
                [float(paper_width - 1), float(paper_height - 1)],
                [0.0, float(paper_height - 1)],
            ],
            dtype=np.float32,
        )
        destination = np.array(
            [
                [self._width * 0.18, self._height * 0.12],
                [self._width * 0.77, self._height * 0.08],
                [self._width * 0.82, self._height * 0.88],
                [self._width * 0.16, self._height * 0.9],
            ],
            dtype=np.float32,
        )
        matrix = cv2.getPerspectiveTransform(source, destination)
        warped_paper = cv2.warpPerspective(paper, matrix, (self._width, self._height))
        warped_mask = cv2.warpPerspective(
            np.full((paper_height, paper_width), 255, dtype=np.uint8),
            matrix,
            (self._width, self._height),
        )
        mask = warped_mask > 0
        frame[mask] = warped_paper[mask]
        ok, encoded = cv2.imencode(".png", frame)
        if not ok:
            raise HardwareOperationError("Mock camera failed to encode the capture preview.")
        return encoded.tobytes()

    def _ensure_ready(self) -> None:
        if not self.available:
            raise HardwareUnavailableError("Camera is unavailable.")
        if not self._connected:
            self.connect()
        if self._busy:
            raise HardwareBusyError("Camera is busy.")

    def _touch(self) -> None:
        self._last_updated = datetime.now(timezone.utc)
