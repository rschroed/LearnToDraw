from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
import re
from pathlib import Path
from tempfile import gettempdir
from typing import Any, Callable, Literal, Optional

from learn_to_draw_api.models import PlotterTestAction


class PyAxiDrawClientError(Exception):
    """Raised when the pyAxiDraw client cannot complete an operation."""


AxiDrawApiSurface = Literal["documented_pyaxidraw", "installed_axidrawinternal_compat"]
AxiDrawConfigSource = Literal["vendor_default", "generated_override", "explicit_path"]


@dataclass(frozen=True)
class AxiDrawProbeResult:
    firmware_version: Optional[str]
    port: Optional[str]
    api_surface: AxiDrawApiSurface
    plot_api_supported: bool
    manual_api_supported: bool
    config_source: AxiDrawConfigSource
    calibration_source: str
    native_res_factor: Optional[float]
    motion_scale: Optional[float]


@dataclass(frozen=True)
class AxiDrawActionResult:
    port: Optional[str]
    api_surface: AxiDrawApiSurface
    plot_api_supported: bool
    manual_api_supported: bool
    config_source: AxiDrawConfigSource
    calibration_source: str
    native_res_factor: Optional[float]
    motion_scale: Optional[float]


@dataclass(frozen=True)
class AxiDrawPlotExecution:
    port: Optional[str]
    api_surface: AxiDrawApiSurface
    plot_api_supported: bool
    manual_api_supported: bool
    config_source: AxiDrawConfigSource
    calibration_source: str
    native_res_factor: Optional[float]
    motion_scale: Optional[float]
    details: dict[str, Any]


