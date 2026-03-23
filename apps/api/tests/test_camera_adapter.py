from __future__ import annotations

import json

import cv2
import numpy as np
import pytest

from learn_to_draw_api.adapters.camerabridge_camera import CameraBridgeCamera
from learn_to_draw_api.adapters.camerabridge_client import (
    CameraBridgeCapturedPhoto,
    CameraBridgeClientError,
    CameraBridgeConnectionError,
    CameraBridgeDevice,
    CameraBridgePermissionResult,
    CameraBridgeSessionSnapshot,
)
from learn_to_draw_api.adapters.factory import build_camera_adapter
from learn_to_draw_api.adapters.mock_camera import MockCamera
import learn_to_draw_api.adapters.camerabridge_camera as camerabridge_camera_module
from learn_to_draw_api.config import AppConfig
from learn_to_draw_api.models import HardwareBusyError, HardwareUnavailableError
from learn_to_draw_api.services.camera_device_settings import (
    CameraDeviceSettingsService,
    CameraDeviceSettingsStore,
)


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


def _camera_settings_service(tmp_path):
    return CameraDeviceSettingsService(
        store=CameraDeviceSettingsStore(tmp_path / "device-settings")
    )


def _write_token(tmp_path, token: str = "test-token"):
    token_path = tmp_path / "auth-token"
    token_path.write_text(token, encoding="utf-8")
    return token_path


def _write_runtime_configuration(tmp_path, *, host: str = "127.0.0.1", port: int = 8731):
    runtime_configuration_path = tmp_path / "runtime-configuration.json"
    runtime_configuration_path.write_text(
        json.dumps({"host": host, "port": port}),
        encoding="utf-8",
    )
    return runtime_configuration_path


def _fake_client_factory(state):
    class FakeCameraBridgeClient:
        def __init__(self, *, base_url: str, token: str | None = None, timeout_s: float = 2.0):
            state["constructed"] = {
                "base_url": base_url,
                "token": token,
                "timeout_s": timeout_s,
            }

        def health(self):
            value = state.get("health", "ok")
            if isinstance(value, Exception):
                raise value
            return value

        def permission_status(self):
            value = state.get("permission_status", "authorized")
            if isinstance(value, Exception):
                raise value
            return value

        def request_permission(self):
            value = state.get(
                "permission_result",
                CameraBridgePermissionResult(
                    status="authorized",
                    prompted=False,
                    message=None,
                    next_step_kind=None,
                ),
            )
            if isinstance(value, Exception):
                raise value
            return value

        def devices(self):
            value = state.get("devices", [])
            if isinstance(value, Exception):
                raise value
            return value

        def session(self):
            value = state.get(
                "session",
                CameraBridgeSessionSnapshot(
                    state="stopped",
                    active_device_id=None,
                    owner_id=None,
                    last_error=None,
                ),
            )
            if isinstance(value, Exception):
                raise value
            return value

        def select_device(self, *, device_id: str, owner_id: str | None):
            state.setdefault("calls", []).append(("select_device", device_id, owner_id))
            value = state.get(
                "select_device_result",
                CameraBridgeSessionSnapshot(
                    state="stopped",
                    active_device_id=device_id,
                    owner_id=owner_id,
                    last_error=None,
                ),
            )
            if isinstance(value, Exception):
                raise value
            return value

        def start_session(self, *, owner_id: str):
            state.setdefault("calls", []).append(("start_session", owner_id))
            value = state.get(
                "start_session_result",
                CameraBridgeSessionSnapshot(
                    state="running",
                    active_device_id="camera-1",
                    owner_id=owner_id,
                    last_error=None,
                ),
            )
            if isinstance(value, Exception):
                raise value
            return value

        def stop_session(self, *, owner_id: str):
            state.setdefault("calls", []).append(("stop_session", owner_id))
            value = state.get(
                "stop_session_result",
                CameraBridgeSessionSnapshot(
                    state="stopped",
                    active_device_id="camera-1",
                    owner_id=None,
                    last_error=None,
                ),
            )
            if isinstance(value, Exception):
                raise value
            return value

        def capture_photo(self, *, owner_id: str):
            state.setdefault("calls", []).append(("capture_photo", owner_id))
            value = state["capture_photo_result"]
            if isinstance(value, Exception):
                raise value
            return value

    return FakeCameraBridgeClient


