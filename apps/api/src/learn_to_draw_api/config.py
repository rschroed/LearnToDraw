from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class AppConfig:
    captures_dir: Path
    plot_assets_dir: Path
    plot_runs_dir: Path
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
        plot_assets_url_prefix = os.getenv(
            "LEARN_TO_DRAW_PLOT_ASSETS_URL_PREFIX",
            "/plot-assets",
        )
        return cls(
            captures_dir=captures_dir,
            plot_assets_dir=plot_assets_dir,
            plot_runs_dir=plot_runs_dir,
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
            capture_url_prefix=capture_url_prefix,
            plot_assets_url_prefix=plot_assets_url_prefix,
        )

    def ensure_directories(self) -> None:
        self.captures_dir.mkdir(parents=True, exist_ok=True)
        self.plot_assets_dir.mkdir(parents=True, exist_ok=True)
        self.plot_runs_dir.mkdir(parents=True, exist_ok=True)

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
