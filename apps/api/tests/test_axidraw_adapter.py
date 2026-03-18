from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from learn_to_draw_api.adapters.axidraw_client import PyAxiDrawClient, PyAxiDrawClientError
from learn_to_draw_api.adapters.axidraw_plotter import AxiDrawPlotter
from learn_to_draw_api.adapters.factory import build_plotter_adapter
from learn_to_draw_api.config import AppConfig
from learn_to_draw_api.models import (
    HardwareOperationError,
    HardwareUnavailableError,
    PlotDocument,
)


class FakeDocumentedAxiDraw:
    def __init__(self) -> None:
        self.options = SimpleNamespace(
            port=None,
            speed_pendown=None,
            speed_penup=None,
            model=None,
            mode=None,
            manual_cmd=None,
            pen_pos_up=None,
            pen_pos_down=None,
            pen_rate_raise=None,
            pen_rate_lower=None,
            pen_delay_up=None,
            pen_delay_down=None,
            penlift=None,
            auto_rotate=None,
            resolution=None,
        )
        self.fw_version_string = "FW-1.2.3"
        self.plot_setup_inputs: list[str | None] = []
        self.plot_run_calls: list[tuple[str | None, str | None]] = []
        self.load_config_calls: list[str] = []
        self.plot_run_result = True
        self.disconnect_called = False

    def disconnect(self) -> None:
        self.disconnect_called = True

    def plot_setup(self, svg_text: str | None = None) -> None:
        self.plot_setup_inputs.append(svg_text)

    def plot_run(self, output: bool = False):
        self.plot_run_calls.append((self.options.mode, self.options.manual_cmd))
        return self.plot_run_result

    def load_config(self, config_ref: str) -> None:
        self.load_config_calls.append(config_ref)


class FakeCompatAxiDraw:
    def __init__(self) -> None:
        self.options = SimpleNamespace(
            port=None,
            speed_pendown=None,
            speed_penup=None,
            model=None,
            mode=None,
            manual_cmd=None,
            pen_pos_up=None,
            pen_pos_down=None,
            pen_rate_raise=None,
            pen_rate_lower=None,
            pen_delay_up=None,
            pen_delay_down=None,
            penlift=None,
            auto_rotate=None,
            resolution=None,
        )
        self.connected = False
        self.plot_status = SimpleNamespace(fw_version="FW-9.9.9")
        self.serial_connect_called = 0
        self.manual_commands: list[str] = []
        self.setup_modes: list[str] = []
        self.affect_inputs: list[list[str]] = []
        self.disconnect_called = False

    def serial_connect(self) -> None:
        self.connected = True
        self.serial_connect_called += 1

    def manual_command(self) -> None:
        self.manual_commands.append(self.options.manual_cmd)

    def setup_command(self) -> None:
        self.setup_modes.append(self.options.mode)

    def affect(self, args: list[str]) -> None:
        self.affect_inputs.append(args)

    def disconnect(self) -> None:
        self.disconnect_called = True


def module_loader_with(instances: list[object]):
    def loader():
        return SimpleNamespace(AxiDraw=lambda: instances.pop(0))

    return loader


def test_pyaxidraw_client_uses_documented_plot_context_and_pen_options():
    probe_instance = FakeDocumentedAxiDraw()
    origin_instance = FakeDocumentedAxiDraw()
    action_instance = FakeDocumentedAxiDraw()
    plot_instance = FakeDocumentedAxiDraw()
    client = PyAxiDrawClient(
        module_loader=module_loader_with(
            [probe_instance, origin_instance, action_instance, plot_instance]
        ),
        port="usb-123",
        speed_pendown=40,
        speed_penup=70,
        model=3,
        pen_pos_up=65,
        pen_pos_down=28,
        pen_rate_raise=80,
        pen_rate_lower=55,
        pen_delay_up=20,
        pen_delay_down=10,
        penlift=1,
    )

    probe = client.probe_connection()
    origin = client.walk_home()
    action = client.run_test_action("raise_pen")
    execution = client.run_plot_document("<svg xmlns='http://www.w3.org/2000/svg' />")

    assert probe.api_surface == "documented_pyaxidraw"
    assert probe.plot_api_supported is True
    assert probe.manual_api_supported is True
    assert probe.firmware_version == "FW-1.2.3"
    assert origin.api_surface == "documented_pyaxidraw"
    assert action.api_surface == "documented_pyaxidraw"
    assert execution.plot_api_supported is True
    assert execution.config_source == "vendor_default"
    assert execution.calibration_source == "vendor_default"
    assert execution.native_res_factor == 1016.0
    assert execution.motion_scale == 1.0
    assert origin_instance.plot_run_calls == [("manual", "walk_home")]
    assert action_instance.plot_run_calls == [("manual", "raise_pen")]
    assert plot_instance.plot_setup_inputs == ["<svg xmlns='http://www.w3.org/2000/svg' />"]
    assert plot_instance.plot_run_calls == [("plot", None)]
    assert plot_instance.options.pen_pos_up == 65
    assert plot_instance.options.pen_pos_down == 28
    assert plot_instance.options.pen_rate_raise == 80
    assert plot_instance.options.pen_rate_lower == 55
    assert plot_instance.options.pen_delay_up == 20
    assert plot_instance.options.pen_delay_down == 10
    assert plot_instance.options.penlift == 1
    assert plot_instance.options.auto_rotate is False
    assert execution.api_surface == "documented_pyaxidraw"


