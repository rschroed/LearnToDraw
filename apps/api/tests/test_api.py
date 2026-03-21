from __future__ import annotations

import time
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from learn_to_draw_api.adapters.axidraw_models import resolve_axidraw_model_info
from learn_to_draw_api.adapters.mock_camera import MockCamera
from learn_to_draw_api.adapters.mock_plotter import MockPlotter
from learn_to_draw_api.adapters.camera import CaptureArtifact
from learn_to_draw_api.api import create_app
from learn_to_draw_api.config import AppConfig
from learn_to_draw_api.models import (
    DeviceStatus,
    HardwareOperationError,
    PlotDocument,
    PlotResult,
)


def create_test_client(tmp_path, *, plotter=None, camera=None):
    app = create_app(
        AppConfig(
            captures_dir=tmp_path / "captures",
            plot_assets_dir=tmp_path / "plot_assets",
            plot_runs_dir=tmp_path / "plot_runs",
            calibration_dir=tmp_path / "calibration",
            device_settings_dir=tmp_path / "device-settings",
            workspace_dir=tmp_path / "workspace",
        ),
        plotter=plotter,
        camera=camera,
    )
    return TestClient(app)


def wait_for_run_completion(client: TestClient, run_id: str):
    for _ in range(200):
        response = client.get(f"/api/plot-runs/{run_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"completed", "failed"}:
            return payload
        time.sleep(0.01)
    raise AssertionError("Plot run did not finish in time.")


def test_health_and_status_endpoints(tmp_path):
    with create_test_client(tmp_path) as client:
        health = client.get("/api/health")
        status = client.get("/api/hardware/status")

    assert health.status_code == 200
    assert health.json() == {"ok": True}
    assert status.status_code == 200
    payload = status.json()
    assert payload["plotter"]["driver"] == "mock-plotter"
    assert payload["camera"]["driver"] == "mock-camera"


class CompatOnlyPlotter:
    driver = "axidraw-pyapi"

    def __init__(self) -> None:
        self._connected = False
        self._last_updated = datetime.now(timezone.utc)

    def connect(self) -> None:
        self._connected = True
        self._last_updated = datetime.now(timezone.utc)

    def disconnect(self) -> None:
        self._connected = False
        self._last_updated = datetime.now(timezone.utc)

    def get_status(self) -> DeviceStatus:
        return DeviceStatus(
            available=True,
            connected=self._connected,
            busy=False,
            error=None,
            driver=self.driver,
            last_updated=self._last_updated,
            details={
                "api_surface": "installed_axidrawinternal_compat",
                "plot_api_supported": False,
                "manual_api_supported": True,
            },
        )

    def walk_home(self) -> None:
        return None

    def set_pen_heights(self, *, pen_pos_up: int, pen_pos_down: int) -> None:
        return None

    def run_test_action(self, action: str) -> None:
        return None

    def plot(self, document: PlotDocument) -> PlotResult:
        raise HardwareOperationError(
            "Trusted plotting requires the official pyaxidraw Plot API "
            "(plot_setup() and plot_run()). Install the unpacked official "
            "AxiDraw API package with 'pip install .' and retry."
        )


def test_status_reports_plot_capability_flags(tmp_path):
    with create_test_client(tmp_path, plotter=CompatOnlyPlotter()) as client:
        response = client.get("/api/hardware/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["plotter"]["details"]["api_surface"] == "installed_axidrawinternal_compat"
    assert payload["plotter"]["details"]["plot_api_supported"] is False
    assert payload["plotter"]["details"]["manual_api_supported"] is True


def test_capture_and_latest_capture_endpoints(tmp_path):
    with create_test_client(tmp_path, camera=MockCamera(capture_delay_s=0)) as client:
        capture_response = client.post("/api/camera/capture")
        latest_response = client.get("/api/captures/latest")

    assert capture_response.status_code == 200
    capture_payload = capture_response.json()
    assert capture_payload["capture"]["public_url"].startswith("/captures/")
    assert latest_response.json()["capture"]["id"] == capture_payload["capture"]["id"]


class StubRealCamera:
    driver = "opencv-camera"

    def __init__(self) -> None:
        self._connected = False
        self._status = DeviceStatus(
            available=False,
            connected=False,
            busy=False,
            error=None,
            driver=self.driver,
            last_updated=datetime.now(timezone.utc),
            details={
                "camera_index": 0,
                "initialization_state": "uninitialized",
                "last_capture_id": None,
                "resolution": None,
            },
        )

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def get_status(self) -> DeviceStatus:
        return self._status.model_copy(update={"connected": self._connected})

    def capture(self) -> CaptureArtifact:
        self._status = self._status.model_copy(
            update={
                "available": True,
                "connected": True,
                "details": {
                    "camera_index": 0,
                    "initialization_state": "ready",
                    "last_capture_id": "capture-real-001",
                    "resolution": "640x480",
                },
            }
        )
        return CaptureArtifact(
            capture_id="capture-real-001",
            timestamp=datetime.now(timezone.utc),
            filename="capture-real-001.jpg",
            content=b"jpeg-bytes",
            media_type="image/jpeg",
            width=640,
            height=480,
        )


def test_capture_endpoint_persists_real_camera_artifact(tmp_path):
    with create_test_client(tmp_path, camera=StubRealCamera()) as client:
        status_before = client.get("/api/hardware/status")
        capture_response = client.post("/api/camera/capture")
        latest_response = client.get("/api/captures/latest")

    assert status_before.status_code == 200
    assert status_before.json()["camera"]["details"]["initialization_state"] == "uninitialized"
    assert capture_response.status_code == 200
    payload = capture_response.json()
    assert payload["status"]["driver"] == "opencv-camera"
    assert payload["capture"]["mime_type"] == "image/jpeg"
    assert payload["capture"]["public_url"].endswith(".jpg")
    assert payload["capture"]["width"] == 640
    assert payload["capture"]["height"] == 480
    assert latest_response.json()["capture"]["id"] == payload["capture"]["id"]


def test_plotter_walk_home_endpoint(tmp_path):
    with create_test_client(tmp_path, plotter=MockPlotter(origin_delay_s=0)) as client:
        response = client.post("/api/plotter/walk-home")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"]["details"]["position"] == "walk_home"


def test_plotter_failure_returns_error(tmp_path):
    with create_test_client(
        tmp_path,
        plotter=MockPlotter(origin_delay_s=0, fail_on_walk_home=True),
    ) as client:
        response = client.post("/api/plotter/walk-home")

    assert response.status_code == 500
    assert response.json()["detail"] == "Mock plotter failed to walk home."


def test_plotter_test_action_endpoint(tmp_path):
    with create_test_client(tmp_path, plotter=MockPlotter(test_action_delay_s=0)) as client:
        response = client.post("/api/plotter/test-actions", json={"action": "raise_pen"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"]["details"]["last_test_action"] == "raise_pen"


def test_plotter_pen_heights_endpoint(tmp_path):
    with create_test_client(tmp_path, plotter=MockPlotter()) as client:
        response = client.post(
            "/api/plotter/pen-heights",
            json={"pen_pos_up": 64, "pen_pos_down": 26},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"]["details"]["pen_tuning"]["pen_pos_up"] == 64
    assert payload["status"]["details"]["pen_tuning"]["pen_pos_down"] == 26


def test_plotter_calibration_endpoint_persists_native_res_factor(tmp_path):
    with create_test_client(tmp_path) as client:
        initial = client.get("/api/plotter/calibration")
        updated = client.post(
            "/api/plotter/calibration",
            json={"native_res_factor": 1905.0},
        )
        current = client.get("/api/plotter/calibration")

    assert initial.status_code == 200
    assert initial.json()["driver_calibration"]["native_res_factor"] == 1016.0
    assert updated.status_code == 200
    assert updated.json()["calibration"]["driver_calibration"]["native_res_factor"] == 1905.0
    assert updated.json()["calibration"]["motion_scale"] == 1.875
    assert current.status_code == 200
    assert current.json()["source"] == "persisted"
    assert current.json()["driver_calibration"]["native_res_factor"] == 1905.0


def test_plotter_device_endpoint_reports_model_derived_bounds(tmp_path):
    app = create_app(
        AppConfig(
            captures_dir=tmp_path / "captures",
            plot_assets_dir=tmp_path / "plot_assets",
            plot_runs_dir=tmp_path / "plot_runs",
            calibration_dir=tmp_path / "calibration",
            device_settings_dir=tmp_path / "device-settings",
            workspace_dir=tmp_path / "workspace",
            plotter_driver="axidraw",
            axidraw_model=2,
        ),
        plotter=MockPlotter(),
        camera=MockCamera(capture_delay_s=0),
    )
    with TestClient(app) as client:
        response = client.get("/api/plotter/device")

    assert response.status_code == 200
    payload = response.json()
    assert payload["plotter_model"]["code"] == 2
    assert payload["plotter_model"]["label"] == "AxiDraw V3/A3 or SE/A3"
    assert payload["nominal_plotter_bounds_source"] == "model_default"
    model_info = resolve_axidraw_model_info(2)
    assert payload["nominal_plotter_bounds_mm"]["width_mm"] == model_info.bounds_width_mm
    assert payload["nominal_plotter_bounds_mm"]["height_mm"] == model_info.bounds_height_mm
    assert payload["plotter_bounds_source"] == "default_clearance"
    assert payload["plotter_bounds_mm"]["width_mm"] == round(model_info.bounds_width_mm - 10.0, 3)
    assert payload["plotter_bounds_mm"]["height_mm"] == round(
        model_info.bounds_height_mm - 10.0,
        3,
    )


def test_axidraw_without_explicit_bounds_degrades_safely(tmp_path):
    app = create_app(
        AppConfig(
            captures_dir=tmp_path / "captures",
            plot_assets_dir=tmp_path / "plot_assets",
            plot_runs_dir=tmp_path / "plot_runs",
            calibration_dir=tmp_path / "calibration",
            device_settings_dir=tmp_path / "device-settings",
            workspace_dir=tmp_path / "workspace",
            plotter_driver="axidraw",
        ),
        camera=MockCamera(capture_delay_s=0),
    )
    with TestClient(app) as client:
        status_response = client.get("/api/hardware/status")
        device_response = client.get("/api/plotter/device")

    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["plotter"]["driver"] == "axidraw-pyapi"
    assert status_payload["plotter"]["available"] is False
    assert "requires explicit machine bounds configuration" in status_payload["plotter"]["error"]
    assert device_response.status_code == 503
    assert "requires explicit machine bounds configuration" in device_response.json()["detail"]


def test_plotter_device_endpoint_reports_explicit_bounds_override(tmp_path):
    app = create_app(
        AppConfig(
            captures_dir=tmp_path / "captures",
            plot_assets_dir=tmp_path / "plot_assets",
            plot_runs_dir=tmp_path / "plot_runs",
            calibration_dir=tmp_path / "calibration",
            device_settings_dir=tmp_path / "device-settings",
            workspace_dir=tmp_path / "workspace",
            plotter_driver="axidraw",
            plotter_bounds_width_mm=300.0,
            plotter_bounds_height_mm=218.0,
        ),
        plotter=MockPlotter(),
        camera=MockCamera(capture_delay_s=0),
    )
    with TestClient(app) as client:
        response = client.get("/api/plotter/device")

    assert response.status_code == 200
    payload = response.json()
    assert payload["plotter_model"] is None
    assert payload["nominal_plotter_bounds_source"] == "config_override"
    assert payload["nominal_plotter_bounds_mm"]["width_mm"] == 300.0
    assert payload["nominal_plotter_bounds_mm"]["height_mm"] == 218.0
    assert payload["plotter_bounds_source"] == "default_clearance"
    assert payload["plotter_bounds_mm"]["width_mm"] == 290.0
    assert payload["plotter_bounds_mm"]["height_mm"] == 208.0


def test_plotter_safe_bounds_endpoint_persists_manual_override(tmp_path):
    app = create_app(
        AppConfig(
            captures_dir=tmp_path / "captures",
            plot_assets_dir=tmp_path / "plot_assets",
            plot_runs_dir=tmp_path / "plot_runs",
            calibration_dir=tmp_path / "calibration",
            device_settings_dir=tmp_path / "device-settings",
            workspace_dir=tmp_path / "workspace",
            plotter_driver="axidraw",
            plotter_bounds_width_mm=300.0,
            plotter_bounds_height_mm=218.0,
        ),
        plotter=MockPlotter(),
        camera=MockCamera(capture_delay_s=0),
    )
    with TestClient(app) as client:
        updated = client.post(
            "/api/plotter/device/safe-bounds",
            json={"width_mm": 280.0, "height_mm": 200.0},
        )
        current = client.get("/api/plotter/device")

    assert updated.status_code == 200
    assert updated.json()["device"]["plotter_bounds_source"] == "manual_override"
    assert updated.json()["device"]["plotter_bounds_mm"]["width_mm"] == 280.0
    assert updated.json()["device"]["plotter_bounds_mm"]["height_mm"] == 200.0
    assert current.status_code == 200
    assert current.json()["plotter_bounds_source"] == "manual_override"
    assert current.json()["plotter_bounds_mm"]["width_mm"] == 280.0
    assert current.json()["plotter_bounds_mm"]["height_mm"] == 200.0


def test_plotter_safe_bounds_endpoint_clears_to_default_clearance(tmp_path):
    app = create_app(
        AppConfig(
            captures_dir=tmp_path / "captures",
            plot_assets_dir=tmp_path / "plot_assets",
            plot_runs_dir=tmp_path / "plot_runs",
            calibration_dir=tmp_path / "calibration",
            device_settings_dir=tmp_path / "device-settings",
            workspace_dir=tmp_path / "workspace",
            plotter_driver="axidraw",
            plotter_bounds_width_mm=300.0,
            plotter_bounds_height_mm=218.0,
        ),
        plotter=MockPlotter(),
        camera=MockCamera(capture_delay_s=0),
    )
    with TestClient(app) as client:
        client.post(
            "/api/plotter/device/safe-bounds",
            json={"width_mm": 280.0, "height_mm": 200.0},
        )
        cleared = client.post(
            "/api/plotter/device/safe-bounds",
            json={"width_mm": None, "height_mm": None},
        )

    assert cleared.status_code == 200
    assert cleared.json()["device"]["plotter_bounds_source"] == "default_clearance"
    assert cleared.json()["device"]["plotter_bounds_mm"]["width_mm"] == 290.0
    assert cleared.json()["device"]["plotter_bounds_mm"]["height_mm"] == 208.0


def test_plotter_safe_bounds_endpoint_rejects_partial_values(tmp_path):
    app = create_app(
        AppConfig(
            captures_dir=tmp_path / "captures",
            plot_assets_dir=tmp_path / "plot_assets",
            plot_runs_dir=tmp_path / "plot_runs",
            calibration_dir=tmp_path / "calibration",
            device_settings_dir=tmp_path / "device-settings",
            workspace_dir=tmp_path / "workspace",
            plotter_driver="axidraw",
            plotter_bounds_width_mm=300.0,
            plotter_bounds_height_mm=218.0,
        ),
        plotter=MockPlotter(),
        camera=MockCamera(capture_delay_s=0),
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/plotter/device/safe-bounds",
            json={"width_mm": 280.0, "height_mm": None},
        )

    assert response.status_code == 400
    assert "Provide both width_mm and height_mm" in response.json()["detail"]


def test_plotter_workspace_endpoint_persists_page_setup(tmp_path):
    with create_test_client(tmp_path) as client:
        initial = client.get("/api/plotter/workspace")
        updated = client.post(
            "/api/plotter/workspace",
            json={
                "page_width_mm": 148,
                "page_height_mm": 210,
                "margin_left_mm": 10,
                "margin_top_mm": 10,
                "margin_right_mm": 10,
                "margin_bottom_mm": 10,
            },
        )
        current = client.get("/api/plotter/workspace")

    assert initial.status_code == 200
    assert initial.json()["drawable_area_mm"]["width_mm"] == 170.0
    assert updated.status_code == 200
    assert updated.json()["workspace"]["page_size_mm"]["width_mm"] == 148.0
    assert updated.json()["workspace"]["drawable_area_mm"]["width_mm"] == 128.0
    assert current.status_code == 200
    assert current.json()["source"] == "persisted"
    assert current.json()["drawable_area_mm"]["height_mm"] == 190.0


def test_axidraw_workspace_endpoint_returns_invalid_state_when_defaults_exceed_explicit_bounds(
    tmp_path,
):
    app = create_app(
        AppConfig(
            captures_dir=tmp_path / "captures",
            plot_assets_dir=tmp_path / "plot_assets",
            plot_runs_dir=tmp_path / "plot_runs",
            calibration_dir=tmp_path / "calibration",
            device_settings_dir=tmp_path / "device-settings",
            workspace_dir=tmp_path / "workspace",
            plotter_driver="axidraw",
            plotter_bounds_width_mm=300.0,
            plotter_bounds_height_mm=218.0,
        ),
        plotter=MockPlotter(),
        camera=MockCamera(capture_delay_s=0),
    )
    with TestClient(app) as client:
        response = client.get("/api/plotter/workspace")

    assert response.status_code == 200
    payload = response.json()
    assert payload["is_valid"] is False
    assert (
        payload["validation_error"]
        == "Configured page height exceeds the plotter bounds height."
    )
    assert payload["page_size_mm"]["height_mm"] == 297.0


def test_plotter_workspace_endpoint_rejects_page_larger_than_bounds(tmp_path):
    with create_test_client(tmp_path) as client:
        response = client.post(
            "/api/plotter/workspace",
            json={
                "page_width_mm": 300,
                "page_height_mm": 297,
                "margin_left_mm": 10,
                "margin_top_mm": 10,
                "margin_right_mm": 10,
                "margin_bottom_mm": 10,
            },
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Configured page width exceeds the plotter bounds width."


def test_upload_plot_asset_endpoint(tmp_path):
    svg = b"<svg xmlns='http://www.w3.org/2000/svg' width='100' height='100'></svg>"

    with create_test_client(tmp_path) as client:
        response = client.post(
            "/api/plot-assets/upload",
            files={"file": ("sample.svg", svg, "image/svg+xml")},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["kind"] == "uploaded_svg"
    assert payload["public_url"].startswith("/plot-assets/")


def test_upload_plot_asset_rejects_invalid_svg(tmp_path):
    with create_test_client(tmp_path) as client:
        response = client.post(
            "/api/plot-assets/upload",
            files={"file": ("sample.svg", b"not svg", "image/svg+xml")},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Provided content is not valid XML/SVG."


def test_pattern_asset_and_plot_run_endpoints(tmp_path):
    with create_test_client(
        tmp_path,
        plotter=MockPlotter(plot_delay_s=0),
        camera=MockCamera(capture_delay_s=0),
    ) as client:
        asset_response = client.post(
            "/api/plot-assets/patterns",
            json={"pattern_id": "test-grid"},
        )
        assert asset_response.status_code == 200
        asset = asset_response.json()

        run_response = client.post("/api/plot-runs", json={"asset_id": asset["id"]})
        assert run_response.status_code == 200
        run = run_response.json()

        completed = wait_for_run_completion(client, run["id"])
        latest = client.get("/api/plot-runs/latest")
        recent = client.get("/api/plot-runs")

    assert completed["status"] == "completed"
    assert completed["capture"]["public_url"].startswith("/captures/")
    assert completed["observed_result"]["capture"]["id"] == completed["capture"]["id"]
    assert completed["observed_result"]["camera_driver"] == "mock-camera"
    assert completed["prepared_artifact"]["public_url"].startswith("/plot-run-artifacts/")
    assert completed["prepared_artifact"]["mime_type"] == "image/svg+xml"
    assert completed["plotter_run_details"]["prepared_svg_path"].endswith("-prepared.svg")
    prepared_artifact_response = client.get(completed["prepared_artifact"]["public_url"])
    assert prepared_artifact_response.status_code == 200
    assert prepared_artifact_response.headers["content-type"].startswith("image/svg+xml")
    assert "<svg" in prepared_artifact_response.text
    assert completed["plotter_run_details"]["preparation"]["source_units"] == "mm"
    assert completed["plotter_run_details"]["calibration"]["driver_calibration"]["native_res_factor"] == 1016.0
    assert completed["plotter_run_details"]["preparation"]["page_width_mm"] == 210.0
    assert completed["plotter_run_details"]["preparation"]["drawable_width_mm"] == 170.0
    assert completed["plotter_run_details"]["preparation"]["workspace_audit"]["page_within_plotter_bounds"] is True
    assert completed["plotter_run_details"]["preparation"]["preparation_audit"]["strategy"] == "fit_top_left"
    assert completed["plotter_run_details"]["preparation"]["preparation_audit"]["placement_origin_x_mm"] == 20.0
    assert latest.json()["run"]["id"] == run["id"]
    assert recent.json()["runs"][0]["id"] == run["id"]


def test_diagnostic_plot_run_skips_capture(tmp_path):
    with create_test_client(
        tmp_path,
        plotter=MockPlotter(plot_delay_s=0),
        camera=MockCamera(capture_delay_s=0),
    ) as client:
        asset_response = client.post(
            "/api/plot-assets/patterns",
            json={"pattern_id": "dash-row"},
        )
        asset = asset_response.json()

        run_response = client.post(
            "/api/plot-runs",
            json={
                "asset_id": asset["id"],
                "purpose": "diagnostic",
                "capture_mode": "skip",
            },
        )
        run = run_response.json()
        completed = wait_for_run_completion(client, run["id"])

    assert completed["status"] == "completed"
    assert completed["purpose"] == "diagnostic"
    assert completed["capture"] is None
    assert completed["observed_result"] is None
    assert completed["stage_states"]["capture"]["message"] == "Capture skipped for diagnostic run."
    assert (
        completed["plotter_run_details"]["preparation"]["preparation_audit"]["strategy"]
        == "diagnostic_passthrough"
    )


def test_normal_preparation_accepts_unitless_upload(tmp_path):
    svg = b"<svg xmlns='http://www.w3.org/2000/svg' width='200' height='100' viewBox='0 0 200 100'></svg>"

    with create_test_client(
        tmp_path,
        plotter=MockPlotter(plot_delay_s=0),
        camera=MockCamera(capture_delay_s=0),
    ) as client:
        asset_response = client.post(
            "/api/plot-assets/upload",
            files={"file": ("sample.svg", svg, "image/svg+xml")},
        )
        asset = asset_response.json()
        run_response = client.post("/api/plot-runs", json={"asset_id": asset["id"]})
        completed = wait_for_run_completion(client, run_response.json()["id"])

    assert completed["status"] == "completed"
    assert completed["plotter_run_details"]["preparation"]["units_inferred"] is True
    assert completed["observed_result"]["capture"]["id"] == completed["capture"]["id"]
    assert completed["plotter_run_details"]["preparation"]["prepared_width_mm"] == 170.0
    assert completed["plotter_run_details"]["preparation"]["workspace_audit"]["drawable_origin_x_mm"] == 20.0
    assert completed["plotter_run_details"]["preparation"]["preparation_audit"]["strategy"] == "fit_top_left"
    assert completed["plotter_run_details"]["preparation"]["preparation_audit"]["fit_scale"] == 0.85
    assert completed["plotter_run_details"]["preparation"]["preparation_audit"]["prepared_viewbox_min_x"] == 0.0


def test_plot_run_conflict_returns_409(tmp_path):
    with create_test_client(
        tmp_path,
        plotter=MockPlotter(plot_delay_s=0.2),
        camera=MockCamera(capture_delay_s=0.2),
    ) as client:
        asset_response = client.post(
            "/api/plot-assets/patterns",
            json={"pattern_id": "test-grid"},
        )
        asset_id = asset_response.json()["id"]

        first = client.post("/api/plot-runs", json={"asset_id": asset_id})
        second = client.post("/api/plot-runs", json={"asset_id": asset_id})

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["detail"] == "A plot run is already active."


def test_plot_run_fails_clearly_without_official_plot_support(tmp_path):
    with create_test_client(
        tmp_path,
        plotter=CompatOnlyPlotter(),
        camera=MockCamera(capture_delay_s=0),
    ) as client:
        asset_response = client.post(
            "/api/plot-assets/patterns",
            json={"pattern_id": "tiny-square"},
        )
        run_response = client.post("/api/plot-runs", json={"asset_id": asset_response.json()["id"]})
        completed = wait_for_run_completion(client, run_response.json()["id"])

    assert completed["status"] == "failed"
    assert "official pyaxidraw Plot API" in completed["error"]
