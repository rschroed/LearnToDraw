from __future__ import annotations

from typing import Protocol

from learn_to_draw_api.models import DeviceStatus, PlotDocument, PlotResult, PlotterTestAction


class PlotterAdapter(Protocol):
    driver: str

    def connect(self) -> None:
        ...

    def disconnect(self) -> None:
        ...

    def get_status(self) -> DeviceStatus:
        ...

    def return_to_origin(self) -> None:
        ...

    def set_pen_heights(self, *, pen_pos_up: int, pen_pos_down: int) -> None:
        ...

    def run_test_action(self, action: PlotterTestAction) -> None:
        ...

    def plot(self, document: PlotDocument) -> PlotResult:
        ...
