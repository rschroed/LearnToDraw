from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Literal, Optional

from learn_to_draw_api.models import PlotterTestAction


class PyAxiDrawClientError(Exception):
    """Raised when the pyAxiDraw client cannot complete an operation."""


AxiDrawApiSurface = Literal["documented_pyaxidraw", "installed_axidrawinternal_compat"]


@dataclass(frozen=True)
class AxiDrawProbeResult:
    firmware_version: Optional[str]
    port: Optional[str]
    api_surface: AxiDrawApiSurface


@dataclass(frozen=True)
class AxiDrawActionResult:
    port: Optional[str]
    api_surface: AxiDrawApiSurface


@dataclass(frozen=True)
class AxiDrawPlotExecution:
    port: Optional[str]
    api_surface: AxiDrawApiSurface
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

    def probe_connection(self) -> AxiDrawProbeResult:
        ad = None
        try:
            ad, api_surface = self._new_axidraw()
            self._apply_common_options(ad)
            if api_surface == "documented_pyaxidraw":
                self._run_documented_manual(ad, "fw_version")
            else:
                self._run_compat_manual(ad, "fw_version")
            return AxiDrawProbeResult(
                firmware_version=self._read_firmware_version(ad),
                port=self._port,
                api_surface=api_surface,
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

    def return_to_origin(self) -> AxiDrawActionResult:
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
            ad, api_surface = self._new_axidraw()
            self._apply_common_options(ad)
            if api_surface == "documented_pyaxidraw":
                self._run_documented_manual(ad, manual_cmd)
            else:
                self._run_compat_manual(ad, manual_cmd)
            return AxiDrawActionResult(port=self._port, api_surface=api_surface)
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
            ad, api_surface = self._new_axidraw()
            self._apply_common_options(ad)
            if api_surface == "documented_pyaxidraw":
                self._run_documented_setup(ad, mode)
            else:
                self._run_compat_setup(ad, mode)
            return AxiDrawActionResult(port=self._port, api_surface=api_surface)
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
            ad, api_surface = self._new_axidraw()
            self._apply_common_options(ad)
            if api_surface == "documented_pyaxidraw":
                self._run_documented_plot(ad, svg_text)
                result = "plot_run"
            else:
                result = self._run_compat_plot(ad, svg_text)
            return AxiDrawPlotExecution(
                port=self._port,
                api_surface=api_surface,
                details={"result": result},
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

    def _new_axidraw(self) -> tuple[Any, AxiDrawApiSurface]:
        module = self._module_loader()
        ad = module.AxiDraw()
        api_surface: AxiDrawApiSurface
        if hasattr(ad, "plot_setup") and hasattr(ad, "plot_run"):
            api_surface = "documented_pyaxidraw"
        else:
            api_surface = "installed_axidrawinternal_compat"
        return ad, api_surface

    def _run_documented_plot(self, ad: Any, svg_text: str) -> None:
        # Official Plot context: plot_setup(svg_input) -> set options -> plot_run().
        ad.plot_setup(svg_text)
        ad.options.mode = "plot"
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

    def _run_compat_plot(self, ad: Any, svg_text: str) -> str:
        with NamedTemporaryFile("w", suffix=".svg", delete=False, encoding="utf-8") as handle:
            handle.write(svg_text)
            temp_path = Path(handle.name)
        try:
            ad.options.mode = "plot"
            ad.affect([str(temp_path)])
            return "affect"
        finally:
            temp_path.unlink(missing_ok=True)

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


def _load_axidraw_module() -> Any:
    try:
        from pyaxidraw import axidraw

        return axidraw
    except ImportError:
        from axidrawinternal import axidraw

        return axidraw


def _safe_disconnect(ad: Any) -> None:
    try:
        ad.disconnect()
    except Exception:
        pass
