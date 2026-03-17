from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class AppConfig:
    captures_dir: Path
    plot_assets_dir: Path
    plot_runs_dir: Path
    calibration_dir: Path = field(default_factory=lambda: Path("artifacts/calibration"))
    device_settings_dir: Path = field(default_factory=lambda: Path("artifacts/device_settings"))
    workspace_dir: Path = field(default_factory=lambda: Path("artifacts/workspace"))
    plotter_driver: str = "mock"
    axidraw_port: Optional[str] = None
    axidraw_speed_pendown: Optional[int] = None
    axidraw_speed_penup: Optional[int] = None
    axidraw_model: Optional[int] = None
    axidraw_pen_pos_up: Optional[int] = None
    axidraw_pen_pos_down: Optional[int] = None
    axidraw_pen_rate_raise: Optional[int] = None
    axidraw_pen_rate_lower: Optional[int] = None
    axidraw_pen_delay_up: Optional[int] = None
    axidraw_pen_delay_down: Optional[int] = None
    axidraw_penlift: Optional[int] = None
    axidraw_config_path: Optional[Path] = None
    axidraw_native_res_factor: Optional[float] = None
    plotter_bounds_width_mm: Optional[float] = None
    plotter_bounds_height_mm: Optional[float] = None
    plot_page_width_mm: float = 210.0
    plot_page_height_mm: float = 297.0
    plot_margin_left_mm: float = 20.0
    plot_margin_top_mm: float = 20.0
    plot_margin_right_mm: float = 20.0
    plot_margin_bottom_mm: float = 20.0
    capture_url_prefix: str = "/captures"
    plot_assets_url_prefix: str = "/plot-assets"
    cors_origins: tuple[str, ...] = (
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    )

    @classmethod
    def from_env(cls) -> "AppConfig":
        repo_root = Path(__file__).resolve().parents[4]
        captures_dir = Path(
            os.getenv(
                "LEARN_TO_DRAW_CAPTURES_DIR",
                repo_root / "artifacts" / "captures",
            )
        )
        plot_assets_dir = Path(
            os.getenv(
                "LEARN_TO_DRAW_PLOT_ASSETS_DIR",
                repo_root / "artifacts" / "plot_assets",
            )
        )
        plot_runs_dir = Path(
            os.getenv(
                "LEARN_TO_DRAW_PLOT_RUNS_DIR",
                repo_root / "artifacts" / "plot_runs",
            )
        )
        calibration_dir = Path(
            os.getenv(
                "LEARN_TO_DRAW_CALIBRATION_DIR",
                repo_root / "artifacts" / "calibration",
            )
        )
        device_settings_dir = Path(
            os.getenv(
                "LEARN_TO_DRAW_DEVICE_SETTINGS_DIR",
                repo_root / "artifacts" / "device_settings",
            )
        )
        workspace_dir = Path(
            os.getenv(
                "LEARN_TO_DRAW_WORKSPACE_DIR",
                repo_root / "artifacts" / "workspace",
            )
        )
        capture_url_prefix = os.getenv("LEARN_TO_DRAW_CAPTURE_URL_PREFIX", "/captures")
        plotter_driver = os.getenv("LEARN_TO_DRAW_PLOTTER_DRIVER", "mock")
        axidraw_port = os.getenv("LEARN_TO_DRAW_AXIDRAW_PORT")
        axidraw_speed_pendown = _read_optional_int(
            "LEARN_TO_DRAW_AXIDRAW_SPEED_PENDOWN"
        )
        axidraw_speed_penup = _read_optional_int(
            "LEARN_TO_DRAW_AXIDRAW_SPEED_PENUP"
        )
        axidraw_model = _read_optional_int("LEARN_TO_DRAW_AXIDRAW_MODEL")
        axidraw_pen_pos_up = _read_optional_int("LEARN_TO_DRAW_AXIDRAW_PEN_POS_UP")
        axidraw_pen_pos_down = _read_optional_int("LEARN_TO_DRAW_AXIDRAW_PEN_POS_DOWN")
        axidraw_pen_rate_raise = _read_optional_int("LEARN_TO_DRAW_AXIDRAW_PEN_RATE_RAISE")
        axidraw_pen_rate_lower = _read_optional_int("LEARN_TO_DRAW_AXIDRAW_PEN_RATE_LOWER")
        axidraw_pen_delay_up = _read_optional_int("LEARN_TO_DRAW_AXIDRAW_PEN_DELAY_UP")
        axidraw_pen_delay_down = _read_optional_int("LEARN_TO_DRAW_AXIDRAW_PEN_DELAY_DOWN")
        axidraw_penlift = _read_optional_int("LEARN_TO_DRAW_AXIDRAW_PENLIFT")
        axidraw_config_path = _read_optional_path("LEARN_TO_DRAW_AXIDRAW_CONFIG_PATH")
        axidraw_native_res_factor = _read_optional_float_or_none(
            "LEARN_TO_DRAW_AXIDRAW_NATIVE_RES_FACTOR"
        )
        plotter_bounds_width_mm = _read_optional_float_or_none(
            "LEARN_TO_DRAW_PLOTTER_BOUNDS_WIDTH_MM"
        )
        plotter_bounds_height_mm = _read_optional_float_or_none(
            "LEARN_TO_DRAW_PLOTTER_BOUNDS_HEIGHT_MM"
        )
        plot_page_width_mm = _read_optional_float("LEARN_TO_DRAW_PLOT_PAGE_WIDTH_MM", 210.0)
        plot_page_height_mm = _read_optional_float("LEARN_TO_DRAW_PLOT_PAGE_HEIGHT_MM", 297.0)
        plot_margin_left_mm = _read_optional_float("LEARN_TO_DRAW_PLOT_MARGIN_LEFT_MM", 20.0)
        plot_margin_top_mm = _read_optional_float("LEARN_TO_DRAW_PLOT_MARGIN_TOP_MM", 20.0)
        plot_margin_right_mm = _read_optional_float("LEARN_TO_DRAW_PLOT_MARGIN_RIGHT_MM", 20.0)
        plot_margin_bottom_mm = _read_optional_float(
            "LEARN_TO_DRAW_PLOT_MARGIN_BOTTOM_MM",
            20.0,
        )
        plot_assets_url_prefix = os.getenv(
            "LEARN_TO_DRAW_PLOT_ASSETS_URL_PREFIX",
            "/plot-assets",
        )
        return cls(
            captures_dir=captures_dir,
            plot_assets_dir=plot_assets_dir,
            plot_runs_dir=plot_runs_dir,
            calibration_dir=calibration_dir,
            device_settings_dir=device_settings_dir,
            workspace_dir=workspace_dir,
            plotter_driver=plotter_driver,
            axidraw_port=axidraw_port,
            axidraw_speed_pendown=axidraw_speed_pendown,
            axidraw_speed_penup=axidraw_speed_penup,
            axidraw_model=axidraw_model,
            axidraw_pen_pos_up=axidraw_pen_pos_up,
            axidraw_pen_pos_down=axidraw_pen_pos_down,
            axidraw_pen_rate_raise=axidraw_pen_rate_raise,
            axidraw_pen_rate_lower=axidraw_pen_rate_lower,
            axidraw_pen_delay_up=axidraw_pen_delay_up,
            axidraw_pen_delay_down=axidraw_pen_delay_down,
            axidraw_penlift=axidraw_penlift,
            axidraw_config_path=axidraw_config_path,
            axidraw_native_res_factor=axidraw_native_res_factor,
            plotter_bounds_width_mm=plotter_bounds_width_mm,
            plotter_bounds_height_mm=plotter_bounds_height_mm,
            plot_page_width_mm=plot_page_width_mm,
            plot_page_height_mm=plot_page_height_mm,
            plot_margin_left_mm=plot_margin_left_mm,
            plot_margin_top_mm=plot_margin_top_mm,
            plot_margin_right_mm=plot_margin_right_mm,
            plot_margin_bottom_mm=plot_margin_bottom_mm,
            capture_url_prefix=capture_url_prefix,
            plot_assets_url_prefix=plot_assets_url_prefix,
        )

    def ensure_directories(self) -> None:
        self.captures_dir.mkdir(parents=True, exist_ok=True)
        self.plot_assets_dir.mkdir(parents=True, exist_ok=True)
        self.plot_runs_dir.mkdir(parents=True, exist_ok=True)
        self.calibration_dir.mkdir(parents=True, exist_ok=True)
        self.device_settings_dir.mkdir(parents=True, exist_ok=True)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    @property
    def normalized_capture_url_prefix(self) -> str:
        return self._normalize_url_prefix(self.capture_url_prefix, "/captures")

    @property
    def normalized_plot_assets_url_prefix(self) -> str:
        return self._normalize_url_prefix(
            self.plot_assets_url_prefix,
            "/plot-assets",
        )

    def _normalize_url_prefix(self, prefix: str, fallback: str) -> str:
        prefix = prefix.strip() or fallback
        if not prefix.startswith("/"):
            prefix = f"/{prefix}"
        return prefix.rstrip("/") or fallback


def _read_optional_int(env_name: str) -> Optional[int]:
    value = os.getenv(env_name)
    if value is None or value == "":
        return None
    return int(value)


def _read_optional_path(env_name: str) -> Optional[Path]:
    value = os.getenv(env_name)
    if value is None or value == "":
        return None
    return Path(value).expanduser()


def _read_optional_float(env_name: str, default: float) -> float:
    value = os.getenv(env_name)
    if value is None or value == "":
        return default
    return float(value)


def _read_optional_float_or_none(env_name: str) -> Optional[float]:
    value = os.getenv(env_name)
    if value is None or value == "":
        return None
    return float(value)
