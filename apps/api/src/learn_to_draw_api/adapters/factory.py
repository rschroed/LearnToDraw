from __future__ import annotations

from learn_to_draw_api.adapters.axidraw_client import PyAxiDrawClient
from learn_to_draw_api.adapters.axidraw_plotter import AxiDrawPlotter
from learn_to_draw_api.adapters.mock_camera import MockCamera
from learn_to_draw_api.adapters.mock_plotter import MockPlotter
from learn_to_draw_api.config import AppConfig


def build_plotter_adapter(config: AppConfig):
    driver = config.plotter_driver.strip().lower()
    if driver == "mock":
        return MockPlotter()
    if driver == "axidraw":
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
        )
        return AxiDrawPlotter(client=client, port=config.axidraw_port)
    raise ValueError(f"Unsupported plotter driver '{config.plotter_driver}'.")


def build_camera_adapter():
    return MockCamera()