def test_pyaxidraw_client_uses_generated_native_res_override(tmp_path):
    plot_instance = FakeDocumentedAxiDraw()
    client = PyAxiDrawClient(
        module_loader=module_loader_with([plot_instance]),
        native_res_factor=1905.0,
    )

    execution = client.run_plot_document("<svg xmlns='http://www.w3.org/2000/svg' />")

    assert execution.config_source == "generated_override"
    assert execution.calibration_source == "persisted"
    assert execution.native_res_factor == 1905.0
    assert execution.motion_scale == 1.875
    assert len(plot_instance.load_config_calls) == 1
    generated_path = Path(plot_instance.load_config_calls[0])
    assert generated_path.exists()
    assert "native_res_factor = 1905.0" in generated_path.read_text()


def test_pyaxidraw_client_prefers_explicit_config_path(tmp_path):
    config_path = tmp_path / "axidraw_conf_custom.py"
    config_path.write_text("native_res_factor = 1800.0\n", encoding="utf-8")
    plot_instance = FakeDocumentedAxiDraw()
    client = PyAxiDrawClient(
        module_loader=module_loader_with([plot_instance]),
        config_path=config_path,
        native_res_factor=1905.0,
    )

    execution = client.run_plot_document("<svg xmlns='http://www.w3.org/2000/svg' />")

    assert execution.config_source == "explicit_path"
    assert execution.calibration_source == "explicit_path"
    assert execution.native_res_factor == 1800.0
    assert plot_instance.load_config_calls == [str(config_path)]


def test_pyaxidraw_client_uses_minimal_compat_path_for_manual_diagnostics_only():
    probe_instance = FakeCompatAxiDraw()
    cycle_instance = FakeCompatAxiDraw()
    client = PyAxiDrawClient(
        module_loader=module_loader_with([probe_instance, cycle_instance, FakeCompatAxiDraw()]),
        port="usb-compat",
        pen_pos_up=60,
        pen_pos_down=30,
    )

    probe = client.probe_connection()
    cycle = client.run_test_action("cycle_pen")

    assert probe.api_surface == "installed_axidrawinternal_compat"
    assert probe.plot_api_supported is False
    assert probe.manual_api_supported is True
    assert probe.config_source == "vendor_default"
    assert probe.calibration_source == "vendor_default"
    assert probe.firmware_version == "FW-9.9.9"
    assert probe_instance.manual_commands == ["fw_version"]
    assert cycle.api_surface == "installed_axidrawinternal_compat"
    assert cycle_instance.setup_modes == ["cycle"]
    assert cycle.plot_api_supported is False

    with pytest.raises(PyAxiDrawClientError, match="official pyaxidraw Plot API"):
        client.run_plot_document("<svg xmlns='http://www.w3.org/2000/svg' />")


def test_pyaxidraw_client_rejects_unsupported_manual_command():
    client = PyAxiDrawClient(module_loader=module_loader_with([FakeCompatAxiDraw()]))

    with pytest.raises(PyAxiDrawClientError):
        client.run_manual_command("toggle_pen")


