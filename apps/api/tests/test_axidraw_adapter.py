from __future__ import annotations

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
        )
        self.fw_version_string = "FW-1.2.3"
        self.plot_setup_inputs: list[str | None] = []
        self.plot_run_calls: list[tuple[str | None, str | None]] = []
        self.plot_run_result = True
        self.disconnect_called = False

    def disconnect(self) -> None:
        self.disconnect_called = True

    def plot_setup(self, svg_text: str | None = None) -> None:
        self.plot_setup_inputs.append(svg_text)

    def plot_run(self, output: bool = False):
        self.plot_run_calls.append((self.options.mode, self.options.manual_cmd))
        return self.plot_run_result


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
    origin = client.return_to_origin()
    action = client.run_test_action("raise_pen")
    execution = client.run_plot_document("<svg xmlns='http://www.w3.org/2000/svg' />")

    assert probe.api_surface == "documented_pyaxidraw"
    assert probe.firmware_version == "FW-1.2.3"
    assert origin.api_surface == "documented_pyaxidraw"
    assert action.api_surface == "documented_pyaxidraw"
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
    assert execution.api_surface == "documented_pyaxidraw"


def test_pyaxidraw_client_uses_minimal_compat_path_for_documented_plot_modes():
    probe_instance = FakeCompatAxiDraw()
    cycle_instance = FakeCompatAxiDraw()
    plot_instance = FakeCompatAxiDraw()
    client = PyAxiDrawClient(
        module_loader=module_loader_with([probe_instance, cycle_instance, plot_instance]),
        port="usb-compat",
        pen_pos_up=60,
        pen_pos_down=30,
    )

    probe = client.probe_connection()
    cycle = client.run_test_action("cycle_pen")
    execution = client.run_plot_document("<svg xmlns='http://www.w3.org/2000/svg' />")

    assert probe.api_surface == "installed_axidrawinternal_compat"
    assert probe.firmware_version == "FW-9.9.9"
    assert probe_instance.manual_commands == ["fw_version"]
    assert cycle.api_surface == "installed_axidrawinternal_compat"
    assert cycle_instance.setup_modes == ["cycle"]
    assert plot_instance.affect_inputs
    assert plot_instance.options.mode == "plot"
    assert plot_instance.options.pen_pos_up == 60
    assert plot_instance.options.pen_pos_down == 30
    assert execution.api_surface == "installed_axidrawinternal_compat"
    assert execution.details["result"] == "affect"


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
    ):
        self.fail_probe = fail_probe
        self.fail_origin = fail_origin
        self.fail_plot = fail_plot
        self.fail_test_action = fail_test_action
        self._pen_tuning = {"pen_pos_up": 60, "pen_pos_down": 30}

    def pen_tuning(self):
        return dict(self._pen_tuning)

    def set_pen_heights(self, *, pen_pos_up: int, pen_pos_down: int):
        self._pen_tuning = {"pen_pos_up": pen_pos_up, "pen_pos_down": pen_pos_down}

    def probe_connection(self):
        if self.fail_probe:
            raise PyAxiDrawClientError("probe failed")
        return SimpleNamespace(
            firmware_version="FW-9.9.9",
            port="usb-a",
            api_surface="installed_axidrawinternal_compat",
        )

    def return_to_origin(self):
        if self.fail_origin:
            raise PyAxiDrawClientError("origin failed")
        return SimpleNamespace(port="usb-a", api_surface="installed_axidrawinternal_compat")

    def run_test_action(self, action: str):
        if self.fail_test_action:
            raise PyAxiDrawClientError("test action failed")
        return SimpleNamespace(port="usb-a", api_surface="installed_axidrawinternal_compat")

    def run_plot_document(self, svg_text: str):
        if self.fail_plot:
            raise PyAxiDrawClientError("plot failed")
        return SimpleNamespace(
            port="usb-a",
            api_surface="installed_axidrawinternal_compat",
            details={"svg_text_length": len(svg_text)},
        )


def test_axidraw_plotter_reports_status_and_maps_operations():
    plotter = AxiDrawPlotter(client=FakeClient(), port="usb-a")
    plotter.connect()

    status = plotter.get_status()
    plotter.set_pen_heights(pen_pos_up=62, pen_pos_down=24)
    origin_result = plotter.return_to_origin()
    plotter.run_test_action("align")
    plot_result = plotter.plot(
        PlotDocument(
            asset_id="asset-1",
            name="Test asset",
            svg_text="<svg xmlns='http://www.w3.org/2000/svg' width='100' height='100' />",
            width=100,
            height=100,
        )
    )

    assert status.connected is True
    assert status.details["firmware_version"] == "FW-9.9.9"
    assert status.details["api_surface"] == "installed_axidrawinternal_compat"
    assert status.details["pen_tuning"] == {"pen_pos_up": 60, "pen_pos_down": 30}
    assert origin_result is None
    assert plot_result.document_id == "asset-1"
    assert plot_result.details["port"] == "usb-a"
    assert plotter.get_status().details["pen_tuning"] == {"pen_pos_up": 62, "pen_pos_down": 24}


def test_axidraw_plotter_maps_probe_and_plot_errors():
    with pytest.raises(HardwareUnavailableError):
        AxiDrawPlotter(client=FakeClient(fail_probe=True)).connect()

    plotter = AxiDrawPlotter(client=FakeClient(fail_plot=True))
    plotter.connect()

    with pytest.raises(HardwareOperationError):
        plotter.plot(
            PlotDocument(
                asset_id="asset-1",
                name="Broken asset",
                svg_text="<svg xmlns='http://www.w3.org/2000/svg' />",
                width=10,
                height=10,
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
    )

    mock_plotter = build_plotter_adapter(mock_config)
    axidraw_plotter = build_plotter_adapter(axidraw_config)

    assert mock_plotter.driver == "mock-plotter"
    assert axidraw_plotter.driver == "axidraw-pyapi"
