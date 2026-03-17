from __future__ import annotations

import threading
import time

import pytest

from learn_to_draw_api.adapters.mock_camera import MockCamera
from learn_to_draw_api.adapters.mock_plotter import MockPlotter
from learn_to_draw_api.config import AppConfig
from learn_to_draw_api.models import HardwareBusyError
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


def build_device_settings_service(tmp_path):
    return PlotterDeviceSettingsService(
        store=PlotterDeviceSettingsStore(tmp_path / "device-settings"),
        config=AppConfig(
            captures_dir=tmp_path / "captures-config",
            plot_assets_dir=tmp_path / "plot-assets-config",
            plot_runs_dir=tmp_path / "plot-runs-config",
            calibration_dir=tmp_path / "calibration",
            device_settings_dir=tmp_path / "device-settings",
            workspace_dir=tmp_path / "workspace",
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

    assert (tmp_path / f"{saved.id}.svg").exists()
    assert store.latest() is not None
    assert store.latest().public_url == f"/captures/{saved.id}.svg"

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
    service = HardwareService(
        plotter=MockPlotter(origin_delay_s=0),
        camera=MockCamera(capture_delay_s=0),
        capture_store=CaptureStore(tmp_path, "/captures"),
        calibration_service=build_calibration_service(tmp_path),
        device_settings_service=build_device_settings_service(tmp_path),
        workspace_service=build_workspace_service(tmp_path),
    )
    service.startup()

    origin_response = service.walk_plotter_home()
    capture_response = service.capture_image()

    assert origin_response.status.details["position"] == "walk_home"
    assert capture_response.capture.public_url.endswith(".svg")
    assert service.latest_capture().capture.id == capture_response.capture.id


def test_hardware_service_rejects_concurrent_plotter_actions(tmp_path):
    service = HardwareService(
        plotter=MockPlotter(origin_delay_s=0.2),
        camera=MockCamera(capture_delay_s=0),
        capture_store=CaptureStore(tmp_path, "/captures"),
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