def test_pyaxidraw_client_raises_when_module_missing():
    client = PyAxiDrawClient(module_loader=lambda: (_ for _ in ()).throw(ImportError()))

    with pytest.raises(PyAxiDrawClientError):
        client.probe_connection()


class FakeClient:
    def __init__(
        self,
        *,
        fail_probe: bool = False,
        fail_origin: bool = False,
        fail_plot: bool = False,
        fail_test_action: bool = False,
        plot_api_supported: bool = False,
        manual_api_supported: bool = True,
    ):
        self.fail_probe = fail_probe
        self.fail_origin = fail_origin
        self.fail_plot = fail_plot
        self.fail_test_action = fail_test_action
        self.plot_api_supported = plot_api_supported
        self.manual_api_supported = manual_api_supported
        self._pen_tuning = {"pen_pos_up": 60, "pen_pos_down": 30}
        self.persisted_calibration: tuple[float, float] | None = None

    def pen_tuning(self):
        return dict(self._pen_tuning)

    def config_details(self):
        return {
            "config_source": "vendor_default",
            "calibration_source": "vendor_default",
            "native_res_factor": 1016.0,
            "motion_scale": 1.0,
        }

    def set_pen_heights(self, *, pen_pos_up: int, pen_pos_down: int):
        self._pen_tuning = {"pen_pos_up": pen_pos_up, "pen_pos_down": pen_pos_down}

    def apply_persisted_native_res_factor(self, *, native_res_factor: float, motion_scale: float):
        self.persisted_calibration = (native_res_factor, motion_scale)

    def probe_connection(self):
        if self.fail_probe:
            raise PyAxiDrawClientError("probe failed")
        return SimpleNamespace(
            firmware_version="FW-9.9.9",
            port="usb-a",
            api_surface="installed_axidrawinternal_compat",
            plot_api_supported=self.plot_api_supported,
            manual_api_supported=self.manual_api_supported,
            config_source="vendor_default",
            calibration_source="vendor_default",
            native_res_factor=1016.0,
            motion_scale=1.0,
        )

    def walk_home(self):
        if self.fail_origin:
            raise PyAxiDrawClientError("origin failed")
        return SimpleNamespace(
            port="usb-a",
            api_surface="installed_axidrawinternal_compat",
            plot_api_supported=self.plot_api_supported,
            manual_api_supported=self.manual_api_supported,
            config_source="vendor_default",
            calibration_source="vendor_default",
            native_res_factor=1016.0,
            motion_scale=1.0,
        )

    def run_test_action(self, action: str):
        if self.fail_test_action:
            raise PyAxiDrawClientError("test action failed")
        return SimpleNamespace(
            port="usb-a",
            api_surface="installed_axidrawinternal_compat",
            plot_api_supported=self.plot_api_supported,
            manual_api_supported=self.manual_api_supported,
            config_source="vendor_default",
            calibration_source="vendor_default",
            native_res_factor=1016.0,
            motion_scale=1.0,
        )

    def run_plot_document(self, svg_text: str):
        if self.fail_plot:
            raise PyAxiDrawClientError("plot failed")
        if not self.plot_api_supported:
            raise PyAxiDrawClientError(
                "Trusted plotting requires the official pyaxidraw Plot API "
                "(plot_setup() and plot_run()). Install the unpacked official "
                "AxiDraw API package with 'pip install .' and retry."
            )
        return SimpleNamespace(
            port="usb-a",
            api_surface="installed_axidrawinternal_compat",
            plot_api_supported=self.plot_api_supported,
            manual_api_supported=self.manual_api_supported,
            config_source="vendor_default",
            calibration_source="vendor_default",
            native_res_factor=1016.0,
            motion_scale=1.0,
            details={"svg_text_length": len(svg_text)},
        )


