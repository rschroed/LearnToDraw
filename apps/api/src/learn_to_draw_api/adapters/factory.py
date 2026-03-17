from __future__ import annotations

from learn_to_draw_api.adapters.axidraw_client import PyAxiDrawClient
from learn_to_draw_api.adapters.axidraw_plotter import AxiDrawPlotter
from learn_to_draw_api.adapters.mock_camera import MockCamera
from learn_to_draw_api.adapters.mock_plotter import MockPlotter
from learn_to_draw_api.config import AppConfig
from learn_to_draw_api.models import PlotterCalibration


def build_plotter_adapter(
    config: AppConfig,
    *,
    calibration: PlotterCalibration | None = None,
):
    driver = config.plotter_driver.strip().lower()
    if driver == "mock":
        return MockPlotter()
    if driver == "axidraw":
        native_res_factor = config.axidraw_native_res_factor
        calibration_source = "env_override" if native_res_factor is not None else None
        motion_scale = None
        if native_res_factor is None and calibration is not None:
            calibration_value = calibration.driver_calibration.get("native_res_factor")
            if isinstance(calibration_value, (int, float)):
                native_res_factor = float(calibration_value)
                calibration_source = "persisted"
                motion_scale = calibration.motion_scale
        client = PyAxiDrawClient(
            port=config.axidraw_port,
            speed_pendown=config.axidraw_speed_pendown,
            speed_penup=config.axidraw_speed_penup,
            model=config.axidraw_model,
            pen_pos_up=config.axidraw_pen_pos_up,
            pen_pos_down=config.axidraw_pen_pos_down,
            pen_rate_raise=config.axidraw_pen_rate_raise,
            pen_rate_lower=config.axidraw_pen_rate_lower,
            pen_delay_up=config.axidraw_pen_delay_up,
            pen_delay_down=config.axidraw_pen_delay_down,
            penlift=config.axidraw_penlift,
            config_path=config.axidraw_config_path,
            native_res_factor=native_res_factor,
            calibration_source=calibration_source,
            motion_scale=motion_scale,
        )
        return AxiDrawPlotter(client=client, port=config.axidraw_port)
    raise ValueError(f"Unsupported plotter driver '{config.plotter_driver}'.")


def build_camera_adapter():
    return MockCamera()
