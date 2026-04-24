from __future__ import annotations

import threading
import time

import cv2
import numpy as np
import pytest

from learn_to_draw_api.adapters.axidraw_models import resolve_axidraw_model_info
from learn_to_draw_api.adapters.mock_camera import MockCamera
from learn_to_draw_api.adapters.mock_plotter import MockPlotter
from learn_to_draw_api.adapters.camera import CaptureArtifact
from learn_to_draw_api.config import AppConfig
from learn_to_draw_api.models import (
    HardwareBusyError,
    HardwareUnavailableError,
    InvalidArtifactError,
)
from learn_to_draw_api.services.capture_normalization import CaptureNormalizationService
from learn_to_draw_api.services.capture_service import CaptureService
from learn_to_draw_api.services.captures import CaptureStore
from learn_to_draw_api.services.hardware import HardwareService
from learn_to_draw_api.services.plotter_calibration import (
    PlotterCalibrationService,
    PlotterCalibrationStore,
)
from learn_to_draw_api.services.plotter_device_settings import (
    PlotterDeviceSettingsService,
    PlotterDeviceSettingsStore,
)
from learn_to_draw_api.services.plotter_workspace import (
    PlotterWorkspaceService,
    PlotterWorkspaceStore,
)


class StubRealCamera:
    driver = "camerabridge"

    def __init__(self) -> None:
        self._connected = False

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def get_status(self):
        return MockCamera(driver=self.driver).get_status().model_copy(
            update={"connected": self._connected}
        )

    def set_selected_device(self, device_id: str | None):
        return self.get_status()

    def capture(self) -> CaptureArtifact:
        return CaptureArtifact(
            capture_id="real-capture",
            timestamp=MockCamera(capture_delay_s=0).capture().timestamp,
            filename="real-capture.jpg",
            content=_jpeg_bytes(),
            media_type="image/jpeg",
            width=640,
            height=480,
        )


def _jpeg_bytes(width: int = 640, height: int = 480) -> bytes:
    image = np.full((height, width, 3), 245, dtype=np.uint8)
    cv2.rectangle(image, (80, 60), (width - 80, height - 60), (30, 30, 30), 6)
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok
    return encoded.tobytes()


def _capture_service(store: CaptureStore) -> CaptureService:
    return CaptureService(
        store=store,
        normalization_service=CaptureNormalizationService(),
    )


def _wait_for_latest_normalized(store: CaptureStore, capture_id: str):
    for _ in range(200):
        latest = store.latest()
        if latest is not None and latest.id == capture_id and latest.normalized is not None:
            return latest
        time.sleep(0.01)
    raise AssertionError("Capture normalization did not finish in time.")


def build_calibration_service(tmp_path):
    return PlotterCalibrationService(
        store=PlotterCalibrationStore(tmp_path / "calibration"),
        config=AppConfig(
            captures_dir=tmp_path / "captures-config",
            plot_assets_dir=tmp_path / "plot-assets-config",
            plot_runs_dir=tmp_path / "plot-runs-config",
            calibration_dir=tmp_path / "calibration",
            device_settings_dir=tmp_path / "device-settings",
        ),
    )


def build_device_settings_service(tmp_path, *, config_overrides=None):
    config_overrides = config_overrides or {}
    return PlotterDeviceSettingsService(
        store=PlotterDeviceSettingsStore(tmp_path / "device-settings"),
        config=AppConfig(
            captures_dir=tmp_path / "captures-config",
            plot_assets_dir=tmp_path / "plot-assets-config",
            plot_runs_dir=tmp_path / "plot-runs-config",
            calibration_dir=tmp_path / "calibration",
            device_settings_dir=tmp_path / "device-settings",
            workspace_dir=tmp_path / "workspace",
            **config_overrides,
        ),
    )


def build_workspace_service(tmp_path):
    return PlotterWorkspaceService(
        store=PlotterWorkspaceStore(tmp_path / "workspace"),
        config=AppConfig(
            captures_dir=tmp_path / "captures-config",
            plot_assets_dir=tmp_path / "plot-assets-config",
            plot_runs_dir=tmp_path / "plot-runs-config",
            calibration_dir=tmp_path / "calibration",
            device_settings_dir=tmp_path / "device-settings",
            workspace_dir=tmp_path / "workspace",
        ),
        device_settings_service=build_device_settings_service(tmp_path),
    )


def test_capture_store_persists_latest_capture(tmp_path):
    camera = MockCamera(capture_delay_s=0)
    camera.connect()
    store = CaptureStore(tmp_path, "/captures")

    artifact = camera.capture()
    saved = store.save(artifact)

    assert (tmp_path / f"{saved.id}.png").exists()
    assert store.latest() is not None
    assert store.latest().public_url == f"/captures/{saved.id}.png"

    reloaded_store = CaptureStore(tmp_path, "/captures")
    assert reloaded_store.latest() is not None
    assert reloaded_store.latest().id == saved.id


