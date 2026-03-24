from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from learn_to_draw_api.models import DeviceStatus


@dataclass(frozen=True)
class CaptureArtifact:
    capture_id: str
    timestamp: datetime
    filename: str
    content: bytes
    media_type: str
    width: int
    height: int


class CameraAdapter(Protocol):
    driver: str

    def connect(self) -> None:
        ...

    def disconnect(self) -> None:
        ...

    def get_status(self) -> DeviceStatus:
        ...

    def set_selected_device(self, device_id: str | None) -> DeviceStatus:
        ...

    def capture(self) -> CaptureArtifact:
        ...