def _jpeg_bytes(width: int = 640, height: int = 480) -> bytes:
    image = np.full((height, width, 3), 245, dtype=np.uint8)
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok
    return encoded.tobytes()


def test_build_camera_adapter_defaults_to_mock(tmp_path):
    adapter = build_camera_adapter(
        _config(tmp_path),
        camera_settings_service=_camera_settings_service(tmp_path),
    )

    assert isinstance(adapter, MockCamera)


def test_build_camera_adapter_supports_camerabridge(tmp_path):
    adapter = build_camera_adapter(
        _config(
            tmp_path,
            camera_driver="camerabridge",
            camerabridge_base_url="http://127.0.0.1:8731",
            camerabridge_token_path=_write_token(tmp_path),
        ),
        camera_settings_service=_camera_settings_service(tmp_path),
    )

    assert isinstance(adapter, CameraBridgeCamera)


def test_build_camera_adapter_rejects_unknown_driver(tmp_path):
    with pytest.raises(ValueError, match="Unsupported camera driver"):
        build_camera_adapter(
            _config(tmp_path, camera_driver="opencv"),
            camera_settings_service=_camera_settings_service(tmp_path),
        )


def test_camerabridge_status_uses_env_base_url_before_runtime_configuration(
    tmp_path,
    monkeypatch,
):
    token_path = _write_token(tmp_path)
    runtime_configuration_path = _write_runtime_configuration(
        tmp_path,
        host="127.0.0.1",
        port=9000,
    )
    monkeypatch.setattr(
        camerabridge_camera_module,
        "CAMERABRIDGE_RUNTIME_CONFIGURATION_PATH",
        runtime_configuration_path,
    )
    state = {
        "devices": [
            CameraBridgeDevice(id="camera-1", name="Built-in Camera", position="front")
        ]
    }
    monkeypatch.setattr(
        camerabridge_camera_module,
        "CameraBridgeClient",
        _fake_client_factory(state),
    )
    camera = CameraBridgeCamera(
        config=_config(
            tmp_path,
            camera_driver="camerabridge",
            camerabridge_base_url="http://127.0.0.1:8731",
            camerabridge_token_path=token_path,
        ),
        camera_settings_service=_camera_settings_service(tmp_path),
    )
    camera.connect()

    status = camera.get_status()

    assert status.available is True
    assert state["constructed"]["base_url"] == "http://127.0.0.1:8731"


def test_camerabridge_status_surfaces_invalid_runtime_configuration(
    tmp_path,
    monkeypatch,
):
    token_path = _write_token(tmp_path)
    runtime_configuration_path = tmp_path / "runtime-configuration.json"
    runtime_configuration_path.write_text("{invalid", encoding="utf-8")
    monkeypatch.setattr(
        camerabridge_camera_module,
        "CAMERABRIDGE_RUNTIME_CONFIGURATION_PATH",
        runtime_configuration_path,
    )
    camera = CameraBridgeCamera(
        config=_config(
            tmp_path,
            camera_driver="camerabridge",
            camerabridge_token_path=token_path,
        ),
        camera_settings_service=_camera_settings_service(tmp_path),
    )
    camera.connect()

    status = camera.get_status()

    assert status.available is False
    assert status.error is not None
    assert "runtime configuration is invalid" in status.error


def test_camerabridge_status_reports_needs_device_selection_for_multiple_devices(
    tmp_path,
    monkeypatch,
):
    token_path = _write_token(tmp_path)
    state = {
        "devices": [
            CameraBridgeDevice(id="camera-1", name="Built-in Camera", position="front"),
            CameraBridgeDevice(id="camera-2", name="Desk Camera", position="external"),
        ]
    }
    monkeypatch.setattr(
        camerabridge_camera_module,
        "CameraBridgeClient",
        _fake_client_factory(state),
    )
    camera = CameraBridgeCamera(
        config=_config(
            tmp_path,
            camera_driver="camerabridge",
            camerabridge_token_path=token_path,
        ),
        camera_settings_service=_camera_settings_service(tmp_path),
    )
    camera.connect()

    status = camera.get_status()

    assert status.available is False
    assert status.error is None
    assert status.details["readiness_state"] == "needs_device_selection"
    assert status.details["selection_required"] is True
    assert status.details["effective_selected_device_id"] is None


