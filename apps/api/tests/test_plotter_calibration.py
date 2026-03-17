from __future__ import annotations

from learn_to_draw_api.config import AppConfig
from learn_to_draw_api.models import PlotterCalibrationRequest
from learn_to_draw_api.services.plotter_calibration import (
    PlotterCalibrationService,
    PlotterCalibrationStore,
)


def build_service(
    tmp_path,
    *,
    native_res_factor: float | None = None,
):
    config = AppConfig(
        captures_dir=tmp_path / "captures",
        plot_assets_dir=tmp_path / "plot_assets",
        plot_runs_dir=tmp_path / "plot_runs",
        calibration_dir=tmp_path / "calibration",
        axidraw_native_res_factor=native_res_factor,
    )
    return PlotterCalibrationService(
        store=PlotterCalibrationStore(config.calibration_dir),
        config=config,
    )


def test_plotter_calibration_defaults_to_vendor_value(tmp_path):
    service = build_service(tmp_path)

    calibration = service.current()

    assert calibration.source == "vendor_default"
    assert calibration.driver_calibration["native_res_factor"] == 1016.0
    assert calibration.motion_scale == 1.0


def test_plotter_calibration_uses_persisted_value_when_present(tmp_path):
    service = build_service(tmp_path)
    service.save_axidraw_native_res_factor(PlotterCalibrationRequest(native_res_factor=1905.0))

    calibration = service.current()

    assert calibration.source == "persisted"
    assert calibration.driver_calibration["native_res_factor"] == 1905.0
    assert calibration.motion_scale == 1.875


def test_plotter_calibration_env_override_wins_over_persisted_value(tmp_path):
    persisted_service = build_service(tmp_path)
    persisted_service.save_axidraw_native_res_factor(
        PlotterCalibrationRequest(native_res_factor=1905.0)
    )
    overridden_service = build_service(tmp_path, native_res_factor=1800.0)

    calibration = overridden_service.current()

    assert calibration.source == "env_override"
    assert calibration.driver_calibration["native_res_factor"] == 1800.0
    assert calibration.motion_scale == round(1800.0 / 1016.0, 6)