def test_capture_store_normalizes_public_url_independently_of_disk_path(tmp_path):
    camera = MockCamera(capture_delay_s=0)
    camera.connect()
    store = CaptureStore(tmp_path / "nested" / "captures", "captures/")

    artifact = camera.capture()
    artifact = type(artifact)(
        capture_id=artifact.capture_id,
        timestamp=artifact.timestamp,
        filename="../odd name.svg",
        content=artifact.content,
        media_type=artifact.media_type,
        width=artifact.width,
        height=artifact.height,
    )
    saved = store.save(artifact)

    assert saved.file_path.endswith("odd name.svg")
    assert saved.public_url == "/captures/odd%20name.svg"


def test_hardware_service_runs_walk_home_and_capture(tmp_path):
    capture_store = CaptureStore(tmp_path, "/captures")
    service = HardwareService(
        plotter=MockPlotter(origin_delay_s=0),
        camera=MockCamera(capture_delay_s=0),
        capture_store=capture_store,
        capture_service=_capture_service(capture_store),
        calibration_service=build_calibration_service(tmp_path),
        device_settings_service=build_device_settings_service(tmp_path),
        workspace_service=build_workspace_service(tmp_path),
    )
    service.startup()

    origin_response = service.walk_plotter_home()
    capture_response = service.capture_image()

    assert origin_response.status.details["position"] == "walk_home"
    assert capture_response.capture.public_url.endswith(".png")
    assert capture_response.capture.normalized is None
    assert service.latest_capture().capture.id == capture_response.capture.id
    normalized = _wait_for_latest_normalized(capture_store, capture_response.capture.id)
    assert normalized.normalized is not None
    assert normalized.normalized.metadata.target_frame_source == "workspace_drawable_area"
    assert normalized.normalized.metadata.frame is not None
    assert normalized.normalized.metadata.frame.kind == "page_aligned"
    assert normalized.normalized.metadata.frame.page_width_mm == 210.0
    assert normalized.normalized.metadata.frame.page_height_mm == 297.0


def test_hardware_service_persists_real_camera_capture_metadata(tmp_path):
    capture_store = CaptureStore(tmp_path, "/captures")
    service = HardwareService(
        plotter=MockPlotter(origin_delay_s=0),
        camera=StubRealCamera(),
        capture_store=capture_store,
        capture_service=_capture_service(capture_store),
        calibration_service=build_calibration_service(tmp_path),
        device_settings_service=build_device_settings_service(tmp_path),
        workspace_service=build_workspace_service(tmp_path),
    )
    service.startup()

    capture_response = service.capture_image()

    assert capture_response.capture.public_url.endswith(".jpg")
    assert capture_response.capture.mime_type == "image/jpeg"
    assert capture_response.capture.width == 640
    assert capture_response.capture.height == 480
    normalized = _wait_for_latest_normalized(capture_store, capture_response.capture.id)
    assert normalized.normalized is not None
    assert normalized.normalized.metadata.frame is not None
    assert normalized.normalized.metadata.frame.kind == "page_aligned"


def test_hardware_service_rejects_concurrent_plotter_actions(tmp_path):
    capture_store = CaptureStore(tmp_path, "/captures")
    service = HardwareService(
        plotter=MockPlotter(origin_delay_s=0.2),
        camera=MockCamera(capture_delay_s=0),
        capture_store=capture_store,
        capture_service=_capture_service(capture_store),
        calibration_service=build_calibration_service(tmp_path),
        device_settings_service=build_device_settings_service(tmp_path),
        workspace_service=build_workspace_service(tmp_path),
    )
    service.startup()

    worker = threading.Thread(target=service.walk_plotter_home)
    worker.start()
    time.sleep(0.05)

    with pytest.raises(HardwareBusyError):
        service.walk_plotter_home()

    worker.join()


def test_device_settings_service_uses_explicit_axidraw_model_bounds(tmp_path):
    service = build_device_settings_service(
        tmp_path,
        config_overrides={
            "plotter_driver": "axidraw",
            "axidraw_model": 1,
        },
    )

    settings = service.current()

    assert settings.plotter_model is not None
    assert settings.plotter_model.code == 1
    assert settings.nominal_plotter_bounds_source == "model_default"
    model_info = resolve_axidraw_model_info(1)
    assert settings.nominal_plotter_bounds_mm.width_mm == model_info.bounds_width_mm
    assert settings.nominal_plotter_bounds_mm.height_mm == model_info.bounds_height_mm
    assert settings.plotter_bounds_source == "default_clearance"
    assert settings.plotter_bounds_mm.width_mm == round(model_info.bounds_width_mm - 10.0, 3)
    assert settings.plotter_bounds_mm.height_mm == round(model_info.bounds_height_mm - 10.0, 3)


