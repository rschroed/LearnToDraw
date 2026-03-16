from __future__ import annotations

import time

from fastapi.testclient import TestClient

from learn_to_draw_api.adapters.mock_camera import MockCamera
from learn_to_draw_api.adapters.mock_plotter import MockPlotter
from learn_to_draw_api.api import create_app
from learn_to_draw_api.config import AppConfig


def create_test_client(tmp_path, *, plotter=None, camera=None):
    app = create_app(
        AppConfig(
            captures_dir=tmp_path / "captures",
            plot_assets_dir=tmp_path / "plot_assets",
            plot_runs_dir=tmp_path / "plot_runs",
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


def test_capture_and_latest_capture_endpoints(tmp_path):
    with create_test_client(tmp_path, camera=MockCamera(capture_delay_s=0)) as client:
        capture_response = client.post("/api/camera/capture")
        latest_response = client.get("/api/captures/latest")

    assert capture_response.status_code == 200
    capture_payload = capture_response.json()
    assert capture_payload["capture"]["public_url"].startswith("/captures/")
    assert latest_response.json()["capture"]["id"] == capture_payload["capture"]["id"]


def test_plotter_return_to_origin_endpoint(tmp_path):
    with create_test_client(tmp_path, plotter=MockPlotter(origin_delay_s=0)) as client:
        response = client.post("/api/plotter/return-to-origin")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"]["details"]["position"] == "origin"


def test_plotter_failure_returns_error(tmp_path):
    with create_test_client(
        tmp_path,
        plotter=MockPlotter(origin_delay_s=0, fail_on_return_to_origin=True),
    ) as client:
        response = client.post("/api/plotter/return-to-origin")

    assert response.status_code == 500
    assert response.json()["detail"] == "Mock plotter failed to return to origin."


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
    assert completed["stage_states"]["capture"]["message"] == "Capture skipped for diagnostic run."


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
