from __future__ import annotations

import time
from pathlib import Path

from learn_to_draw_api.adapters.camera import CaptureArtifact
from learn_to_draw_api.adapters.mock_camera import MockCamera
from learn_to_draw_api.adapters.mock_plotter import MockPlotter
from learn_to_draw_api.models import (
    PatternAssetCreateRequest,
    PlotterCalibrationRequest,
    PlotterWorkspaceRequest,
)
from learn_to_draw_api.services.captures import CaptureStore
from learn_to_draw_api.services.plot_workflow import (
    PlotAssetStore,
    PlotRunStore,
    PlotWorkflowService,
)
from learn_to_draw_api.config import AppConfig
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
        self._capture_count = 0

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
        self._capture_count += 1
        return CaptureArtifact(
            capture_id=f"real-capture-{self._capture_count}",
            timestamp=MockCamera(capture_delay_s=0).capture().timestamp,
            filename=f"real-capture-{self._capture_count}.jpg",
            content=b"jpeg-bytes",
            media_type="image/jpeg",
            width=640,
            height=480,
        )


def _build_service(tmp_path, *, plotter=None, camera=None, config_overrides=None):
    config_overrides = config_overrides or {}
    config = AppConfig(
        captures_dir=tmp_path / "captures-config",
        plot_assets_dir=tmp_path / "plot_assets-config",
        plot_runs_dir=tmp_path / "plot_runs-config",
        calibration_dir=tmp_path / "calibration",
        device_settings_dir=tmp_path / "device-settings",
        workspace_dir=tmp_path / "workspace",
        **config_overrides,
    )
    calibration_service = PlotterCalibrationService(
        store=PlotterCalibrationStore(tmp_path / "calibration"),
        config=config,
    )
    device_settings_service = PlotterDeviceSettingsService(
        store=PlotterDeviceSettingsStore(tmp_path / "device-settings"),
        config=config,
    )
    workspace_service = PlotterWorkspaceService(
        store=PlotterWorkspaceStore(tmp_path / "workspace"),
        config=config,
        device_settings_service=device_settings_service,
    )
    return PlotWorkflowService(
        plotter=plotter or MockPlotter(plot_delay_s=0),
        camera=camera or MockCamera(capture_delay_s=0),
        capture_store=CaptureStore(tmp_path / "captures", "/captures"),
        asset_store=PlotAssetStore(tmp_path / "plot_assets", "/plot-assets"),
        run_store=PlotRunStore(tmp_path / "plot_runs"),
        calibration_service=calibration_service,
        device_settings_service=device_settings_service,
        workspace_service=workspace_service,
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
    assert completed.observed_result is not None
    assert completed.observed_result.capture.id == completed.capture.id
    assert completed.observed_result.camera_driver == "mock-camera"
    assert completed.observed_result.duration_ms >= 0
    assert completed.prepared_artifact is not None
    assert completed.prepared_artifact.public_url.endswith(f"/{completed.id}-prepared.svg")
    assert completed.prepared_artifact.mime_type == "image/svg+xml"
    assert completed.stage_states["plot"].status == "completed"
    assert completed.stage_states["capture"].status == "completed"
    assert completed.plotter_run_details["document_id"] == asset.id
    assert completed.plotter_run_details["calibration"]["driver_calibration"]["native_res_factor"] == 1016.0
    assert completed.plotter_run_details["device"]["plotter_bounds_source"] == "config_default"
    assert completed.plotter_run_details["workspace"]["page_size_mm"]["width_mm"] == 210.0
    prepared_svg_path = Path(completed.prepared_artifact.file_path)
    assert prepared_svg_path.exists()
    assert completed.plotter_run_details["prepared_svg_path"] == completed.prepared_artifact.file_path
    prepared_svg_text = prepared_svg_path.read_text(encoding="utf-8")
    assert prepared_svg_text != Path(asset.file_path).read_text(encoding="utf-8")
    assert "<g transform=" in prepared_svg_text
    assert 'width="210mm"' in prepared_svg_text
    assert 'height="297mm"' in prepared_svg_text
    assert 'viewBox="0 0 210 297"' in prepared_svg_text
    assert completed.plotter_run_details["preparation"]["workspace_audit"]["page_within_plotter_bounds"] is True
    assert completed.plotter_run_details["preparation"]["workspace_audit"]["drawable_origin_x_mm"] == 20.0
    assert completed.plotter_run_details["preparation"]["workspace_audit"]["remaining_bounds_right_mm"] == 0.0
    assert completed.plotter_run_details["preparation"]["prepared_width_mm"] == 160.0
    assert completed.plotter_run_details["preparation"]["prepared_height_mm"] == 120.0
    assert completed.plotter_run_details["preparation"]["preparation_audit"]["strategy"] == "fit_top_left"
    assert completed.plotter_run_details["preparation"]["preparation_audit"]["fit_scale"] == 0.166667
    assert completed.plotter_run_details["preparation"]["preparation_audit"]["placement_origin_x_mm"] == 20.0
    assert completed.plotter_run_details["preparation"]["preparation_audit"]["content_max_x_mm"] == 180.0
    assert completed.plotter_run_details["preparation"]["preparation_audit"]["prepared_within_drawable_area"] is True


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
    assert failed.observed_result is None
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
    assert failed.observed_result is None
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
    assert completed.observed_result is None
    assert completed.stage_states["capture"].status == "completed"
    assert completed.camera_run_details["capture_mode"] == "skip"


def test_plot_workflow_service_persists_real_camera_capture(tmp_path):
    service = _build_service(tmp_path, camera=StubRealCamera())
    asset = service.create_pattern_asset(
        PatternAssetCreateRequest(pattern_id="test-grid")
    )

    run = service.create_run(asset.id)
    completed = _wait_for_terminal_run(service, run.id)

    assert completed.status == "completed"
    assert completed.capture is not None
    assert completed.observed_result is not None
    assert completed.capture.mime_type == "image/jpeg"
    assert completed.capture.public_url.endswith(".jpg")
    assert completed.observed_result.capture.mime_type == "image/jpeg"
    assert completed.observed_result.camera_driver == "camerabridge"
    assert completed.camera_run_details["driver"] == "camerabridge"
    assert completed.camera_run_details["resolution"] == "640x480"


def test_builtin_patterns_use_explicit_physical_units(tmp_path):
    service = _build_service(tmp_path)

    tiny_square = service.create_pattern_asset(PatternAssetCreateRequest(pattern_id="tiny-square"))
    dash_row = service.create_pattern_asset(PatternAssetCreateRequest(pattern_id="dash-row"))
    tiny_square_svg = Path(tiny_square.file_path).read_text(encoding="utf-8")
    dash_row_svg = Path(dash_row.file_path).read_text(encoding="utf-8")

    assert 'width="20mm"' in tiny_square_svg
    assert 'height="20mm"' in tiny_square_svg
    assert 'width="40mm"' in dash_row_svg
    assert 'height="12mm"' in dash_row_svg


def test_normal_preparation_max_fits_unitless_upload(tmp_path):
    service = _build_service(tmp_path)
    asset = service.create_uploaded_asset(
        filename="unitless.svg",
        content=(
            b"<svg xmlns='http://www.w3.org/2000/svg' width='200' height='100' "
            b"viewBox='0 0 200 100'><path d='M 0 0 H 200' /></svg>"
        ),
        content_type="image/svg+xml",
    )

    run = service.create_run(asset.id)
    completed = _wait_for_terminal_run(service, run.id)

    assert completed.status == "completed"
    assert completed.plotter_run_details["preparation"]["prepared_width_mm"] == 170.0
    assert completed.plotter_run_details["preparation"]["prepared_height_mm"] == 85.0
    assert completed.plotter_run_details["preparation"]["drawable_width_mm"] == 170.0
    assert completed.plotter_run_details["preparation"]["drawable_height_mm"] == 257.0
    assert completed.plotter_run_details["preparation"]["plotter_bounds_width_mm"] == 210.0
    assert completed.plotter_run_details["preparation"]["plotter_bounds_source"] == "config_default"
    assert completed.plotter_run_details["preparation"]["units_inferred"] is True
    assert completed.plotter_run_details["preparation"]["workspace_audit"]["page_within_plotter_bounds"] is True
    assert completed.plotter_run_details["preparation"]["workspace_audit"]["drawable_area_positive"] is True
    assert completed.plotter_run_details["preparation"]["workspace_audit"]["drawable_origin_x_mm"] == 20.0
    assert completed.plotter_run_details["preparation"]["workspace_audit"]["drawable_origin_y_mm"] == 20.0
    assert completed.plotter_run_details["preparation"]["workspace_audit"]["remaining_bounds_right_mm"] == 0.0
    assert completed.plotter_run_details["preparation"]["workspace_audit"]["remaining_bounds_bottom_mm"] == 0.0
    assert completed.plotter_run_details["preparation"]["preparation_audit"]["strategy"] == "fit_top_left"
    assert completed.plotter_run_details["preparation"]["preparation_audit"]["fit_scale"] == 0.85
    assert completed.plotter_run_details["preparation"]["preparation_audit"]["prepared_within_drawable_area"] is True
    assert completed.plotter_run_details["preparation"]["preparation_audit"]["overflow_x_mm"] == 0.0
    assert completed.plotter_run_details["preparation"]["preparation_audit"]["overflow_y_mm"] == 0.0
    assert completed.plotter_run_details["preparation"]["preparation_audit"]["placement_origin_x_mm"] == 20.0
    assert completed.plotter_run_details["preparation"]["preparation_audit"]["placement_origin_y_mm"] == 20.0
    assert completed.plotter_run_details["preparation"]["preparation_audit"]["content_max_x_mm"] == 190.0
    assert completed.plotter_run_details["preparation"]["preparation_audit"]["content_max_y_mm"] == 105.0
    assert completed.plotter_run_details["preparation"]["preparation_audit"]["prepared_viewbox_min_x"] == 0.0
    assert completed.plotter_run_details["preparation"]["preparation_audit"]["prepared_viewbox_min_y"] == 0.0
    assert completed.plotter_run_details["preparation"]["preparation_audit"]["prepared_viewbox_width"] == 210.0
    assert completed.plotter_run_details["preparation"]["preparation_audit"]["prepared_viewbox_height"] == 297.0
    prepared_svg_path = Path(completed.plotter_run_details["prepared_svg_path"])
    prepared_svg_text = prepared_svg_path.read_text(encoding="utf-8")
    assert "<g transform=" in prepared_svg_text
    assert prepared_svg_text.startswith('<svg xmlns="http://www.w3.org/2000/svg"')
    assert 'width="210mm"' in prepared_svg_text
    assert 'height="297mm"' in prepared_svg_text
    assert 'viewBox="0 0 210 297"' in prepared_svg_text


def test_normal_preparation_preserves_smaller_explicit_unit_upload_size(tmp_path):
    service = _build_service(tmp_path)
    asset = service.create_uploaded_asset(
        filename="small-explicit.svg",
        content=(
            b"<svg xmlns='http://www.w3.org/2000/svg' width='40mm' height='20mm' "
            b"viewBox='0 0 200 100'><path d='M 0 0 H 200' /></svg>"
        ),
        content_type="image/svg+xml",
    )

    run = service.create_run(asset.id)
    completed = _wait_for_terminal_run(service, run.id)

    assert completed.status == "completed"
    assert completed.plotter_run_details["preparation"]["prepared_width_mm"] == 40.0
    assert completed.plotter_run_details["preparation"]["prepared_height_mm"] == 20.0
    assert completed.plotter_run_details["preparation"]["preparation_audit"]["fit_scale"] == 0.2
    assert completed.plotter_run_details["preparation"]["preparation_audit"]["strategy"] == "fit_top_left"
    assert completed.plotter_run_details["preparation"]["preparation_audit"]["placement_origin_x_mm"] == 20.0
    assert completed.plotter_run_details["preparation"]["preparation_audit"]["content_max_y_mm"] == 40.0


def test_normal_preparation_downscales_oversized_explicit_unit_upload(tmp_path):
    service = _build_service(tmp_path)
    asset = service.create_uploaded_asset(
        filename="oversized.svg",
        content=(
            b"<svg xmlns='http://www.w3.org/2000/svg' width='200mm' height='260mm' "
            b"viewBox='0 0 200 260'><path d='M 0 0 H 200' /></svg>"
        ),
        content_type="image/svg+xml",
    )

    run = service.create_run(asset.id)
    completed = _wait_for_terminal_run(service, run.id)

    assert completed.status == "completed"
    assert completed.plotter_run_details["preparation"]["workspace_audit"]["page_within_plotter_bounds"] is True
    assert completed.plotter_run_details["preparation"]["prepared_width_mm"] == 170.0
    assert completed.plotter_run_details["preparation"]["prepared_height_mm"] == 221.0
    assert completed.plotter_run_details["preparation"]["preparation_audit"]["strategy"] == "fit_top_left"
    assert completed.plotter_run_details["preparation"]["preparation_audit"]["prepared_within_drawable_area"] is True
    assert completed.plotter_run_details["preparation"]["preparation_audit"]["fit_scale"] == 0.85
    assert completed.plotter_run_details["preparation"]["preparation_audit"]["overflow_x_mm"] == 0.0
    assert completed.plotter_run_details["preparation"]["preparation_audit"]["overflow_y_mm"] == 0.0


def test_plot_workflow_fails_cleanly_when_workspace_exceeds_current_bounds(tmp_path):
    service = _build_service(
        tmp_path,
        config_overrides={
            "plotter_driver": "axidraw",
            "plotter_bounds_width_mm": 300.0,
            "plotter_bounds_height_mm": 218.0,
        },
    )
    asset = service.create_pattern_asset(PatternAssetCreateRequest(pattern_id="tiny-square"))

    run = service.create_run(asset.id)
    failed = _wait_for_terminal_run(service, run.id)

    assert failed.status == "failed"
    assert failed.error == "Configured page height exceeds the plotter bounds height."
    assert failed.stage_states["prepare"].status == "failed"
    assert failed.stage_states["prepare"].message == "Configured page height exceeds the plotter bounds height."


def test_plot_workflow_records_effective_calibration(tmp_path):
    service = _build_service(tmp_path)
    service._calibration_service.save_axidraw_native_res_factor(  # noqa: SLF001
        PlotterCalibrationRequest(native_res_factor=1905.0)
    )
    asset = service.create_pattern_asset(PatternAssetCreateRequest(pattern_id="tiny-square"))

    run = service.create_run(asset.id)
    completed = _wait_for_terminal_run(service, run.id)

    assert completed.status == "completed"
    assert completed.plotter_run_details["calibration"]["motion_scale"] == 1.875
    assert (
        completed.plotter_run_details["calibration"]["driver_calibration"]["native_res_factor"]
        == 1905.0
    )


def test_plot_workflow_uses_persisted_workspace_for_normal_preparation(tmp_path):
    service = _build_service(tmp_path)
    service._workspace_service.save(  # noqa: SLF001
        PlotterWorkspaceRequest(
            page_width_mm=148,
            page_height_mm=210,
            margin_left_mm=10,
            margin_top_mm=10,
            margin_right_mm=10,
            margin_bottom_mm=10,
        )
    )
    asset = service.create_uploaded_asset(
        filename="unitless.svg",
        content=(
            b"<svg xmlns='http://www.w3.org/2000/svg' width='200' height='100' "
            b"viewBox='0 0 200 100'><path d='M 0 0 H 200' /></svg>"
        ),
        content_type="image/svg+xml",
    )

    run = service.create_run(asset.id)
    completed = _wait_for_terminal_run(service, run.id)

    assert completed.status == "completed"
    assert completed.plotter_run_details["workspace"]["page_size_mm"]["width_mm"] == 148.0
    assert completed.plotter_run_details["preparation"]["drawable_width_mm"] == 128.0
    assert completed.plotter_run_details["preparation"]["drawable_height_mm"] == 190.0
    assert completed.plotter_run_details["device"]["plotter_bounds_mm"]["width_mm"] == 210.0
    assert completed.plotter_run_details["preparation"]["workspace_audit"]["drawable_origin_x_mm"] == 10.0
    assert completed.plotter_run_details["preparation"]["workspace_audit"]["drawable_origin_y_mm"] == 10.0
    assert completed.plotter_run_details["preparation"]["workspace_audit"]["remaining_bounds_right_mm"] == 62.0
    assert completed.plotter_run_details["preparation"]["workspace_audit"]["remaining_bounds_bottom_mm"] == 87.0
    assert completed.plotter_run_details["preparation"]["prepared_width_mm"] == 128.0
    assert completed.plotter_run_details["preparation"]["prepared_height_mm"] == 64.0
    assert completed.plotter_run_details["preparation"]["preparation_audit"]["strategy"] == "fit_top_left"


def test_normal_preparation_places_letter_sized_upload_inside_persisted_workspace(tmp_path):
    service = _build_service(tmp_path)
    service._workspace_service.save(  # noqa: SLF001
        PlotterWorkspaceRequest(
            page_width_mm=210,
            page_height_mm=297,
            margin_left_mm=10,
            margin_top_mm=10,
            margin_right_mm=10,
            margin_bottom_mm=10,
        )
    )
    asset = service.create_uploaded_asset(
        filename="test-print.svg",
        content=(
            b"<svg xmlns='http://www.w3.org/2000/svg' width='612' height='792' "
            b"viewBox='0 0 612 792'><circle cx='306' cy='396' r='107.5' /></svg>"
        ),
        content_type="image/svg+xml",
    )

    run = service.create_run(asset.id)
    completed = _wait_for_terminal_run(service, run.id)

    assert completed.status == "completed"
    assert completed.plotter_run_details["preparation"]["prepared_width_mm"] == 190.0
    assert completed.plotter_run_details["preparation"]["prepared_height_mm"] == 245.882
    assert completed.plotter_run_details["preparation"]["preparation_audit"]["fit_scale"] == 0.310458
    assert completed.plotter_run_details["preparation"]["preparation_audit"]["prepared_viewbox_min_x"] == 0.0
    assert completed.plotter_run_details["preparation"]["preparation_audit"]["prepared_viewbox_min_y"] == 0.0
    assert completed.plotter_run_details["preparation"]["preparation_audit"]["prepared_viewbox_width"] == 210.0
    assert completed.plotter_run_details["preparation"]["preparation_audit"]["prepared_viewbox_height"] == 297.0
    assert completed.plotter_run_details["preparation"]["preparation_audit"]["placement_origin_x_mm"] == 10.0
    assert completed.plotter_run_details["preparation"]["preparation_audit"]["content_max_x_mm"] == 200.0
    prepared_svg_path = Path(completed.plotter_run_details["prepared_svg_path"])
    prepared_svg_text = prepared_svg_path.read_text(encoding="utf-8")
    assert "<g transform=" in prepared_svg_text
    assert prepared_svg_text.startswith('<svg xmlns="http://www.w3.org/2000/svg"')
    assert 'width="210mm"' in prepared_svg_text
    assert 'height="297mm"' in prepared_svg_text
    assert 'viewBox="0 0 210 297"' in prepared_svg_text


def test_normal_preparation_rejects_non_finite_preparation_math(tmp_path):
    service = _build_service(tmp_path)
    asset = service.create_uploaded_asset(
        filename="nan-viewbox.svg",
        content=(
            b"<svg xmlns='http://www.w3.org/2000/svg' width='200' height='100' "
            b"viewBox='0 0 NaN 100'><path d='M 0 0 H 200' /></svg>"
        ),
        content_type="image/svg+xml",
    )

    run = service.create_run(asset.id)
    failed = _wait_for_terminal_run(service, run.id)

    assert failed.status == "failed"
    assert failed.error == "Prepared SVG math produced non-finite bounds or scale."


def test_normal_preparation_is_allowed_for_real_axidraw_plotting(tmp_path):
    service = _build_service(
        tmp_path,
        plotter=MockPlotter(plot_delay_s=0),
    )
    service._plotter.driver = "axidraw-pyapi"  # noqa: SLF001
    asset = service.create_uploaded_asset(
        filename="unitless.svg",
        content=(
            b"<svg xmlns='http://www.w3.org/2000/svg' width='200' height='100' "
            b"viewBox='0 0 200 100'><path d='M 0 0 H 200' /></svg>"
        ),
        content_type="image/svg+xml",
    )

    run = service.create_run(asset.id)
    completed = _wait_for_terminal_run(service, run.id)

    assert completed.status == "completed"
    assert completed.plotter_run_details["preparation"]["preparation_audit"]["strategy"] == "fit_top_left"