def test_device_settings_service_uses_explicit_axidraw_bounds_override(tmp_path):
    service = build_device_settings_service(
        tmp_path,
        config_overrides={
            "plotter_driver": "axidraw",
            "plotter_bounds_width_mm": 300.0,
            "plotter_bounds_height_mm": 218.0,
        },
    )

    settings = service.current()

    assert settings.plotter_model is None
    assert settings.nominal_plotter_bounds_source == "config_override"
    assert settings.nominal_plotter_bounds_mm.width_mm == 300.0
    assert settings.nominal_plotter_bounds_mm.height_mm == 218.0
    assert settings.plotter_bounds_source == "default_clearance"
    assert settings.plotter_bounds_mm.width_mm == 290.0
    assert settings.plotter_bounds_mm.height_mm == 208.0


def test_device_settings_service_persists_manual_safe_bounds_override(tmp_path):
    service = build_device_settings_service(
        tmp_path,
        config_overrides={
            "plotter_driver": "axidraw",
            "plotter_bounds_width_mm": 300.0,
            "plotter_bounds_height_mm": 218.0,
        },
    )

    saved = service.save_safe_bounds_override(width_mm=280.0, height_mm=200.0)
    current = service.current()

    assert saved.plotter_bounds_source == "manual_override"
    assert saved.plotter_bounds_mm.width_mm == 280.0
    assert saved.plotter_bounds_mm.height_mm == 200.0
    assert current.plotter_bounds_source == "manual_override"
    assert current.plotter_bounds_mm.width_mm == 280.0
    assert current.plotter_bounds_mm.height_mm == 200.0


def test_device_settings_service_clears_manual_safe_bounds_override(tmp_path):
    service = build_device_settings_service(
        tmp_path,
        config_overrides={
            "plotter_driver": "axidraw",
            "plotter_bounds_width_mm": 300.0,
            "plotter_bounds_height_mm": 218.0,
        },
    )
    service.save_safe_bounds_override(width_mm=280.0, height_mm=200.0)

    cleared = service.save_safe_bounds_override(width_mm=None, height_mm=None)

    assert cleared.plotter_bounds_source == "default_clearance"
    assert cleared.plotter_bounds_mm.width_mm == 290.0
    assert cleared.plotter_bounds_mm.height_mm == 208.0


def test_device_settings_service_rejects_unconfigured_axidraw_bounds(tmp_path):
    service = build_device_settings_service(
        tmp_path,
        config_overrides={
            "plotter_driver": "axidraw",
        },
    )

    with pytest.raises(HardwareUnavailableError, match="requires explicit machine bounds configuration"):
        service.current()


def test_device_settings_service_rejects_partial_axidraw_bounds_override(tmp_path):
    service = build_device_settings_service(
        tmp_path,
        config_overrides={
            "plotter_driver": "axidraw",
            "plotter_bounds_width_mm": 300.0,
        },
    )

    with pytest.raises(HardwareUnavailableError, match="Set both LEARN_TO_DRAW_PLOTTER_BOUNDS_WIDTH_MM"):
        service.current()


def test_device_settings_service_rejects_safe_bounds_override_that_exceeds_nominal(tmp_path):
    service = build_device_settings_service(
        tmp_path,
        config_overrides={
            "plotter_driver": "axidraw",
            "plotter_bounds_width_mm": 300.0,
            "plotter_bounds_height_mm": 218.0,
        },
    )

    with pytest.raises(InvalidArtifactError, match="cannot exceed the nominal machine bounds"):
        service.save_safe_bounds_override(width_mm=301.0, height_mm=200.0)


def test_mock_device_settings_keep_nominal_and_operational_bounds_identical(tmp_path):
    service = build_device_settings_service(tmp_path)

    settings = service.current()

    assert settings.nominal_plotter_bounds_mm == settings.plotter_bounds_mm
    assert settings.nominal_plotter_bounds_source == "config_default"
    assert settings.plotter_bounds_source == "config_default"


def test_workspace_service_returns_invalid_state_for_misaligned_axidraw_defaults(tmp_path):
    service = PlotterWorkspaceService(
        store=PlotterWorkspaceStore(tmp_path / "workspace"),
        config=AppConfig(
            captures_dir=tmp_path / "captures-config",
            plot_assets_dir=tmp_path / "plot-assets-config",
            plot_runs_dir=tmp_path / "plot-runs-config",
            calibration_dir=tmp_path / "calibration",
            device_settings_dir=tmp_path / "device-settings",
            workspace_dir=tmp_path / "workspace",
            plotter_driver="axidraw",
            plotter_bounds_width_mm=300.0,
            plotter_bounds_height_mm=218.0,
        ),
        device_settings_service=build_device_settings_service(
            tmp_path,
            config_overrides={
                "plotter_driver": "axidraw",
                "plotter_bounds_width_mm": 300.0,
                "plotter_bounds_height_mm": 218.0,
            },
        ),
    )

    workspace = service.current()

    assert workspace.is_valid is False
    assert workspace.validation_error == "Configured page height exceeds the plotter bounds height."
    with pytest.raises(InvalidArtifactError, match="Configured page height exceeds the plotter bounds height."):
        service.current_validated()
