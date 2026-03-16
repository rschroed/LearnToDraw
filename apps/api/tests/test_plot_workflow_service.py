from __future__ import annotations

import time

from learn_to_draw_api.adapters.mock_camera import MockCamera
from learn_to_draw_api.adapters.mock_plotter import MockPlotter
from learn_to_draw_api.models import PatternAssetCreateRequest
from learn_to_draw_api.services.captures import CaptureStore
from learn_to_draw_api.services.plot_workflow import (
    PlotAssetStore,
    PlotRunStore,
    PlotWorkflowService,
)


def _build_service(tmp_path, *, plotter=None, camera=None):
    return PlotWorkflowService(
        plotter=plotter or MockPlotter(plot_delay_s=0),
        camera=camera or MockCamera(capture_delay_s=0),
        capture_store=CaptureStore(tmp_path / "captures", "/captures"),
        asset_store=PlotAssetStore(tmp_path / "plot_assets", "/plot-assets"),
        run_store=PlotRunStore(tmp_path / "plot_runs"),
    )


def _wait_for_terminal_run(service: PlotWorkflowService, run_id: str):
    for _ in range(200):
        run = service.get_run(run_id)
        if run.status in {"completed", "failed"}:
            return run
        time.sleep(0.01)
    raise AssertionError("Run did not reach a terminal state in time.")


def test_plot_asset_store_separates_public_url_from_disk_path(tmp_path):
    store = PlotAssetStore(tmp_path / "plot_assets", "plot-assets/")
    asset = store.save_svg(
        svg_text="<svg xmlns='http://www.w3.org/2000/svg' width='100' height='100' />",
        name="../odd name.svg",
        kind="uploaded_svg",
    )

    assert asset.file_path.endswith(".svg")
    assert "/plot-assets/" in asset.public_url
    assert "%20" not in asset.public_url
    assert ".." not in asset.public_url


def test_plot_workflow_service_completes_pattern_run(tmp_path):
    service = _build_service(tmp_path)
    asset = service.create_pattern_asset(
        PatternAssetCreateRequest(pattern_id="test-grid")
    )

    run = service.create_run(asset.id)
    completed = _wait_for_terminal_run(service, run.id)

    assert completed.status == "completed"
    assert completed.capture is not None
    assert completed.stage_states["plot"].status == "completed"
    assert completed.stage_states["capture"].status == "completed"
    assert completed.plotter_run_details["document_id"] == asset.id


def test_plot_workflow_service_fails_before_capture_on_plot_error(tmp_path):
    service = _build_service(
        tmp_path,
        plotter=MockPlotter(plot_delay_s=0, fail_on_plot=True),
    )
    asset = service.create_pattern_asset(
        PatternAssetCreateRequest(pattern_id="test-grid")
    )

    run = service.create_run(asset.id)
    failed = _wait_for_terminal_run(service, run.id)

    assert failed.status == "failed"
    assert failed.capture is None
    assert failed.stage_states["plot"].status == "failed"
    assert failed.stage_states["capture"].status == "pending"


def test_plot_workflow_service_fails_after_plot_on_camera_error(tmp_path):
    service = _build_service(
        tmp_path,
        camera=MockCamera(capture_delay_s=0, fail_on_capture=True),
    )
    asset = service.create_pattern_asset(
        PatternAssetCreateRequest(pattern_id="test-grid")
    )

    run = service.create_run(asset.id)
    failed = _wait_for_terminal_run(service, run.id)

    assert failed.status == "failed"
    assert failed.stage_states["plot"].status == "completed"
    assert failed.stage_states["capture"].status == "failed"
    assert failed.error == "Mock camera failed to capture."


def test_plot_workflow_service_skips_capture_for_diagnostic_run(tmp_path):
    service = _build_service(tmp_path)
    asset = service.create_pattern_asset(
        PatternAssetCreateRequest(pattern_id="dash-row")
    )

    run = service.create_run(asset.id, purpose="diagnostic", capture_mode="skip")
    completed = _wait_for_terminal_run(service, run.id)

    assert completed.status == "completed"
    assert completed.purpose == "diagnostic"
    assert completed.capture is None
    assert completed.stage_states["capture"].status == "completed"
    assert completed.camera_run_details["capture_mode"] == "skip"
