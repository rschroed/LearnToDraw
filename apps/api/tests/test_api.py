from __future__ import annotations

import json
import time
from datetime import datetime, timezone

import cv2
from fastapi.testclient import TestClient
import httpx
import numpy as np

from learn_to_draw_api.adapters.axidraw_models import resolve_axidraw_model_info
from learn_to_draw_api.adapters.mock_camera import MockCamera
from learn_to_draw_api.adapters.mock_plotter import MockPlotter
from learn_to_draw_api.adapters.camera import CaptureArtifact
from learn_to_draw_api.api import create_app
from learn_to_draw_api.config import AppConfig
from learn_to_draw_api.services import drawing_sessions as drawing_sessions_module
from learn_to_draw_api.models import (
    DeviceStatus,
    DrawingSession,
    HardwareOperationError,
    PlotDocument,
    PlotResult,
)


def create_test_client(tmp_path, *, plotter=None, camera=None, config_overrides=None):
    config_overrides = config_overrides or {}
    app = create_app(
        AppConfig(
            captures_dir=tmp_path / "captures",
            plot_assets_dir=tmp_path / "plot_assets",
            plot_runs_dir=tmp_path / "plot_runs",
            calibration_dir=tmp_path / "calibration",
            device_settings_dir=tmp_path / "device-settings",
            workspace_dir=tmp_path / "workspace",
            drawing_sessions_dir=tmp_path / "drawing-sessions",
            **config_overrides,
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
        if payload["status"] == "awaiting_capture_review":
            review = payload["capture"]["review"]
            confirm_response = client.post(
                f"/api/plot-runs/{run_id}/capture-review/confirm",
                json={"corners": review["proposed_corners"]},
            )
            assert confirm_response.status_code == 200
            continue
        if payload["status"] in {"completed", "failed"}:
            return payload
        time.sleep(0.01)
    raise AssertionError("Plot run did not finish in time.")


def wait_for_run_status(client: TestClient, run_id: str, statuses: set[str]):
    for _ in range(200):
        response = client.get(f"/api/plot-runs/{run_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in statuses:
            return payload
        time.sleep(0.01)
    raise AssertionError(f"Plot run did not reach expected state: {statuses}")


def wait_for_session_status(client: TestClient, session_id: str, statuses: set[str]):
    for _ in range(200):
        response = client.get(f"/api/drawing-sessions/{session_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in statuses:
            return payload
        time.sleep(0.01)
    raise AssertionError(f"Drawing session did not reach expected state: {statuses}")


def drive_v2_session_until(
    client: TestClient,
    session_id: str,
    statuses: set[str],
):
    confirmed_run_ids = set()
    for _ in range(500):
        client.post(f"/api/drawing-sessions/{session_id}/heartbeat")
        session = client.get(f"/api/drawing-sessions/{session_id}").json()
        if session["status"] in statuses:
            return session
        run_id = session.get("current_run_id")
        if session["status"] == "awaiting_capture_review" and run_id not in confirmed_run_ids:
            run = client.get(f"/api/plot-runs/{run_id}").json()
            response = client.post(
                f"/api/plot-runs/{run_id}/capture-review/confirm",
                json={"corners": run["capture"]["review"]["proposed_corners"]},
            )
            assert response.status_code == 200
            confirmed_run_ids.add(run_id)
        time.sleep(0.01)
    raise AssertionError(f"Drawing session did not reach expected state: {statuses}")


def _jpeg_bytes(width: int = 640, height: int = 480) -> bytes:
    image = np.full((height, width, 3), 245, dtype=np.uint8)
    cv2.rectangle(image, (80, 60), (width - 80, height - 60), (32, 32, 32), 6)
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok
    return encoded.tobytes()


def _blank_jpeg_bytes(width: int = 640, height: int = 480) -> bytes:
    image = np.full((height, width, 3), 250, dtype=np.uint8)
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok
    return encoded.tobytes()


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


def test_runtime_openai_advisor_configuration_is_redacted_and_used(tmp_path, monkeypatch):
    class Response:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return {"output_text": json.dumps(self._payload)}

    criteria = [
        "Create a loose botanical character.",
        "Vary the flowers rather than repeating a symbol.",
        "Preserve breathing room around the cluster.",
    ]

    def fake_post(_url, **kwargs):
        schema_name = kwargs["json"]["text"]["format"]["name"]
        if schema_name == "initial_drawing_plan":
            return Response(
                {
                        "summary": "Build a loose cluster of varied flowers.",
                        "paper_strategy": "Use the center and preserve breathing room.",
                        "completion_intent": "Stop when the field feels lively.",
                        "creative_criteria": criteria,
                        "svg": (
                            '<svg xmlns="http://www.w3.org/2000/svg" '
                            'width="170mm" height="257mm" viewBox="0 0 170 257">'
                            '<circle cx="85" cy="128" r="10"/></svg>'
                        ),
                }
            )
        return Response(
            {
                "summary": "The varied focal gesture is a sound first layer.",
                "decision": "accept",
                "criterion_assessments": [
                    {
                        "rank": rank,
                        "outcome": "meets",
                        "assessment": "The candidate visibly supports this criterion.",
                    }
                    for rank in range(1, 4)
                ],
                "svg": None,
            }
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    api_key = "sk-test-runtime-secret"

    with create_test_client(tmp_path) as client:
        startup = client.get("/api/drawing-advisor/configuration")
        configured = client.post(
            "/api/drawing-advisor/configuration",
            json={"api_key": api_key, "model": "vision-model"},
        )
        model_updated = client.patch(
            "/api/drawing-advisor/configuration",
            json={"model": "vision-model-v2"},
        )
        created = client.post(
            "/api/drawing-sessions",
            json={"intent": "A loose field of flowers"},
        ).json()
        planned = wait_for_session_status(
            client,
            created["id"],
            {"awaiting_approval", "failed"},
        )
        cleared = client.delete("/api/drawing-advisor/configuration")

    assert startup.json() == {
        "advisor": {
            "driver": "disabled",
            "available": False,
            "model": None,
            "message": (
                "Drawing advisor is disabled. Set LEARN_TO_DRAW_DRAWING_ADVISOR=openai, "
                "OPENAI_API_KEY, and LEARN_TO_DRAW_OPENAI_MODEL to enable it."
            ),
        },
        "source": "startup",
        "persistence": "process_memory",
        "clears_on_restart": True,
    }
    assert configured.status_code == 200
    assert configured.json()["advisor"] == {
        "driver": "openai",
        "available": True,
        "model": "vision-model",
        "message": None,
    }
    assert configured.json()["source"] == "runtime"
    assert api_key not in configured.text
    assert model_updated.status_code == 200
    assert model_updated.json()["advisor"]["model"] == "vision-model-v2"
    assert model_updated.json()["source"] == "runtime"
    assert api_key not in model_updated.text
    assert planned["status"] == "awaiting_approval"
    assert planned["advisor"]["driver"] == "openai"
    assert planned["current_proposal"]["advisor_model"] == "vision-model-v2"
    assert cleared.json()["advisor"]["driver"] == "disabled"
    assert cleared.json()["source"] == "startup"


def test_invalid_runtime_advisor_configuration_preserves_active_advisor(tmp_path):
    with create_test_client(
        tmp_path,
        config_overrides={"drawing_advisor_driver": "mock"},
    ) as client:
        invalid = client.post(
            "/api/drawing-advisor/configuration",
            json={"api_key": "   ", "model": "vision-model"},
        )
        model_only = client.patch(
            "/api/drawing-advisor/configuration",
            json={"model": "vision-model-v2"},
        )
        current = client.get("/api/drawing-advisor/configuration")

    assert invalid.status_code == 400
    assert invalid.json() == {"detail": "Enter an OpenAI API key."}
    assert model_only.status_code == 409
    assert model_only.json() == {
        "detail": "Configure an OpenAI API key before changing the model."
    }
    assert current.json()["advisor"]["driver"] == "mock"
    assert current.json()["source"] == "startup"


def test_model_only_update_requires_an_active_openai_credential(tmp_path):
    with create_test_client(
        tmp_path,
        config_overrides={
            "drawing_advisor_driver": "openai",
            "openai_model": "startup-model",
        },
    ) as client:
        response = client.patch(
            "/api/drawing-advisor/configuration",
            json={"model": "replacement-model"},
        )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Configure an OpenAI API key before changing the model."
    }


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
        latest_capture = client.get("/api/captures/latest").json()["capture"]

    assert capture_response.status_code == 200
    capture_payload = capture_response.json()
    assert capture_payload["capture"]["public_url"].startswith("/captures/")
    assert capture_payload["capture"]["normalized"] is None
    assert latest_capture["id"] == capture_payload["capture"]["id"]
    assert latest_capture["normalized"] is None


class StubRealCamera:
    driver = "camerabridge"

    def __init__(self) -> None:
        self._connected = False
        self._selected_device_id = "camera-1"
        self._status = DeviceStatus(
            available=True,
            connected=False,
            busy=False,
            error=None,
            driver=self.driver,
            last_updated=datetime.now(timezone.utc),
            details={
                "base_url": "http://127.0.0.1:8731",
                "token_path": "/tmp/auth-token",
                "token_readable": True,
                "service_available": True,
                "permission_status": "authorized",
                "permission_message": None,
                "permission_next_step_kind": None,
                "session_state": "stopped",
                "session_owner_id": None,
                "active_device_id": None,
                "devices": [
                    {
                        "id": "camera-1",
                        "name": "Built-in Camera",
                        "position": "front",
                    }
                ],
                "device_count": 1,
                "persisted_selected_device_id": "camera-1",
                "effective_selected_device_id": "camera-1",
                "selection_required": False,
                "readiness_state": "ready",
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

    def set_selected_device(self, device_id: str | None) -> DeviceStatus:
        self._selected_device_id = device_id
        self._status = self._status.model_copy(
            update={
                "details": {
                    **self._status.details,
                    "persisted_selected_device_id": device_id,
                    "effective_selected_device_id": device_id,
                    "selection_required": device_id is None,
                    "readiness_state": "ready" if device_id is not None else "needs_device_selection",
                }
            }
        )
        return self.get_status()

    def capture(self) -> CaptureArtifact:
        self._status = self._status.model_copy(
            update={
                "available": True,
                "connected": True,
                "details": {
                    **self._status.details,
                    "last_capture_id": "capture-real-001",
                    "resolution": "640x480",
                },
            }
        )
        return CaptureArtifact(
            capture_id="capture-real-001",
            timestamp=datetime.now(timezone.utc),
            filename="capture-real-001.jpg",
            content=_jpeg_bytes(),
            media_type="image/jpeg",
            width=640,
            height=480,
        )


class LowConfidenceCamera:
    driver = "mock-camera"

    def __init__(self) -> None:
        self._connected = False
        self._capture_count = 0

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def get_status(self) -> DeviceStatus:
        return MockCamera(driver=self.driver).get_status().model_copy(
            update={"connected": self._connected}
        )

    def set_selected_device(self, device_id: str | None):
        return self.get_status()

    def capture(self) -> CaptureArtifact:
        self._capture_count += 1
        return CaptureArtifact(
            capture_id=f"capture-review-{self._capture_count}",
            timestamp=datetime.now(timezone.utc),
            filename=f"capture-review-{self._capture_count}.jpg",
            content=_blank_jpeg_bytes(),
            media_type="image/jpeg",
            width=640,
            height=480,
        )


class CountingPlotter(MockPlotter):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.plot_count = 0

    def plot(self, document):
        self.plot_count += 1
        return super().plot(document)


def test_capture_endpoint_persists_real_camera_artifact(tmp_path):
    with create_test_client(tmp_path, camera=StubRealCamera()) as client:
        status_before = client.get("/api/hardware/status")
        capture_response = client.post("/api/camera/capture")
        latest_capture = client.get("/api/captures/latest").json()["capture"]

    assert status_before.status_code == 200
    assert status_before.json()["camera"]["details"]["readiness_state"] == "ready"
    assert capture_response.status_code == 200
    payload = capture_response.json()
    assert payload["status"]["driver"] == "camerabridge"
    assert payload["capture"]["mime_type"] == "image/jpeg"
    assert payload["capture"]["public_url"].endswith(".jpg")
    assert payload["capture"]["width"] == 640
    assert payload["capture"]["height"] == 480
    assert latest_capture["id"] == payload["capture"]["id"]
    assert latest_capture["normalized"] is None


def test_camera_device_endpoint_updates_selected_device(tmp_path):
    with create_test_client(tmp_path, camera=StubRealCamera()) as client:
        response = client.post("/api/camera/device", json={"device_id": "camera-1"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["message"] == "Camera device preference updated."
    assert payload["status"]["driver"] == "camerabridge"
    assert payload["status"]["details"]["persisted_selected_device_id"] == "camera-1"
    assert payload["status"]["details"]["effective_selected_device_id"] == "camera-1"


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
        == "Configured drawable area exceeds the plotter bounds height."
    )
    assert payload["page_size_mm"]["height_mm"] == 297.0


def test_plotter_workspace_endpoint_allows_letter_paper_when_margins_keep_drawing_in_bounds(
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
            axidraw_model=1,
        ),
        plotter=MockPlotter(),
        camera=MockCamera(capture_delay_s=0),
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/plotter/workspace",
            json={
                "page_width_mm": 279.4,
                "page_height_mm": 215.9,
                "margin_left_mm": 10,
                "margin_top_mm": 10,
                "margin_right_mm": 10,
                "margin_bottom_mm": 10,
            },
        )

    assert response.status_code == 200
    workspace = response.json()["workspace"]
    assert workspace["page_size_mm"] == {"width_mm": 279.4, "height_mm": 215.9}
    assert workspace["drawable_area_mm"] == {"width_mm": 259.4, "height_mm": 195.9}


def test_plotter_workspace_endpoint_rejects_drawable_area_larger_than_bounds(tmp_path):
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
    assert (
        response.json()["detail"]
        == "Configured drawable area exceeds the plotter bounds width."
    )


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
    assert completed["capture"]["normalized"] is not None
    assert completed["capture"]["normalized"]["metadata"]["target_frame_source"] == "prepared_svg"
    assert completed["capture"]["normalized"]["metadata"]["frame"]["kind"] == "page_aligned"
    assert completed["capture"]["normalized"]["metadata"]["frame"]["version"] == 2
    assert completed["capture"]["normalized"]["metadata"]["frame"]["page_width_mm"] == 210.0
    assert completed["capture"]["normalized"]["metadata"]["frame"]["page_height_mm"] == 297.0
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
    assert completed["plotter_run_details"]["preparation"]["preparation_audit"]["comparison_frame_version"] == 1
    assert completed["plotter_run_details"]["preparation"]["preparation_audit"]["placement_origin_x_mm"] == 20.0
    assert completed["plotter_run_details"]["preparation"]["preparation_audit"]["source_content_left_ratio"] == 0.083333
    assert latest.json()["run"]["id"] == run["id"]
    assert recent.json()["runs"][0]["id"] == run["id"]


def test_plot_run_capture_review_confirm_endpoint_creates_v2_registration(tmp_path):
    with create_test_client(
        tmp_path,
        plotter=MockPlotter(plot_delay_s=0),
        camera=LowConfidenceCamera(),
    ) as client:
        asset_response = client.post(
            "/api/plot-assets/patterns",
            json={"pattern_id": "test-grid"},
        )
        run_response = client.post(
            "/api/plot-runs", json={"asset_id": asset_response.json()["id"]}
        )
        pending = wait_for_run_status(
            client, run_response.json()["id"], {"awaiting_capture_review"}
        )
        assert pending["capture"]["review"]["proposal"]["status"] == "fallback"
        assert (
            pending["capture"]["review"]["proposal"]["method"]
            == "inset_5_percent_v1"
        )
        corners = pending["capture"]["review"]["proposed_corners"]
        confirm_response = client.post(
            f"/api/plot-runs/{pending['id']}/capture-review/confirm",
            json={"corners": corners},
        )
        completed = wait_for_run_completion(client, pending["id"])

    assert confirm_response.status_code == 200
    assert confirm_response.json()["run"]["status"] == "capturing"
    assert completed["capture"]["review"]["registration_version"] == 2
    assert completed["capture"]["review"]["review_mode"] == "manual_corners"
    assert completed["capture"]["review"]["confirmation_source"] == "manual"
    assert completed["capture"]["review"]["proposal"]["status"] == "fallback"
    metadata = completed["capture"]["normalized"]["metadata"]
    assert metadata["method"] == "manual_corners_v2"
    assert metadata["frame"]["version"] == 2
    assert metadata["transform"]["source_space"] == "raw_capture_px"
    assert metadata["transform"]["destination_space"] == "page_px"
    assert metadata["transform"]["inverse_matrix"] is not None


def test_plot_run_capture_review_confirm_rejects_invalid_quad_without_state_change(tmp_path):
    with create_test_client(
        tmp_path,
        plotter=MockPlotter(plot_delay_s=0),
        camera=LowConfidenceCamera(),
    ) as client:
        asset_response = client.post(
            "/api/plot-assets/patterns",
            json={"pattern_id": "test-grid"},
        )
        run_response = client.post(
            "/api/plot-runs", json={"asset_id": asset_response.json()["id"]}
        )
        pending = wait_for_run_status(
            client, run_response.json()["id"], {"awaiting_capture_review"}
        )
        invalid_corners = {
            "top_left": [50.0, 50.0],
            "top_right": [590.0, 430.0],
            "bottom_right": [590.0, 50.0],
            "bottom_left": [50.0, 430.0],
        }
        confirm_response = client.post(
            f"/api/plot-runs/{pending['id']}/capture-review/confirm",
            json={"corners": invalid_corners},
        )
        unchanged = client.get(f"/api/plot-runs/{pending['id']}").json()

    assert confirm_response.status_code == 400
    assert "convex, non-crossing" in confirm_response.json()["detail"]
    assert unchanged["status"] == "awaiting_capture_review"
    assert unchanged["capture"]["review"]["review_status"] == "pending"
    assert unchanged["capture"]["normalized"] is None


def test_completed_v2_capture_review_can_be_refined_without_replotting(tmp_path):
    plotter = MockPlotter(plot_delay_s=0)
    with create_test_client(
        tmp_path,
        plotter=plotter,
        camera=LowConfidenceCamera(),
    ) as client:
        asset_response = client.post(
            "/api/plot-assets/patterns",
            json={"pattern_id": "test-grid"},
        )
        run_response = client.post(
            "/api/plot-runs", json={"asset_id": asset_response.json()["id"]}
        )
        pending = wait_for_run_status(
            client, run_response.json()["id"], {"awaiting_capture_review"}
        )
        initial_corners = pending["capture"]["review"]["proposed_corners"]
        client.post(
            f"/api/plot-runs/{pending['id']}/capture-review/confirm",
            json={"corners": initial_corners},
        )
        completed = wait_for_run_completion(client, pending["id"])
        revised_corners = {
            "top_left": [initial_corners["top_left"][0] + 2, initial_corners["top_left"][1] + 1],
            "top_right": [
                initial_corners["top_right"][0] - 1,
                initial_corners["top_right"][1] + 1,
            ],
            "bottom_right": [
                initial_corners["bottom_right"][0] - 1,
                initial_corners["bottom_right"][1] - 2,
            ],
            "bottom_left": [
                initial_corners["bottom_left"][0] + 2,
                initial_corners["bottom_left"][1] - 2,
            ],
        }

        refine_response = client.post(
            f"/api/plot-runs/{completed['id']}/capture-review/confirm",
            json={"corners": revised_corners},
        )
        refined = wait_for_run_completion(client, completed["id"])

    assert refine_response.status_code == 200
    assert refine_response.json()["run"]["status"] == "capturing"
    assert refined["status"] == "completed"
    assert refined["capture"]["id"] == completed["capture"]["id"]
    assert refined["capture"]["timestamp"] == completed["capture"]["timestamp"]
    assert refined["capture"]["review"]["confirmed_corners"] == revised_corners
    assert refined["capture"]["normalized"]["metadata"]["corners"] == revised_corners


def test_completed_v2_capture_review_rejects_invalid_refinement_without_state_change(tmp_path):
    with create_test_client(
        tmp_path,
        plotter=MockPlotter(plot_delay_s=0),
        camera=LowConfidenceCamera(),
    ) as client:
        asset_response = client.post(
            "/api/plot-assets/patterns",
            json={"pattern_id": "test-grid"},
        )
        run_response = client.post(
            "/api/plot-runs", json={"asset_id": asset_response.json()["id"]}
        )
        pending = wait_for_run_status(
            client, run_response.json()["id"], {"awaiting_capture_review"}
        )
        initial_corners = pending["capture"]["review"]["proposed_corners"]
        client.post(
            f"/api/plot-runs/{pending['id']}/capture-review/confirm",
            json={"corners": initial_corners},
        )
        completed = wait_for_run_completion(client, pending["id"])
        invalid_corners = {
            "top_left": [50.0, 50.0],
            "top_right": [590.0, 430.0],
            "bottom_right": [590.0, 50.0],
            "bottom_left": [50.0, 430.0],
        }

        refine_response = client.post(
            f"/api/plot-runs/{completed['id']}/capture-review/confirm",
            json={"corners": invalid_corners},
        )
        unchanged = client.get(f"/api/plot-runs/{completed['id']}").json()

    assert refine_response.status_code == 400
    assert unchanged["status"] == "completed"
    assert unchanged["capture"]["review"]["confirmed_corners"] == initial_corners
    assert unchanged["capture"]["normalized"]["metadata"]["corners"] == initial_corners


def test_legacy_capture_review_endpoints_are_removed(tmp_path):
    with create_test_client(tmp_path) as client:
        assert client.post("/api/plot-runs/run-1/capture-review/accept").status_code == 404
        assert client.post("/api/plot-runs/run-1/capture-review/adjust").status_code == 404
        assert client.post("/api/plot-runs/run-1/capture-review/reuse-last").status_code == 404


def test_drawing_session_runs_observes_proposes_and_approves_next_layer(tmp_path):
    with create_test_client(
        tmp_path,
        plotter=MockPlotter(plot_delay_s=0),
        camera=LowConfidenceCamera(),
        config_overrides={"drawing_advisor_driver": "mock"},
    ) as client:
        asset = client.post(
            "/api/plot-assets/patterns",
            json={"pattern_id": "test-grid"},
        ).json()
        created_response = client.post(
            "/api/drawing-sessions",
            json={
                "intent": "Grow a lively field of flowers",
                "initial_asset_id": asset["id"],
                "iteration_limit": 2,
                "mode": "additive",
            },
        )
        assert created_response.status_code == 200
        created = created_response.json()
        first_run_id = created["iterations"][0]["run_id"]
        wait_for_run_completion(client, first_run_id)

        observed = client.get(f"/api/drawing-sessions/{created['id']}").json()
        advice_response = client.post(
            f"/api/drawing-sessions/{created['id']}/advice"
        )
        latest = client.get("/api/drawing-sessions/latest").json()["session"]

        assert observed["status"] == "observed"
        assert advice_response.status_code == 200
        proposed = advice_response.json()
        assert proposed["status"] == "proposal_ready"
        proposal = proposed["iterations"][0]["next_proposal"]
        assert proposal["advisor_driver"] == "mock"
        assert proposal["asset"]["kind"] == "generated_svg"
        assert "field of flowers" in proposal["interpretation"]
        proposal_response = client.get(
            f"/api/plot-assets/{proposal['asset']['id']}"
        )
        assert proposal_response.status_code == 200
        assert latest["id"] == created["id"]

        approve_response = client.post(
            f"/api/drawing-sessions/{created['id']}/iterations"
        )
        assert approve_response.status_code == 200
        approved = approve_response.json()
        assert approved["status"] == "running"
        assert len(approved["iterations"]) == 2
        second_run_id = approved["iterations"][1]["run_id"]
        assert proposal["asset"]["id"] == approved["iterations"][1]["asset"]["id"]
        wait_for_run_completion(client, second_run_id)
        completed = client.get(f"/api/drawing-sessions/{created['id']}").json()
        gallery_summary = client.get("/api/drawing-sessions").json()["sessions"][0]

    assert completed["status"] == "completed"
    assert len(completed["iterations"]) == 2
    assert completed["iterations"][0]["next_proposal"]["approved_run_id"] == second_run_id
    assert gallery_summary["preview_url"].endswith("-rectified-grayscale.png")

    with create_test_client(
        tmp_path,
        plotter=MockPlotter(plot_delay_s=0),
        camera=LowConfidenceCamera(),
        config_overrides={"drawing_advisor_driver": "mock"},
    ) as restarted_client:
        reloaded = restarted_client.get(
            f"/api/drawing-sessions/{created['id']}"
        ).json()

    assert reloaded["status"] == "completed"
    assert [item["run_id"] for item in reloaded["iterations"]] == [
        first_run_id,
        second_run_id,
    ]
    assert reloaded["session_version"] == 1


def test_v2_drawing_session_plans_revises_and_approves_without_early_motion(tmp_path):
    with create_test_client(
        tmp_path,
        plotter=MockPlotter(plot_delay_s=0),
        camera=LowConfidenceCamera(),
        config_overrides={"drawing_advisor_driver": "mock"},
    ) as client:
        created_response = client.post(
            "/api/drawing-sessions",
            json={"intent": "A curious pelican riding a bicycle"},
        )
        assert created_response.status_code == 200
        created = created_response.json()
        assert created["session_version"] == 2
        assert created["iterations"] == []
        assert client.get("/api/plot-runs").json()["runs"] == []

        planned = wait_for_session_status(
            client,
            created["id"],
            {"awaiting_approval"},
        )
        first_asset_id = planned["current_proposal"]["asset"]["id"]
        assert planned["plan"]["paper_strategy"]
        assert len(planned["plan"]["creative_criteria"]) == 3
        assert planned["current_proposal"]["quality_review"]["decision"] == "accept"
        assert (
            len(
                planned["current_proposal"]["quality_review"][
                    "criterion_assessments"
                ]
            )
            == 3
        )
        assert planned["iteration_limit"] is None
        assert client.get("/api/plot-runs").json()["runs"] == []

        earlier_v2_payload = json.loads(json.dumps(planned))
        earlier_v2_payload["plan"].pop("creative_criteria")
        earlier_v2_payload["current_proposal"].pop("quality_review")
        earlier_v2_session = DrawingSession.model_validate(earlier_v2_payload)
        assert earlier_v2_session.plan.creative_criteria == []
        assert earlier_v2_session.current_proposal.quality_review is None

        message_response = client.post(
            f"/api/drawing-sessions/{created['id']}/messages",
            json={"text": "Make the pose feel less formal."},
        )
        assert message_response.status_code == 200
        revised = wait_for_session_status(
            client,
            created["id"],
            {"awaiting_approval"},
        )
        assert revised["planning_generation"] == 2
        assert revised["current_proposal"]["asset"]["id"] != first_asset_id
        assert revised["queued_guidance"] == ["Make the pose feel less formal."]

        summaries = client.get("/api/drawing-sessions").json()["sessions"]
        assert summaries[0]["id"] == created["id"]
        assert summaries[0]["preview_url"] == revised["current_proposal"]["asset"]["public_url"]

        missing_preflight = client.post(
            f"/api/drawing-sessions/{created['id']}/approve",
            json={"paper_ready": False},
        )
        assert missing_preflight.status_code == 400
        assert missing_preflight.json() == {
            "detail": "Confirm that a blank sheet and pen are ready before drawing."
        }
        assert client.get("/api/plot-runs").json()["runs"] == []

        approved_response = client.post(
            f"/api/drawing-sessions/{created['id']}/approve",
            json={"paper_ready": True},
        )
        assert approved_response.status_code == 200
        approved = approved_response.json()
        assert approved["status"] == "running"
        assert approved["authorization"]["approved_at"] is not None
        assert approved["pass_count"] == 1
        assert len(approved["iterations"]) == 1
        assert approved["paper_preflight"] == {
            "confirmed_at": approved["approved_at"],
            "page_width_mm": 210.0,
            "page_height_mm": 297.0,
            "drawable_width_mm": 170.0,
            "drawable_height_mm": 257.0,
        }
        assert any(
            event["type"] == "paper_confirmed" for event in approved["events"]
        )


def test_v2_unplotted_session_can_be_abandoned_without_motion(tmp_path):
    with create_test_client(
        tmp_path,
        plotter=MockPlotter(plot_delay_s=0),
        config_overrides={"drawing_advisor_driver": "mock"},
    ) as client:
        created = client.post(
            "/api/drawing-sessions",
            json={"intent": "An idea I changed my mind about"},
        ).json()
        wait_for_session_status(client, created["id"], {"awaiting_approval"})

        response = client.post(
            f"/api/drawing-sessions/{created['id']}/abandon"
        )
        unchanged = client.post(
            f"/api/drawing-sessions/{created['id']}/abandon"
        )

    assert response.status_code == 200
    abandoned = response.json()
    assert abandoned["status"] == "abandoned"
    assert abandoned["abandoned_at"] is not None
    assert abandoned["pass_count"] == 0
    assert abandoned["events"][-1]["type"] == "session_abandoned"
    assert unchanged.json()["status"] == "abandoned"


def test_v2_drawing_session_disabled_advisor_pauses_without_motion(tmp_path):
    with create_test_client(tmp_path) as client:
        created = client.post(
            "/api/drawing-sessions",
            json={"intent": "A quiet field of flowers"},
        ).json()
        paused = wait_for_session_status(client, created["id"], {"paused"})

        assert "Drawing advisor is disabled" in paused["error"]
        assert paused["current_proposal"] is None
        assert client.get("/api/plot-runs").json()["runs"] == []


def test_v2_session_auto_continues_consumes_guidance_and_completes(tmp_path):
    plotter = CountingPlotter(plot_delay_s=0.03)
    with create_test_client(
        tmp_path,
        plotter=plotter,
        camera=LowConfidenceCamera(),
        config_overrides={"drawing_advisor_driver": "mock"},
    ) as client:
        created = client.post(
            "/api/drawing-sessions",
            json={"intent": "A loose field of flowers"},
        ).json()
        planned = wait_for_session_status(client, created["id"], {"awaiting_approval"})
        approved = client.post(
            f"/api/drawing-sessions/{planned['id']}/approve",
            json={"paper_ready": True},
        ).json()
        guidance_response = client.post(
            f"/api/drawing-sessions/{planned['id']}/messages",
            json={"text": "Make the flowers less regular."},
        )
        assert guidance_response.status_code == 200

        completed = drive_v2_session_until(
            client,
            approved["id"],
            {"completed"},
        )

    assert completed["pass_count"] == 2
    assert plotter.plot_count == 2
    decisions = [
        event for event in completed["events"] if event["type"] == "agent_decision"
    ]
    assert decisions[0]["details"]["guidance"] == [
        "Make the flowers less regular."
    ]
    assert len(decisions[0]["details"]["criterion_assessments"]) == 3
    assert decisions[-1]["details"]["decision"] == "complete"
    assert completed["queued_guidance"] == []


def test_v2_stop_after_pass_prevents_another_plot(tmp_path):
    plotter = CountingPlotter(plot_delay_s=0.05)
    with create_test_client(
        tmp_path,
        plotter=plotter,
        camera=LowConfidenceCamera(),
        config_overrides={"drawing_advisor_driver": "mock"},
    ) as client:
        created = client.post(
            "/api/drawing-sessions",
            json={"intent": "A single thoughtful flower"},
        ).json()
        planned = wait_for_session_status(client, created["id"], {"awaiting_approval"})
        approved = client.post(
            f"/api/drawing-sessions/{planned['id']}/approve",
            json={"paper_ready": True},
        ).json()
        stopped = client.post(
            f"/api/drawing-sessions/{approved['id']}/stop",
            json={"mode": "after_pass"},
        )
        assert stopped.status_code == 200

        paused = drive_v2_session_until(client, approved["id"], {"paused"})
        finished = client.post(
            f"/api/drawing-sessions/{approved['id']}/finish"
        ).json()

    assert paused["authorization"]["stop_requested"] is True
    assert paused["pass_count"] == 1
    assert finished["status"] == "completed"
    assert finished["events"][-1]["details"]["source"] == "user"
    assert plotter.plot_count == 1


def test_v2_finish_request_completes_current_pass_without_another_plot(tmp_path):
    plotter = CountingPlotter(plot_delay_s=0.05)
    with create_test_client(
        tmp_path,
        plotter=plotter,
        camera=LowConfidenceCamera(),
        config_overrides={"drawing_advisor_driver": "mock"},
    ) as client:
        created = client.post(
            "/api/drawing-sessions",
            json={"intent": "One final thoughtful flower"},
        ).json()
        planned = wait_for_session_status(client, created["id"], {"awaiting_approval"})
        approved = client.post(
            f"/api/drawing-sessions/{planned['id']}/approve",
            json={"paper_ready": True},
        ).json()

        active_abandon = client.post(
            f"/api/drawing-sessions/{approved['id']}/abandon"
        )
        finish_response = client.post(
            f"/api/drawing-sessions/{approved['id']}/finish"
        )
        completed = drive_v2_session_until(client, approved["id"], {"completed"})

    assert active_abandon.status_code == 409
    assert finish_response.status_code == 200
    assert completed["pass_count"] == 1
    assert completed["authorization"]["finish_requested"] is False
    assert completed["events"][-1]["type"] == "session_completed"
    assert completed["events"][-1]["details"]["source"] == "user"
    assert plotter.plot_count == 1


def test_v2_emergency_stop_cancels_plot_without_capture_or_continuation(tmp_path):
    plotter = CountingPlotter(plot_delay_s=1)
    with create_test_client(
        tmp_path,
        plotter=plotter,
        camera=LowConfidenceCamera(),
        config_overrides={"drawing_advisor_driver": "mock"},
    ) as client:
        created = client.post(
            "/api/drawing-sessions",
            json={"intent": "A drawing that can be interrupted"},
        ).json()
        planned = wait_for_session_status(client, created["id"], {"awaiting_approval"})
        approved = client.post(
            f"/api/drawing-sessions/{planned['id']}/approve",
            json={"paper_ready": True},
        ).json()
        active_run = wait_for_run_status(
            client,
            approved["current_run_id"],
            {"plotting"},
        )

        stop_response = client.post(
            f"/api/drawing-sessions/{approved['id']}/stop",
            json={"mode": "emergency"},
        )
        assert stop_response.status_code == 200
        cancelled = wait_for_run_status(
            client,
            active_run["id"],
            {"cancelled"},
        )
        paused = wait_for_session_status(client, approved["id"], {"paused"})

    assert cancelled["capture"] is None
    assert cancelled["interruption_reason"] == "operator_emergency_stop"
    assert cancelled["progress_artifact"]["public_url"].endswith(
        "-paused-progress.svg"
    )
    assert cancelled["stage_states"]["plot"]["status"] == "cancelled"
    assert paused["pass_count"] == 1
    assert paused["authorization"]["stop_requested"] is True
    assert plotter.plot_count == 1


def test_v2_attention_timeout_pauses_before_a_second_plot(tmp_path, monkeypatch):
    monkeypatch.setattr(drawing_sessions_module, "ATTENTION_GRACE_SECONDS", 0)
    plotter = CountingPlotter(plot_delay_s=0)
    with create_test_client(
        tmp_path,
        plotter=plotter,
        camera=LowConfidenceCamera(),
        config_overrides={"drawing_advisor_driver": "mock"},
    ) as client:
        created = client.post(
            "/api/drawing-sessions",
            json={"intent": "An attended drawing"},
        ).json()
        planned = wait_for_session_status(client, created["id"], {"awaiting_approval"})
        approved = client.post(
            f"/api/drawing-sessions/{planned['id']}/approve",
            json={"paper_ready": True},
        ).json()
        first_run = wait_for_run_status(
            client,
            approved["current_run_id"],
            {"awaiting_capture_review"},
        )
        client.post(
            f"/api/plot-runs/{first_run['id']}/capture-review/confirm",
            json={"corners": first_run["capture"]["review"]["proposed_corners"]},
        )
        paused = wait_for_session_status(client, approved["id"], {"paused"})

    assert "disconnected" in paused["error"]
    assert paused["pass_count"] == 1
    assert plotter.plot_count == 1


def test_capture_retry_preserves_attempts_and_does_not_replot(tmp_path):
    plotter = CountingPlotter(plot_delay_s=0)
    with create_test_client(
        tmp_path,
        plotter=plotter,
        camera=LowConfidenceCamera(),
    ) as client:
        asset = client.post(
            "/api/plot-assets/patterns",
            json={"pattern_id": "tiny-square"},
        ).json()
        run = client.post("/api/plot-runs", json={"asset_id": asset["id"]}).json()
        first = wait_for_run_status(
            client,
            run["id"],
            {"awaiting_capture_review"},
        )
        first_capture_id = first["capture"]["id"]

        retry_response = client.post(f"/api/plot-runs/{run['id']}/capture/retry")
        assert retry_response.status_code == 200
        second = wait_for_run_status(
            client,
            run["id"],
            {"awaiting_capture_review"},
        )

    assert second["capture"]["id"] != first_capture_id
    assert [item["id"] for item in second["capture_attempts"]] == [
        first_capture_id,
        second["capture"]["id"],
    ]
    assert plotter.plot_count == 1


def test_v2_backend_restart_requires_explicit_resume(tmp_path):
    with create_test_client(
        tmp_path,
        plotter=CountingPlotter(plot_delay_s=0),
        camera=LowConfidenceCamera(),
        config_overrides={"drawing_advisor_driver": "mock"},
    ) as client:
        created = client.post(
            "/api/drawing-sessions",
            json={"intent": "A restart-safe drawing"},
        ).json()
        planned = wait_for_session_status(client, created["id"], {"awaiting_approval"})
        approved = client.post(
            f"/api/drawing-sessions/{planned['id']}/approve",
            json={"paper_ready": True},
        ).json()
        completed = drive_v2_session_until(client, approved["id"], {"completed"})

    session_path = tmp_path / "drawing-sessions" / f"{completed['id']}.json"
    persisted = json.loads(session_path.read_text(encoding="utf-8"))
    persisted["status"] = "running"
    persisted["completed_at"] = None
    session_path.write_text(json.dumps(persisted), encoding="utf-8")
    restarted_plotter = CountingPlotter(plot_delay_s=0)

    with create_test_client(
        tmp_path,
        plotter=restarted_plotter,
        camera=LowConfidenceCamera(),
        config_overrides={"drawing_advisor_driver": "mock"},
    ) as restarted_client:
        recovered = restarted_client.get(
            f"/api/drawing-sessions/{completed['id']}"
        ).json()

    assert recovered["status"] == "paused"
    assert "Backend restarted" in recovered["error"]
    assert restarted_plotter.plot_count == 0


def test_drawing_session_disabled_advisor_leaves_observation_retryable(tmp_path):
    with create_test_client(
        tmp_path,
        plotter=MockPlotter(plot_delay_s=0),
        camera=LowConfidenceCamera(),
    ) as client:
        asset = client.post(
            "/api/plot-assets/patterns",
            json={"pattern_id": "test-grid"},
        ).json()
        created = client.post(
            "/api/drawing-sessions",
            json={
                "intent": "A pelican riding a bicycle",
                "initial_asset_id": asset["id"],
                "iteration_limit": 3,
            },
        ).json()
        wait_for_run_completion(client, created["iterations"][0]["run_id"])

        advice_response = client.post(
            f"/api/drawing-sessions/{created['id']}/advice"
        )
        unchanged = client.get(f"/api/drawing-sessions/{created['id']}").json()

    assert advice_response.status_code == 503
    assert "Drawing advisor is disabled" in advice_response.json()["detail"]
    assert unchanged["status"] == "observed"
    assert unchanged["iterations"][0]["next_proposal"] is None


def test_drawing_session_rejects_iteration_limit_outside_safe_range(tmp_path):
    with create_test_client(tmp_path) as client:
        response = client.post(
            "/api/drawing-sessions",
            json={
                "intent": "A field of flowers",
                "initial_asset_id": "asset-id",
                "iteration_limit": 11,
            },
        )

    assert response.status_code == 422


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
    assert completed["capture"]["normalized"]["metadata"]["output"]["width"] == 1448
    assert completed["capture"]["normalized"]["metadata"]["output"]["height"] == 2048
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