def test_camerabridge_status_uses_persisted_device_selection(tmp_path, monkeypatch):
    token_path = _write_token(tmp_path)
    settings_service = _camera_settings_service(tmp_path)
    settings_service.save_selected_device("camera-2")
    state = {
        "devices": [
            CameraBridgeDevice(id="camera-1", name="Built-in Camera", position="front"),
            CameraBridgeDevice(id="camera-2", name="Desk Camera", position="external"),
        ]
    }
    monkeypatch.setattr(
        camerabridge_camera_module,
        "CameraBridgeClient",
        _fake_client_factory(state),
    )
    camera = CameraBridgeCamera(
        config=_config(
            tmp_path,
            camera_driver="camerabridge",
            camerabridge_token_path=token_path,
        ),
        camera_settings_service=settings_service,
    )
    camera.connect()

    status = camera.get_status()

    assert status.available is True
    assert status.details["effective_selected_device_id"] == "camera-2"
    assert status.details["selection_required"] is False


def test_camerabridge_status_surfaces_missing_token(tmp_path, monkeypatch):
    state = {
        "devices": [
            CameraBridgeDevice(id="camera-1", name="Built-in Camera", position="front")
        ]
    }
    monkeypatch.setattr(
        camerabridge_camera_module,
        "CameraBridgeClient",
        _fake_client_factory(state),
    )
    monkeypatch.setattr(
        camerabridge_camera_module,
        "CAMERABRIDGE_DEFAULT_TOKEN_PATH",
        tmp_path / "missing-auth-token",
    )
    camera = CameraBridgeCamera(
        config=_config(tmp_path, camera_driver="camerabridge"),
        camera_settings_service=_camera_settings_service(tmp_path),
    )
    camera.connect()

    status = camera.get_status()

    assert status.available is False
    assert status.error is not None
    assert "auth token is missing" in status.error
    assert status.details["token_readable"] is False


def test_camerabridge_status_maps_permission_guidance_without_error(
    tmp_path,
    monkeypatch,
):
    token_path = _write_token(tmp_path)
    state = {
        "permission_status": "not_determined",
        "permission_result": CameraBridgePermissionResult(
            status="not_determined",
            prompted=False,
            message="Open CameraBridgeApp to request camera access.",
            next_step_kind="open_camera_bridge_app",
        ),
        "devices": [
            CameraBridgeDevice(id="camera-1", name="Built-in Camera", position="front")
        ],
    }
    monkeypatch.setattr(
        camerabridge_camera_module,
        "CameraBridgeClient",
        _fake_client_factory(state),
    )
    camera = CameraBridgeCamera(
        config=_config(
            tmp_path,
            camera_driver="camerabridge",
            camerabridge_token_path=token_path,
        ),
        camera_settings_service=_camera_settings_service(tmp_path),
    )
    camera.connect()

    status = camera.get_status()

    assert status.available is False
    assert status.error is None
    assert status.details["readiness_state"] == "needs_permission"
    assert status.details["permission_message"] == "Open CameraBridgeApp to request camera access."
    assert status.details["permission_next_step_kind"] == "open_camera_bridge_app"