class PyAxiDrawClient:
    def __init__(
        self,
        *,
        module_loader: Optional[Callable[[], Any]] = None,
        port: Optional[str] = None,
        speed_pendown: Optional[int] = None,
        speed_penup: Optional[int] = None,
        model: Optional[int] = None,
        pen_pos_up: Optional[int] = None,
        pen_pos_down: Optional[int] = None,
        pen_rate_raise: Optional[int] = None,
        pen_rate_lower: Optional[int] = None,
        pen_delay_up: Optional[int] = None,
        pen_delay_down: Optional[int] = None,
        penlift: Optional[int] = None,
        config_path: Optional[Path | str] = None,
        native_res_factor: Optional[float] = None,
        calibration_source: Optional[Literal["persisted", "env_override"]] = None,
        motion_scale: Optional[float] = None,
    ) -> None:
        self._module_loader = module_loader or _load_axidraw_module
        self._port = port
        self._speed_pendown = speed_pendown
        self._speed_penup = speed_penup
        self._model = model
        self._pen_pos_up = pen_pos_up
        self._pen_pos_down = pen_pos_down
        self._pen_rate_raise = pen_rate_raise
        self._pen_rate_lower = pen_rate_lower
        self._pen_delay_up = pen_delay_up
        self._pen_delay_down = pen_delay_down
        self._penlift = penlift
        self._config_path = Path(config_path).expanduser() if config_path is not None else None
        self._native_res_factor_override = native_res_factor
        self._explicit_calibration_source = calibration_source
        self._motion_scale = motion_scale
        self._config_source = self._resolve_config_source()
        self._effective_native_res_factor = self._resolve_native_res_factor()
        if self._motion_scale is None and self._effective_native_res_factor is not None:
            vendor_default = read_vendor_default_native_res_factor() or 1016.0
            self._motion_scale = round(self._effective_native_res_factor / vendor_default, 6)

    def config_details(self) -> dict[str, Any]:
        return {
            "config_source": self._config_source,
            "calibration_source": self._resolve_calibration_source(),
            "native_res_factor": self._effective_native_res_factor,
            "motion_scale": self._motion_scale,
        }

    def pen_tuning(self) -> dict[str, int]:
        tuning: dict[str, int] = {}
        for key, value in (
            ("pen_pos_up", self._pen_pos_up),
            ("pen_pos_down", self._pen_pos_down),
            ("pen_rate_raise", self._pen_rate_raise),
            ("pen_rate_lower", self._pen_rate_lower),
            ("pen_delay_up", self._pen_delay_up),
            ("pen_delay_down", self._pen_delay_down),
            ("penlift", self._penlift),
        ):
            if value is not None:
                tuning[key] = value
        return tuning

    def set_pen_heights(self, *, pen_pos_up: int, pen_pos_down: int) -> None:
        self._pen_pos_up = pen_pos_up
        self._pen_pos_down = pen_pos_down

    def apply_persisted_native_res_factor(
        self,
        *,
        native_res_factor: float,
        motion_scale: float,
    ) -> None:
        if self._config_path is not None or self._explicit_calibration_source == "env_override":
            return
        self._native_res_factor_override = native_res_factor
        self._motion_scale = motion_scale
        self._explicit_calibration_source = "persisted"
        self._config_source = self._resolve_config_source()
        self._effective_native_res_factor = self._resolve_native_res_factor()

    def probe_connection(self) -> AxiDrawProbeResult:
        ad = None
        try:
            ad, api_surface, plot_api_supported, manual_api_supported = self._new_axidraw()
            self._apply_common_options(ad)
            if api_surface == "documented_pyaxidraw":
                self._run_documented_manual(ad, "fw_version")
            else:
                self._run_compat_manual(ad, "fw_version")
            return AxiDrawProbeResult(
                firmware_version=self._read_firmware_version(ad),
                port=self._port,
                api_surface=api_surface,
                plot_api_supported=plot_api_supported,
                manual_api_supported=manual_api_supported,
                config_source=self._config_source,
                calibration_source=self._resolve_calibration_source(),
                native_res_factor=self._effective_native_res_factor,
                motion_scale=self._motion_scale,
            )
        except ImportError as exc:
            raise PyAxiDrawClientError(
                "pyAxiDraw is not installed. Install the official AxiDraw Python API first."
            ) from exc
        except Exception as exc:
            if isinstance(exc, PyAxiDrawClientError):
                raise
            raise PyAxiDrawClientError(str(exc)) from exc
        finally:
            _safe_disconnect(ad)

    def walk_home(self) -> AxiDrawActionResult:
        return self.run_manual_command("walk_home")

    def run_test_action(self, action: PlotterTestAction) -> AxiDrawActionResult:
        if action == "raise_pen":
            return self.run_manual_command("raise_pen")
        if action == "lower_pen":
            return self.run_manual_command("lower_pen")
        if action == "cycle_pen":
            return self.run_setup_mode("cycle")
        if action == "align":
            return self.run_setup_mode("align")
        raise PyAxiDrawClientError(f"Unsupported diagnostic action '{action}'.")

    def run_manual_command(self, manual_cmd: str) -> AxiDrawActionResult:
        if manual_cmd not in {"fw_version", "raise_pen", "lower_pen", "walk_home"}:
            raise PyAxiDrawClientError(f"Unsupported documented manual command '{manual_cmd}'.")

        ad = None
        try:
            ad, api_surface, plot_api_supported, manual_api_supported = self._new_axidraw()
            self._apply_common_options(ad)
            if api_surface == "documented_pyaxidraw":
                self._run_documented_manual(ad, manual_cmd)
            else:
                self._run_compat_manual(ad, manual_cmd)
            return AxiDrawActionResult(
                port=self._port,
                api_surface=api_surface,
                plot_api_supported=plot_api_supported,
                manual_api_supported=manual_api_supported,
                config_source=self._config_source,
                calibration_source=self._resolve_calibration_source(),
                native_res_factor=self._effective_native_res_factor,
                motion_scale=self._motion_scale,
            )
        except ImportError as exc:
            raise PyAxiDrawClientError(
                "pyAxiDraw is not installed. Install the official AxiDraw Python API first."
            ) from exc
        except Exception as exc:
            if isinstance(exc, PyAxiDrawClientError):
                raise
            raise PyAxiDrawClientError(str(exc)) from exc
        finally:
            _safe_disconnect(ad)

    def run_setup_mode(self, mode: str) -> AxiDrawActionResult:
        if mode not in {"align", "cycle"}:
            raise PyAxiDrawClientError(f"Unsupported documented setup mode '{mode}'.")

        ad = None
        try:
            ad, api_surface, plot_api_supported, manual_api_supported = self._new_axidraw()
            self._apply_common_options(ad)
            if api_surface == "documented_pyaxidraw":
                self._run_documented_setup(ad, mode)
            else:
                self._run_compat_setup(ad, mode)
            return AxiDrawActionResult(
                port=self._port,
                api_surface=api_surface,
                plot_api_supported=plot_api_supported,
                manual_api_supported=manual_api_supported,
                config_source=self._config_source,
                calibration_source=self._resolve_calibration_source(),
                native_res_factor=self._effective_native_res_factor,
                motion_scale=self._motion_scale,
            )
        except ImportError as exc:
            raise PyAxiDrawClientError(
                "pyAxiDraw is not installed. Install the official AxiDraw Python API first."
            ) from exc
        except Exception as exc:
            if isinstance(exc, PyAxiDrawClientError):
                raise
            raise PyAxiDrawClientError(str(exc)) from exc
        finally:
            _safe_disconnect(ad)

    def run_plot_document(self, svg_text: str) -> AxiDrawPlotExecution:
        ad = None
        try:
            ad, api_surface, plot_api_supported, manual_api_supported = self._new_axidraw()
            if not plot_api_supported:
                raise PyAxiDrawClientError(
                    "Trusted plotting requires the official pyaxidraw Plot API "
                    "(plot_setup() and plot_run()). Install the unpacked official "
                    "AxiDraw API package with 'pip install .' and retry."
                )
            self._apply_common_options(ad)
            self._run_documented_plot(ad, svg_text)
            return AxiDrawPlotExecution(
                port=self._port,
                api_surface=api_surface,
                plot_api_supported=plot_api_supported,
                manual_api_supported=manual_api_supported,
                config_source=self._config_source,
                calibration_source=self._resolve_calibration_source(),
                native_res_factor=self._effective_native_res_factor,
                motion_scale=self._motion_scale,
                details={"result": "plot_run"},
            )
        except ImportError as exc:
            raise PyAxiDrawClientError(
                "pyAxiDraw is not installed. Install the official AxiDraw Python API first."
            ) from exc
        except Exception as exc:
            if isinstance(exc, PyAxiDrawClientError):
                raise
            raise PyAxiDrawClientError(str(exc)) from exc
        finally:
            _safe_disconnect(ad)

    def _new_axidraw(self) -> tuple[Any, AxiDrawApiSurface, bool, bool]:
        module = self._module_loader()
        ad = module.AxiDraw()
        api_surface: AxiDrawApiSurface
        if hasattr(ad, "plot_setup") and hasattr(ad, "plot_run"):
            api_surface = "documented_pyaxidraw"
            plot_api_supported = True
            manual_api_supported = True
            self._apply_config(ad)
        else:
            api_surface = "installed_axidrawinternal_compat"
            plot_api_supported = False
            manual_api_supported = all(
                hasattr(ad, attribute)
                for attribute in ("serial_connect", "manual_command", "setup_command")
            )
        return ad, api_surface, plot_api_supported, manual_api_supported

    def _apply_config(self, ad: Any) -> None:
        if self._config_source == "vendor_default":
            return
        if not hasattr(ad, "load_config"):
            raise PyAxiDrawClientError(
                "Installed AxiDraw API does not expose load_config() for custom config support."
            )
        config_path = self._resolve_config_path()
        ad.load_config(str(config_path))

    def _run_documented_plot(self, ad: Any, svg_text: str) -> None:
        # Official Plot context: plot_setup(svg_input) -> set options -> plot_run().
        ad.plot_setup(svg_text)
        ad.options.mode = "plot"
        if hasattr(ad.options, "auto_rotate"):
            ad.options.auto_rotate = False
        result = ad.plot_run(output=False)
        if result is False:
            raise PyAxiDrawClientError("AxiDraw plot_run() reported failure.")

    def _run_documented_manual(self, ad: Any, manual_cmd: str) -> None:
        # Official Plot context: plot_setup() -> options.mode/manual_cmd -> plot_run().
        ad.plot_setup()
        ad.options.mode = "manual"
        ad.options.manual_cmd = manual_cmd
        result = ad.plot_run(output=False)
        if result is False:
            raise PyAxiDrawClientError(f"AxiDraw manual command '{manual_cmd}' failed.")

    def _run_documented_setup(self, ad: Any, mode: str) -> None:
        # Official Plot context: plot_setup() -> options.mode -> plot_run().
        ad.plot_setup()
        ad.options.mode = mode
        result = ad.plot_run(output=False)
        if result is False:
            raise PyAxiDrawClientError(f"AxiDraw setup mode '{mode}' failed.")

    def _run_compat_manual(self, ad: Any, manual_cmd: str) -> None:
        self._compat_connect(ad)
        ad.options.mode = "manual"
        ad.options.manual_cmd = manual_cmd
        ad.manual_command()

    def _run_compat_setup(self, ad: Any, mode: str) -> None:
        self._compat_connect(ad)
        ad.options.mode = mode
        ad.setup_command()

    def _compat_connect(self, ad: Any) -> None:
        if not hasattr(ad, "serial_connect"):
            raise PyAxiDrawClientError("Installed AxiDraw API does not expose serial_connect().")
        ad.serial_connect()
        if not getattr(ad, "connected", False):
            raise PyAxiDrawClientError("Could not connect to AxiDraw.")

    def _apply_common_options(self, ad: Any) -> None:
        if self._port:
            ad.options.port = self._port
        if self._speed_pendown is not None:
            ad.options.speed_pendown = self._speed_pendown
        if self._speed_penup is not None:
            ad.options.speed_penup = self._speed_penup
        if self._model is not None:
            ad.options.model = self._model
        if self._pen_pos_up is not None:
            ad.options.pen_pos_up = self._pen_pos_up
        if self._pen_pos_down is not None:
            ad.options.pen_pos_down = self._pen_pos_down
        if self._pen_rate_raise is not None:
            ad.options.pen_rate_raise = self._pen_rate_raise
        if self._pen_rate_lower is not None:
            ad.options.pen_rate_lower = self._pen_rate_lower
        if self._pen_delay_up is not None:
            ad.options.pen_delay_up = self._pen_delay_up
        if self._pen_delay_down is not None:
            ad.options.pen_delay_down = self._pen_delay_down
        if self._penlift is not None:
            ad.options.penlift = self._penlift

    def _read_firmware_version(self, ad: Any) -> Optional[str]:
        firmware_version = getattr(ad, "fw_version_string", None)
        if firmware_version is None:
            firmware_version = getattr(getattr(ad, "plot_status", None), "fw_version", None)
        return firmware_version

    def _resolve_config_source(self) -> AxiDrawConfigSource:
        if self._config_path is not None:
            return "explicit_path"
        if self._native_res_factor_override is not None:
            return "generated_override"
        return "vendor_default"

    def _resolve_calibration_source(self) -> str:
        if self._config_path is not None:
            return "explicit_path"
        if self._explicit_calibration_source is not None:
            return self._explicit_calibration_source
        if self._native_res_factor_override is not None:
            return "persisted"
        return "vendor_default"

    def _resolve_native_res_factor(self) -> Optional[float]:
        if self._config_path is not None:
            return _read_native_res_factor_from_config(self._config_path)
        if self._native_res_factor_override is not None:
            return self._native_res_factor_override
        return _read_vendor_default_native_res_factor()

    def _resolve_config_path(self) -> Path:
        if self._config_source == "explicit_path":
            assert self._config_path is not None
            if not self._config_path.exists():
                raise PyAxiDrawClientError(
                    f"AxiDraw config file '{self._config_path}' does not exist."
                )
            return self._config_path
        if self._config_source == "generated_override":
            assert self._native_res_factor_override is not None
            return _ensure_generated_override_config(self._native_res_factor_override)
        raise PyAxiDrawClientError("Vendor default config does not require a config path.")