def test_axidraw_plotter_reports_status_and_maps_operations():
    plotter = AxiDrawPlotter(
        client=FakeClient(plot_api_supported=True, manual_api_supported=True),
        port="usb-a",
    )
    plotter.connect()

    status = plotter.get_status()
    plotter.set_pen_heights(pen_pos_up=62, pen_pos_down=24)
    origin_result = plotter.walk_home()
    plotter.run_test_action("align")
    plot_result = plotter.plot(
        PlotDocument(
            asset_id="asset-1",
            name="Test asset",
            svg_text="<svg xmlns='http://www.w3.org/2000/svg' width='100' height='100' />",
            width=100,
            height=100,
            prepared_width_mm=100.0,
            prepared_height_mm=100.0,
        )
    )

    assert status.connected is True
    assert status.details["firmware_version"] == "FW-9.9.9"
    assert status.details["api_surface"] == "installed_axidrawinternal_compat"
    assert status.details["plot_api_supported"] is True
    assert status.details["manual_api_supported"] is True
    assert status.details["config_source"] == "vendor_default"
    assert status.details["calibration_source"] == "vendor_default"
    assert status.details["native_res_factor"] == 1016.0
    assert status.details["motion_scale"] == 1.0
    assert status.details["pen_tuning"] == {"pen_pos_up": 60, "pen_pos_down": 30}
    assert origin_result is None
    assert plot_result.document_id == "asset-1"
    assert plot_result.details["port"] == "usb-a"
    assert plotter.get_status().details["pen_tuning"] == {"pen_pos_up": 62, "pen_pos_down": 24}


def test_axidraw_plotter_applies_persisted_calibration_to_client():
    client = FakeClient(plot_api_supported=True, manual_api_supported=True)
    plotter = AxiDrawPlotter(client=client, port="usb-a")

    plotter.apply_persisted_calibration(native_res_factor=1905.0, motion_scale=1.875)

    assert client.persisted_calibration == (1905.0, 1.875)


def test_axidraw_plotter_maps_probe_and_plot_errors():
    with pytest.raises(HardwareUnavailableError):
        AxiDrawPlotter(client=FakeClient(fail_probe=True)).connect()

    plotter = AxiDrawPlotter(client=FakeClient(fail_plot=True, plot_api_supported=True))
    plotter.connect()

    with pytest.raises(HardwareOperationError):
        plotter.plot(
            PlotDocument(
                asset_id="asset-1",
                name="Broken asset",
                svg_text="<svg xmlns='http://www.w3.org/2000/svg' />",
                width=10,
                height=10,
                prepared_width_mm=10.0,
                prepared_height_mm=10.0,
            )
        )


def test_axidraw_plotter_refuses_plotting_without_documented_plot_support():
    plotter = AxiDrawPlotter(
        client=FakeClient(plot_api_supported=False, manual_api_supported=True)
    )
    plotter.connect()

    with pytest.raises(HardwareOperationError, match="official pyaxidraw Plot API"):
        plotter.plot(
            PlotDocument(
                asset_id="asset-1",
                name="Compat-only asset",
                svg_text="<svg xmlns='http://www.w3.org/2000/svg' />",
                width=10,
                height=10,
                prepared_width_mm=10.0,
                prepared_height_mm=10.0,
            )
        )


def test_axidraw_plotter_maps_test_action_errors():
    plotter = AxiDrawPlotter(client=FakeClient(fail_test_action=True))
    plotter.connect()

    with pytest.raises(HardwareOperationError):
        plotter.run_test_action("cycle_pen")


def test_build_plotter_adapter_uses_configured_driver(tmp_path):
    mock_config = AppConfig(
        captures_dir=tmp_path / "captures",
        plot_assets_dir=tmp_path / "plot_assets",
        plot_runs_dir=tmp_path / "plot_runs",
    )
    axidraw_config = AppConfig(
        captures_dir=tmp_path / "captures2",
        plot_assets_dir=tmp_path / "plot_assets2",
        plot_runs_dir=tmp_path / "plot_runs2",
        plotter_driver="axidraw",
        axidraw_port="usb-real",
        axidraw_model=1,
    )

    mock_plotter = build_plotter_adapter(mock_config)
    axidraw_plotter = build_plotter_adapter(axidraw_config)

    assert mock_plotter.driver == "mock-plotter"
    assert axidraw_plotter.driver == "axidraw-pyapi"


def test_build_plotter_adapter_degrades_when_axidraw_bounds_are_unconfigured(tmp_path):
    axidraw_config = AppConfig(
        captures_dir=tmp_path / "captures",
        plot_assets_dir=tmp_path / "plot_assets",
        plot_runs_dir=tmp_path / "plot_runs",
        plotter_driver="axidraw",
    )

    plotter = build_plotter_adapter(axidraw_config)
    status = plotter.get_status()

    assert plotter.driver == "axidraw-pyapi"
    assert status.available is False
    assert "requires explicit machine bounds configuration" in status.error
