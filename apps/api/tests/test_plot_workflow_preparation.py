from __future__ import annotations

from datetime import datetime, timezone

import pytest

from learn_to_draw_api.models import PlotArea, PlotterDeviceSettings, SizeMm
from learn_to_draw_api.services.plot_workflow_preparation import (
    PreparationValidationError,
    parse_svg_root,
    pattern_definition,
    prepare_svg_for_plotting,
)


def build_device_settings() -> PlotterDeviceSettings:
    return PlotterDeviceSettings(
        driver="mock",
        plotter_model=None,
        nominal_plotter_bounds_mm=SizeMm(width_mm=210.0, height_mm=297.0),
        nominal_plotter_bounds_source="config_default",
        plotter_bounds_mm=SizeMm(width_mm=210.0, height_mm=297.0),
        plotter_bounds_source="config_default",
        updated_at=datetime.now(timezone.utc),
        source="config_default",
    )


def build_plot_area() -> PlotArea:
    return PlotArea(
        page_width_mm=210.0,
        page_height_mm=297.0,
        margin_left_mm=20.0,
        margin_top_mm=20.0,
        margin_right_mm=20.0,
        margin_bottom_mm=20.0,
    )


def test_pattern_definition_returns_built_in_assets() -> None:
    tiny_square = pattern_definition("tiny-square")

    assert tiny_square is not None
    assert tiny_square["name"] == "Tiny square"
    assert 'width="20mm"' in tiny_square["svg_text"]


def test_prepare_svg_for_plotting_keeps_diagnostic_passthrough_when_size_fits() -> None:
    svg_text = (
        "<svg xmlns='http://www.w3.org/2000/svg' width='40mm' height='12mm' "
        "viewBox='0 0 40 12'><path d='M 0 0 H 40' /></svg>"
    )
    root = parse_svg_root(svg_text)

    prepared_svg_text, preparation = prepare_svg_for_plotting(
        svg_text,
        root,
        purpose="diagnostic",
        plot_area=build_plot_area(),
        device_settings=build_device_settings(),
    )

    assert prepared_svg_text == svg_text
    assert preparation.prepared_width_mm == 40.0
    assert preparation.prepared_height_mm == 12.0
    assert preparation.preparation_audit.strategy == "diagnostic_passthrough"
    assert preparation.preparation_audit.prepared_within_drawable_area is True


def test_prepare_svg_for_plotting_reports_diagnostic_overflow() -> None:
    svg_text = (
        "<svg xmlns='http://www.w3.org/2000/svg' width='300mm' height='240mm' "
        "viewBox='0 0 300 240'><path d='M 0 0 H 300' /></svg>"
    )
    root = parse_svg_root(svg_text)

    with pytest.raises(PreparationValidationError) as exc_info:
        prepare_svg_for_plotting(
            svg_text,
            root,
            purpose="diagnostic",
            plot_area=build_plot_area(),
            device_settings=build_device_settings(),
        )

    assert "exceeds the current drawable area" in str(exc_info.value)
    assert exc_info.value.preparation is not None
    assert exc_info.value.preparation.preparation_audit.strategy == "diagnostic_passthrough"
    assert exc_info.value.preparation.preparation_audit.prepared_within_drawable_area is False


def test_prepare_svg_for_plotting_prefers_authored_scale_for_smaller_explicit_units() -> None:
    svg_text = (
        "<svg xmlns='http://www.w3.org/2000/svg' width='40mm' height='20mm' "
        "viewBox='0 0 200 100'><path d='M 0 0 H 200' /></svg>"
    )
    root = parse_svg_root(svg_text)

    _, preparation = prepare_svg_for_plotting(
        svg_text,
        root,
        purpose="normal",
        plot_area=build_plot_area(),
        device_settings=build_device_settings(),
    )

    assert preparation.prepared_width_mm == 40.0
    assert preparation.prepared_height_mm == 20.0
    assert preparation.preparation_audit.fit_scale == 0.2
    assert preparation.preparation_audit.strategy == "fit_top_left"


def test_prepare_svg_for_plotting_rejects_non_finite_viewbox_math() -> None:
    svg_text = (
        "<svg xmlns='http://www.w3.org/2000/svg' width='200' height='100' "
        "viewBox='0 0 NaN 100'><path d='M 0 0 H 200' /></svg>"
    )
    root = parse_svg_root(svg_text)

    with pytest.raises(PreparationValidationError) as exc_info:
        prepare_svg_for_plotting(
            svg_text,
            root,
            purpose="normal",
            plot_area=build_plot_area(),
            device_settings=build_device_settings(),
        )

    assert str(exc_info.value) == "Prepared SVG math produced non-finite bounds or scale."
