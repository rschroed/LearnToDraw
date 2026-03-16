from __future__ import annotations

import threading
import time

import pytest

from learn_to_draw_api.adapters.mock_camera import MockCamera
from learn_to_draw_api.adapters.mock_plotter import MockPlotter
from learn_to_draw_api.models import HardwareBusyError
from learn_to_draw_api.services.captures import CaptureStore
from learn_to_draw_api.services.hardware import HardwareService


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


def test_hardware_service_runs_return_to_origin_and_capture(tmp_path):
    service = HardwareService(
        plotter=MockPlotter(origin_delay_s=0),
        camera=MockCamera(capture_delay_s=0),
        capture_store=CaptureStore(tmp_path, "/captures"),
    )
    service.startup()

    origin_response = service.return_plotter_to_origin()
    capture_response = service.capture_image()

    assert origin_response.status.details["position"] == "origin"
    assert capture_response.capture.public_url.endswith(".svg")
    assert service.latest_capture().capture.id == capture_response.capture.id


def test_hardware_service_rejects_concurrent_plotter_actions(tmp_path):
    service = HardwareService(
        plotter=MockPlotter(origin_delay_s=0.2),
        camera=MockCamera(capture_delay_s=0),
        capture_store=CaptureStore(tmp_path, "/captures"),
    )
    service.startup()

    worker = threading.Thread(target=service.return_plotter_to_origin)
    worker.start()
    time.sleep(0.05)

    with pytest.raises(HardwareBusyError):
        service.return_plotter_to_origin()

    worker.join()