def _load_axidraw_module() -> Any:
    try:
        from pyaxidraw import axidraw

        return axidraw
    except ImportError:
        from axidrawinternal import axidraw

        return axidraw


def _read_vendor_default_native_res_factor() -> Optional[float]:
    try:
        module = import_module("axidrawinternal.axidraw_conf")
    except Exception:
        return None
    value = getattr(module, "native_res_factor", None)
    return float(value) if isinstance(value, (int, float)) else None


def read_vendor_default_native_res_factor() -> Optional[float]:
    return _read_vendor_default_native_res_factor()


def _read_vendor_default_config_path() -> Optional[Path]:
    try:
        module = import_module("axidrawinternal.axidraw_conf")
    except Exception:
        return None
    module_file = getattr(module, "__file__", None)
    if not module_file:
        return None
    return Path(module_file)


def _read_native_res_factor_from_config(path: Path) -> Optional[float]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(
        r"^native_res_factor\s*=\s*([0-9]+(?:\.[0-9]+)?)",
        text,
        re.MULTILINE,
    )
    if match is None:
        return None
    return float(match.group(1))


def _ensure_generated_override_config(native_res_factor: float) -> Path:
    vendor_config_path = _read_vendor_default_config_path()
    if vendor_config_path is None or not vendor_config_path.exists():
        raise PyAxiDrawClientError(
            "Could not locate the vendor AxiDraw config to build an override file."
        )
    target = Path(gettempdir()) / (
        f"learn_to_draw_axidraw_conf_native_res_"
        f"{str(native_res_factor).replace('.', '_')}.py"
    )
    vendor_text = vendor_config_path.read_text(encoding="utf-8")
    updated_text, replacements = re.subn(
        r"^native_res_factor\s*=\s*[0-9]+(?:\.[0-9]+)?",
        f"native_res_factor = {native_res_factor}",
        vendor_text,
        count=1,
        flags=re.MULTILINE,
    )
    if replacements == 0:
        updated_text = (
            vendor_text.rstrip()
            + f"\n\nnative_res_factor = {native_res_factor}\n"
        )
    target.write_text(updated_text, encoding="utf-8")
    return target


def _safe_disconnect(ad: Any) -> None:
    try:
        ad.disconnect()
    except Exception:
        pass
