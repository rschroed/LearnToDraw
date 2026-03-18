from __future__ import annotations

from types import SimpleNamespace

import pytest

from learn_to_draw_api.adapters.factory import build_camera_adapter
from learn_to_draw_api.adapters.mock_camera import MockCamera
from learn_to_draw_api.adapters.opencv_camera import OpenCVCamera
import learn_to_draw_api.adapters.opencv_camera as opencv_camera_module
from learn_to_draw_api.config import AppConfig
from learn_to_draw_api.models import HardwareOperationError, HardwareUnavailableError


class FakeFrame:
    shape = (480, 640, 3)


class FakeBuffer:
    def __init__(self, value: bytes) -> None:
        self._value = value

    def tobytes(self) -> bytes:
        return self._value


class FakeVideoCapture:
    def __init__(self, *, opened: bool = True, frames=None) -> None:
        self._opened = opened
        self._frames = list(frames or [(True, FakeFrame())])
        self.release_called = False
        self.read_calls = 0

    def isOpened(self) -> bool:
        return self._opened

    def read(self):
        self.read_calls += 1
        if self._frames:
            return self._frames.pop(0)
        return True, FakeFrame()

    def release(self) -> None:
        self.release_called = True


def _config(tmp_path, **overrides):
    return AppConfig(
        captures_dir=tmp_path / "captures",
        plot_assets_dir=tmp_path / "plot-assets",
        plot_runs_dir=tmp_path / "plot-runs",
        calibration_dir=tmp_path / "calibration",
        device_settings_dir=tmp_path / "device-settings",
        workspace_dir=tmp_path / "workspace",
        **overrides,
    )


def test_build_camera_adapter_defaults_to_mock(tmp_path):
    adapter = build_camera_adapter(_config(tmp_path))

    assert isinstance(adapter, MockCamera)


def test_build_camera_adapter_supports_opencv(tmp_path):
    adapter = build_camera_adapter(
        _config(
            tmp_path,
            camera_driver="opencv",
            opencv_camera_index=3,
            camera_warmup_ms=25,
            camera_discard_frames=1,
        )
    )

    assert isinstance(adapter, OpenCVCamera)
    assert adapter.get_status().details["camera_index"] == 3


def test_build_camera_adapter_rejects_unknown_driver(tmp_path):
    with pytest.raises(ValueError, match="Unsupported camera driver"):
        build_camera_adapter(_config(tmp_path, camera_driver="unknown"))


def test_opencv_camera_reports_uninitialized_status():
    camera = OpenCVCamera()

    status = camera.get_status()

    assert status.available is False
    assert status.connected is False
    assert status.error is None
    assert status.details["initialization_state"] == "uninitialized"
    assert status.details["resolution"] is None


def test_opencv_camera_capture_is_lazy_and_records_actual_frame_dimensions(monkeypatch):
    fake_capture = FakeVideoCapture(frames=[(True, FakeFrame()), (True, FakeFrame()), (True, FakeFrame())])
    fake_cv2 = SimpleNamespace(
        VideoCapture=lambda index: fake_capture,
        imencode=lambda ext, frame: (True, FakeBuffer(b"jpeg-bytes")),
    )
    monkeypatch.setattr(opencv_camera_module, "cv2", fake_cv2)
    camera = OpenCVCamera(camera_index=2, warmup_ms=0, discard_frames=2)

    artifact = camera.capture()
    status = camera.get_status()

    assert artifact.filename.endswith(".jpg")
    assert artifact.media_type == "image/jpeg"
    assert artifact.content == b"jpeg-bytes"
    assert artifact.width == 640
    assert artifact.height == 480
    assert fake_capture.read_calls == 3
    assert status.available is True
    assert status.connected is True
    assert status.details["initialization_state"] == "ready"
    assert status.details["camera_index"] == 2
    assert status.details["resolution"] == "640x480"
    assert status.details["last_capture_id"] == artifact.capture_id


def test_opencv_camera_connect_keeps_lazy_uninitialized_state(monkeypatch):
    fake_capture = FakeVideoCapture()
    fake_cv2 = SimpleNamespace(
        VideoCapture=lambda index: fake_capture,
        imencode=lambda ext, frame: (True, FakeBuffer(b"jpeg-bytes")),
    )
    monkeypatch.setattr(opencv_camera_module, "cv2", fake_cv2)
    camera = OpenCVCamera(warmup_ms=0, discard_frames=0)

    camera.connect()

    status = camera.get_status()
    assert status.available is False
    assert status.connected is False
    assert status.details["initialization_state"] == "uninitialized"
    assert fake_capture.read_calls == 0


def test_opencv_camera_reports_unavailable_when_open_fails_on_capture(monkeypatch):
    fake_capture = FakeVideoCapture(opened=False)
    fake_cv2 = SimpleNamespace(
        VideoCapture=lambda index: fake_capture,
        imencode=lambda ext, frame: (True, FakeBuffer(b"jpeg-bytes")),
    )
    monkeypatch.setattr(opencv_camera_module, "cv2", fake_cv2)
    camera = OpenCVCamera(warmup_ms=0, discard_frames=0)

    with pytest.raises(HardwareUnavailableError, match="permission was denied"):
        camera.capture()

    status = camera.get_status()
    assert status.available is False
    assert status.connected is False
    assert status.details["initialization_state"] == "unavailable"
    assert "permission was denied" in status.error


def test_opencv_camera_raises_when_frame_read_fails(monkeypatch):
    fake_capture = FakeVideoCapture(frames=[(False, None)])
    fake_cv2 = SimpleNamespace(
        VideoCapture=lambda index: fake_capture,
        imencode=lambda ext, frame: (True, FakeBuffer(b"jpeg-bytes")),
    )
    monkeypatch.setattr(opencv_camera_module, "cv2", fake_cv2)
    camera = OpenCVCamera(warmup_ms=0, discard_frames=0)

    with pytest.raises(HardwareOperationError, match="failed to read a frame"):
        camera.capture()


def test_opencv_camera_raises_when_jpeg_encode_fails(monkeypatch):
    fake_capture = FakeVideoCapture()
    fake_cv2 = SimpleNamespace(
        VideoCapture=lambda index: fake_capture,
        imencode=lambda ext, frame: (False, None),
    )
    monkeypatch.setattr(opencv_camera_module, "cv2", fake_cv2)
    camera = OpenCVCamera(warmup_ms=0, discard_frames=0)

    with pytest.raises(HardwareOperationError, match="failed to encode a JPEG"):
        camera.capture()


def test_opencv_camera_disconnect_releases_device(monkeypatch):
    fake_capture = FakeVideoCapture()
    fake_cv2 = SimpleNamespace(
        VideoCapture=lambda index: fake_capture,
        imencode=lambda ext, frame: (True, FakeBuffer(b"jpeg-bytes")),
    )
    monkeypatch.setattr(opencv_camera_module, "cv2", fake_cv2)
    camera = OpenCVCamera(warmup_ms=0, discard_frames=0)
    camera.capture()

    camera.disconnect()

    assert fake_capture.release_called is True
    status = camera.get_status()
    assert status.available is True
    assert status.connected is False
    assert status.details["initialization_state"] == "ready"


def test_opencv_camera_requires_opencv_installation(monkeypatch):
    monkeypatch.setattr(opencv_camera_module, "cv2", None)
    camera = OpenCVCamera()

    with pytest.raises(HardwareUnavailableError, match="OpenCV support is not installed"):
        camera.connect()