def test_camerabridge_capture_restarts_same_owner_session_and_imports_capture(
    tmp_path,
    monkeypatch,
):
    token_path = _write_token(tmp_path)
    capture_path = tmp_path / "capture-real-001.jpg"
    capture_path.write_bytes(_jpeg_bytes())
    state = {
        "session": CameraBridgeSessionSnapshot(
            state="running",
            active_device_id="camera-1",
            owner_id="learntodraw-api",
            last_error=None,
        ),
        "devices": [
            CameraBridgeDevice(id="camera-1", name="Built-in Camera", position="front")
        ],
        "capture_photo_result": CameraBridgeCapturedPhoto(
            local_path=str(capture_path),
            captured_at="2026-03-22T20:15:00Z",
            device_id="camera-1",
        ),
    }
    monkeypatch.setattr(
        camerabridge_camera_module,
        "CameraBridgeClient",
        _fake_client_factory(state),
    )
    camera = CameraBridgeCamera(
        config=_config(
            tmp_path,
            camera_driver="camerabridge",
            camerabridge_token_path=token_path,
        ),
        camera_settings_service=_camera_settings_service(tmp_path),
    )
    camera.connect()

    artifact = camera.capture()

    assert artifact.filename == "capture-real-001.jpg"
    assert artifact.media_type == "image/jpeg"
    assert artifact.width == 640
    assert artifact.height == 480
    assert state["calls"] == [
        ("stop_session", "learntodraw-api"),
        ("select_device", "camera-1", "learntodraw-api"),
        ("start_session", "learntodraw-api"),
        ("capture_photo", "learntodraw-api"),
        ("stop_session", "learntodraw-api"),
    ]


def test_camerabridge_capture_rejects_external_owner_session(tmp_path, monkeypatch):
    token_path = _write_token(tmp_path)
    state = {
        "session": CameraBridgeSessionSnapshot(
            state="running",
            active_device_id="camera-1",
            owner_id="other-client",
            last_error=None,
        ),
        "devices": [
            CameraBridgeDevice(id="camera-1", name="Built-in Camera", position="front")
        ],
        "capture_photo_result": CameraBridgeCapturedPhoto(
            local_path="/tmp/unused.jpg",
            captured_at="2026-03-22T20:15:00Z",
            device_id="camera-1",
        ),
    }
    monkeypatch.setattr(
        camerabridge_camera_module,
        "CameraBridgeClient",
        _fake_client_factory(state),
    )
    camera = CameraBridgeCamera(
        config=_config(
            tmp_path,
            camera_driver="camerabridge",
            camerabridge_token_path=token_path,
        ),
        camera_settings_service=_camera_settings_service(tmp_path),
    )
    camera.connect()

    with pytest.raises(HardwareBusyError, match="another local client owns"):
        camera.capture()


def test_camerabridge_capture_maps_invalid_state_to_unavailable(tmp_path, monkeypatch):
    token_path = _write_token(tmp_path)
    state = {
        "devices": [
            CameraBridgeDevice(id="camera-1", name="Built-in Camera", position="front")
        ],
        "capture_photo_result": CameraBridgeCapturedPhoto(
            local_path="/tmp/unused.jpg",
            captured_at="2026-03-22T20:15:00Z",
            device_id="camera-1",
        ),
        "start_session_result": CameraBridgeClientError(
            status_code=409,
            code="invalid_state",
            message="Camera permission is denied",
        ),
    }
    monkeypatch.setattr(
        camerabridge_camera_module,
        "CameraBridgeClient",
        _fake_client_factory(state),
    )
    camera = CameraBridgeCamera(
        config=_config(
            tmp_path,
            camera_driver="camerabridge",
            camerabridge_token_path=token_path,
        ),
        camera_settings_service=_camera_settings_service(tmp_path),
    )
    camera.connect()

    with pytest.raises(HardwareUnavailableError, match="Camera permission is denied"):
        camera.capture()


def test_camerabridge_capture_maps_connection_failure_to_unavailable(
    tmp_path,
    monkeypatch,
):
    token_path = _write_token(tmp_path)
    state = {
        "health": CameraBridgeConnectionError("unreachable"),
    }
    monkeypatch.setattr(
        camerabridge_camera_module,
        "CameraBridgeClient",
        _fake_client_factory(state),
    )
    camera = CameraBridgeCamera(
        config=_config(
            tmp_path,
            camera_driver="camerabridge",
            camerabridge_token_path=token_path,
        ),
        camera_settings_service=_camera_settings_service(tmp_path),
    )
    camera.connect()

    with pytest.raises(HardwareUnavailableError, match="CameraBridge is unavailable"):
        camera.capture()
