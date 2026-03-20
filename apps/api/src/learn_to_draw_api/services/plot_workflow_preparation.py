from __future__ import annotations

import copy
import math
from pathlib import Path
import re
from typing import Optional
import xml.etree.ElementTree as ET

from learn_to_draw_api.models import (
    InvalidArtifactError,
    PlotArea,
    PlotAsset,
    PlotDocument,
    PlotPreparationMetadata,
    PlotRunPurpose,
    PlotterDeviceSettings,
    PlotterWorkspace,
)


PATTERNS_DIR = Path(__file__).resolve().parent.parent / "assets" / "patterns"
PREPARATION_EPSILON_MM = 0.001
NORMAL_PREPARATION_STRATEGY = "fit_top_left"
DIAGNOSTIC_PREPARATION_STRATEGY = "diagnostic_passthrough"

ET.register_namespace("", "http://www.w3.org/2000/svg")


def parse_svg_root(svg_text: str) -> ET.Element:
    if not svg_text.strip():
        raise InvalidArtifactError("SVG content cannot be empty.")
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as exc:
        raise InvalidArtifactError("Provided content is not valid XML/SVG.") from exc
    if not root.tag.lower().endswith("svg"):
        raise InvalidArtifactError("Provided content is not an SVG document.")
    return root


def pattern_definition(pattern_id: str) -> Optional[dict[str, str]]:
    patterns = {
        "test-grid": {
            "name": "Test grid",
            "filename": "test-grid.svg",
        },
        "tiny-square": {
            "name": "Tiny square",
            "filename": "tiny-square.svg",
        },
        "dash-row": {
            "name": "Dash row",
            "filename": "dash-row.svg",
        },
        "double-box": {
            "name": "Double box",
            "filename": "double-box.svg",
        },
    }
    pattern = patterns.get(pattern_id)
    if pattern is None:
        return None
    return {
        "name": pattern["name"],
        "svg_text": (PATTERNS_DIR / pattern["filename"]).read_text(encoding="utf-8"),
    }


def load_document(
    asset: PlotAsset,
    *,
    purpose: PlotRunPurpose,
    workspace: PlotterWorkspace,
    device_settings: PlotterDeviceSettings,
) -> tuple[PlotDocument, PlotPreparationMetadata]:
    svg_text = Path(asset.file_path).read_text(encoding="utf-8")
    root = parse_svg_root(svg_text)
    prepared_svg_text, preparation = prepare_svg_for_plotting(
        svg_text,
        root,
        purpose=purpose,
        plot_area=workspace.to_plot_area(),
        device_settings=device_settings,
    )
    width, height = extract_svg_dimensions(root)
    document = PlotDocument(
        asset_id=asset.id,
        name=asset.name,
        svg_text=prepared_svg_text,
        width=width,
        height=height,
        prepared_width_mm=preparation.prepared_width_mm,
        prepared_height_mm=preparation.prepared_height_mm,
    )
    return document, preparation


def extract_svg_dimensions(root: ET.Element) -> tuple[int, int]:
    width = coerce_svg_dimension(root.attrib.get("width"))
    height = coerce_svg_dimension(root.attrib.get("height"))
    if width and height:
        return width, height
    view_box = parse_view_box(root.attrib.get("viewBox"))
    if view_box:
        width = width or max(1, int(round(view_box[2])))
        height = height or max(1, int(round(view_box[3])))
    return width or 1000, height or 1000


def coerce_svg_dimension(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    match = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)", value)
    if not match:
        return None
    return max(1, int(round(float(match.group(1)))))


def prepare_svg_for_plotting(
    svg_text: str,
    root: ET.Element,
    *,
    purpose: PlotRunPurpose,
    plot_area: PlotArea,
    device_settings: PlotterDeviceSettings,
) -> tuple[str, PlotPreparationMetadata]:
    source_box = extract_source_box(root)
    source_units = classify_source_units(root)
    units_inferred = source_units in {"unitless", "px", "unknown"}
    strategy = (
        DIAGNOSTIC_PREPARATION_STRATEGY
        if purpose == "diagnostic"
        else NORMAL_PREPARATION_STRATEGY
    )
    workspace_audit = build_workspace_audit(
        plot_area=plot_area,
        device_settings=device_settings,
    )

    if strategy == DIAGNOSTIC_PREPARATION_STRATEGY:
        if source_box.physical_width_mm is None or source_box.physical_height_mm is None:
            raise InvalidArtifactError(
                "Diagnostic plotting requires explicit physical SVG dimensions such as mm, cm, or in."
            )
        prepared_width_mm = source_box.physical_width_mm
        prepared_height_mm = source_box.physical_height_mm
        preparation_audit = build_preparation_audit(
            strategy=strategy,
            plot_area=plot_area,
            prepared_width_mm=prepared_width_mm,
            prepared_height_mm=prepared_height_mm,
            scale=None,
            placement_origin_x_mm=0.0,
            placement_origin_y_mm=0.0,
            prepared_view_box=None,
        )
        validate_preparation_consistency(
            prepared_width_mm=prepared_width_mm,
            prepared_height_mm=prepared_height_mm,
            preparation_audit=preparation_audit,
            drawable_width_mm=plot_area.draw_width_mm,
            drawable_height_mm=plot_area.draw_height_mm,
        )
        if not preparation_audit.prepared_within_drawable_area:
            preparation = build_preparation_metadata(
                source_box=source_box,
                source_units=source_units,
                units_inferred=units_inferred,
                prepared_width_mm=prepared_width_mm,
                prepared_height_mm=prepared_height_mm,
                plot_area=plot_area,
                device_settings=device_settings,
                workspace_audit=workspace_audit,
                preparation_audit=preparation_audit,
            )
            raise PreparationValidationError(
                "Diagnostic SVG size "
                f"{format_mm(prepared_width_mm)} x {format_mm(prepared_height_mm)} mm "
                "exceeds the current drawable area of "
                f"{format_mm(plot_area.draw_width_mm)} x {format_mm(plot_area.draw_height_mm)} mm.",
                preparation=preparation,
            )
        prepared_svg_text = svg_text
    else:
        if source_box.view_box_width <= 0 or source_box.view_box_height <= 0:
            raise InvalidArtifactError("SVG content is missing usable size information.")
        scale = select_normal_preparation_scale(
            plot_area=plot_area,
            source_box=source_box,
        )
        if not math.isfinite(scale):
            raise PreparationValidationError(
                "Prepared SVG math produced non-finite bounds or scale."
            )
        if scale <= 0:
            raise PreparationValidationError(
                "Prepared SVG math produced a non-positive output scale."
            )
        prepared_width_mm = source_box.view_box_width * scale
        prepared_height_mm = source_box.view_box_height * scale
        preparation_audit = build_preparation_audit(
            strategy=strategy,
            plot_area=plot_area,
            prepared_width_mm=prepared_width_mm,
            prepared_height_mm=prepared_height_mm,
            scale=scale,
            placement_origin_x_mm=plot_area.margin_left_mm,
            placement_origin_y_mm=plot_area.margin_top_mm,
            prepared_view_box=(0.0, 0.0, plot_area.page_width_mm, plot_area.page_height_mm),
        )
        validate_preparation_consistency(
            prepared_width_mm=prepared_width_mm,
            prepared_height_mm=prepared_height_mm,
            preparation_audit=preparation_audit,
            drawable_width_mm=plot_area.draw_width_mm,
            drawable_height_mm=plot_area.draw_height_mm,
        )
        if not preparation_audit.prepared_within_drawable_area:
            preparation = build_preparation_metadata(
                source_box=source_box,
                source_units=source_units,
                units_inferred=units_inferred,
                prepared_width_mm=prepared_width_mm,
                prepared_height_mm=prepared_height_mm,
                plot_area=plot_area,
                device_settings=device_settings,
                workspace_audit=workspace_audit,
                preparation_audit=preparation_audit,
            )
            raise PreparationValidationError(
                "Prepared SVG math exceeded the current drawable area by "
                f"{format_mm(preparation_audit.overflow_x_mm)} x "
                f"{format_mm(preparation_audit.overflow_y_mm)} mm.",
                preparation=preparation,
            )
        prepared_svg_text = build_prepared_svg(
            root,
            plot_area=plot_area,
            source_box=source_box,
            scale=scale,
            placement_origin_x_mm=plot_area.margin_left_mm,
            placement_origin_y_mm=plot_area.margin_top_mm,
        )
    return (
        prepared_svg_text,
        build_preparation_metadata(
            source_box=source_box,
            source_units=source_units,
            units_inferred=units_inferred,
            prepared_width_mm=prepared_width_mm,
            prepared_height_mm=prepared_height_mm,
            plot_area=plot_area,
            device_settings=device_settings,
            workspace_audit=workspace_audit,
            preparation_audit=preparation_audit,
        ),
    )


class SourceBox:
    def __init__(
        self,
        *,
        reported_width: float,
        reported_height: float,
        physical_width_mm: Optional[float],
        physical_height_mm: Optional[float],
        view_box_min_x: float,
        view_box_min_y: float,
        view_box_width: float,
        view_box_height: float,
    ) -> None:
        self.reported_width = reported_width
        self.reported_height = reported_height
        self.physical_width_mm = physical_width_mm
        self.physical_height_mm = physical_height_mm
        self.view_box_min_x = view_box_min_x
        self.view_box_min_y = view_box_min_y
        self.view_box_width = view_box_width
        self.view_box_height = view_box_height


class PreparationValidationError(InvalidArtifactError):
    def __init__(
        self,
        message: str,
        *,
        preparation: Optional[PlotPreparationMetadata] = None,
    ) -> None:
        super().__init__(message)
        self.preparation = preparation


def extract_source_box(root: ET.Element) -> SourceBox:
    width_length = parse_svg_length(root.attrib.get("width"))
    height_length = parse_svg_length(root.attrib.get("height"))
    view_box = parse_view_box(root.attrib.get("viewBox"))

    if view_box is not None:
        min_x, min_y, view_box_width, view_box_height = view_box
    else:
        if width_length is None or height_length is None:
            raise InvalidArtifactError("SVG content is missing width/height or viewBox values.")
        min_x = 0.0
        min_y = 0.0
        view_box_width = width_length[0]
        view_box_height = height_length[0]

    reported_width = width_length[0] if width_length is not None else view_box_width
    reported_height = height_length[0] if height_length is not None else view_box_height
    physical_width_mm = length_to_mm(width_length)
    physical_height_mm = length_to_mm(height_length)

    return SourceBox(
        reported_width=reported_width,
        reported_height=reported_height,
        physical_width_mm=physical_width_mm,
        physical_height_mm=physical_height_mm,
        view_box_min_x=min_x,
        view_box_min_y=min_y,
        view_box_width=view_box_width,
        view_box_height=view_box_height,
    )


def build_workspace_audit(
    *,
    plot_area: PlotArea,
    device_settings: PlotterDeviceSettings,
) -> PlotPreparationMetadata.WorkspaceAudit:
    plotter_bounds = device_settings.plotter_bounds_mm
    return PlotPreparationMetadata.WorkspaceAudit(
        page_within_plotter_bounds=(
            plot_area.page_width_mm <= plotter_bounds.width_mm + PREPARATION_EPSILON_MM
            and plot_area.page_height_mm <= plotter_bounds.height_mm + PREPARATION_EPSILON_MM
        ),
        drawable_area_positive=(
            plot_area.draw_width_mm > 0 and plot_area.draw_height_mm > 0
        ),
        drawable_origin_x_mm=round(plot_area.margin_left_mm, 3),
        drawable_origin_y_mm=round(plot_area.margin_top_mm, 3),
        remaining_bounds_right_mm=round(
            plotter_bounds.width_mm - plot_area.page_width_mm,
            3,
        ),
        remaining_bounds_bottom_mm=round(
            plotter_bounds.height_mm - plot_area.page_height_mm,
            3,
        ),
    )


def build_preparation_audit(
    *,
    strategy: str,
    plot_area: PlotArea,
    prepared_width_mm: float,
    prepared_height_mm: float,
    scale: Optional[float],
    placement_origin_x_mm: Optional[float],
    placement_origin_y_mm: Optional[float],
    prepared_view_box: Optional[tuple[float, float, float, float]],
) -> PlotPreparationMetadata.PreparationAudit:
    overflow_x = max(0.0, prepared_width_mm - plot_area.draw_width_mm)
    overflow_y = max(0.0, prepared_height_mm - plot_area.draw_height_mm)
    content_min_x_mm = placement_origin_x_mm
    content_min_y_mm = placement_origin_y_mm
    content_max_x_mm = (
        None
        if placement_origin_x_mm is None
        else placement_origin_x_mm + prepared_width_mm
    )
    content_max_y_mm = (
        None
        if placement_origin_y_mm is None
        else placement_origin_y_mm + prepared_height_mm
    )
    return PlotPreparationMetadata.PreparationAudit(
        strategy=strategy,
        fit_scale=round(scale, 6) if scale is not None else None,
        prepared_within_drawable_area=(
            overflow_x <= PREPARATION_EPSILON_MM and overflow_y <= PREPARATION_EPSILON_MM
        ),
        overflow_x_mm=round(overflow_x, 6),
        overflow_y_mm=round(overflow_y, 6),
        placement_origin_x_mm=(
            round(placement_origin_x_mm, 3)
            if placement_origin_x_mm is not None
            else None
        ),
        placement_origin_y_mm=(
            round(placement_origin_y_mm, 3)
            if placement_origin_y_mm is not None
            else None
        ),
        content_min_x_mm=round(content_min_x_mm, 3) if content_min_x_mm is not None else None,
        content_min_y_mm=round(content_min_y_mm, 3) if content_min_y_mm is not None else None,
        content_max_x_mm=round(content_max_x_mm, 3) if content_max_x_mm is not None else None,
        content_max_y_mm=round(content_max_y_mm, 3) if content_max_y_mm is not None else None,
        content_width_mm=round(prepared_width_mm, 3),
        content_height_mm=round(prepared_height_mm, 3),
        prepared_viewbox_min_x=(
            round(prepared_view_box[0], 3) if prepared_view_box is not None else None
        ),
        prepared_viewbox_min_y=(
            round(prepared_view_box[1], 3) if prepared_view_box is not None else None
        ),
        prepared_viewbox_width=(
            round(prepared_view_box[2], 3) if prepared_view_box is not None else None
        ),
        prepared_viewbox_height=(
            round(prepared_view_box[3], 3) if prepared_view_box is not None else None
        ),
    )


def build_preparation_metadata(
    *,
    source_box: SourceBox,
    source_units: str,
    units_inferred: bool,
    prepared_width_mm: float,
    prepared_height_mm: float,
    plot_area: PlotArea,
    device_settings: PlotterDeviceSettings,
    workspace_audit: PlotPreparationMetadata.WorkspaceAudit,
    preparation_audit: PlotPreparationMetadata.PreparationAudit,
) -> PlotPreparationMetadata:
    return PlotPreparationMetadata(
        source_width=source_box.reported_width,
        source_height=source_box.reported_height,
        source_units=source_units,
        prepared_width_mm=round(prepared_width_mm, 3),
        prepared_height_mm=round(prepared_height_mm, 3),
        page_width_mm=round(plot_area.page_width_mm, 3),
        page_height_mm=round(plot_area.page_height_mm, 3),
        drawable_width_mm=round(plot_area.draw_width_mm, 3),
        drawable_height_mm=round(plot_area.draw_height_mm, 3),
        plotter_bounds_width_mm=round(device_settings.plotter_bounds_mm.width_mm, 3),
        plotter_bounds_height_mm=round(device_settings.plotter_bounds_mm.height_mm, 3),
        plotter_bounds_source=device_settings.plotter_bounds_source,
        plotter_model_code=(
            device_settings.plotter_model.code
            if device_settings.plotter_model is not None
            else None
        ),
        plotter_model_label=(
            device_settings.plotter_model.label
            if device_settings.plotter_model is not None
            else None
        ),
        units_inferred=units_inferred,
        workspace_audit=workspace_audit,
        preparation_audit=preparation_audit,
    )


def validate_preparation_consistency(
    *,
    prepared_width_mm: float,
    prepared_height_mm: float,
    preparation_audit: PlotPreparationMetadata.PreparationAudit,
    drawable_width_mm: float,
    drawable_height_mm: float,
) -> None:
    values = [
        prepared_width_mm,
        prepared_height_mm,
        drawable_width_mm,
        drawable_height_mm,
        preparation_audit.overflow_x_mm,
        preparation_audit.overflow_y_mm,
    ]
    if preparation_audit.fit_scale is not None:
        values.append(preparation_audit.fit_scale)
    for maybe_value in (
        preparation_audit.prepared_viewbox_min_x,
        preparation_audit.prepared_viewbox_min_y,
        preparation_audit.prepared_viewbox_width,
        preparation_audit.prepared_viewbox_height,
    ):
        if maybe_value is not None:
            values.append(maybe_value)
    if not all(math.isfinite(value) for value in values):
        raise PreparationValidationError(
            "Prepared SVG math produced non-finite bounds or scale."
        )
    if prepared_width_mm <= 0 or prepared_height_mm <= 0:
        raise PreparationValidationError(
            "Prepared SVG math produced a non-positive output size."
        )


def select_normal_preparation_scale(
    *,
    plot_area: PlotArea,
    source_box: SourceBox,
) -> float:
    fit_scale = min(
        plot_area.draw_width_mm / source_box.view_box_width,
        plot_area.draw_height_mm / source_box.view_box_height,
    )
    authored_scale_value = authored_scale(source_box)
    if authored_scale_value is None:
        return fit_scale
    authored_width_mm = source_box.view_box_width * authored_scale_value
    authored_height_mm = source_box.view_box_height * authored_scale_value
    if (
        authored_width_mm <= plot_area.draw_width_mm + PREPARATION_EPSILON_MM
        and authored_height_mm <= plot_area.draw_height_mm + PREPARATION_EPSILON_MM
    ):
        return authored_scale_value
    return fit_scale


def authored_scale(source_box: SourceBox) -> Optional[float]:
    if source_box.physical_width_mm is None or source_box.physical_height_mm is None:
        return None
    scale_x = source_box.physical_width_mm / source_box.view_box_width
    scale_y = source_box.physical_height_mm / source_box.view_box_height
    return min(scale_x, scale_y)


def build_prepared_svg(
    root: ET.Element,
    *,
    plot_area: PlotArea,
    source_box: SourceBox,
    scale: float,
    placement_origin_x_mm: float,
    placement_origin_y_mm: float,
) -> str:
    root_copy = copy.deepcopy(root)
    root_copy.attrib["width"] = f"{format_mm(plot_area.page_width_mm)}mm"
    root_copy.attrib["height"] = f"{format_mm(plot_area.page_height_mm)}mm"
    root_copy.attrib["viewBox"] = (
        f"0 0 {format_numeric(plot_area.page_width_mm)} {format_numeric(plot_area.page_height_mm)}"
    )
    wrapper = ET.Element(
        qualify_svg_tag(root_copy.tag, "g"),
        {
            "transform": (
                f"translate({format_numeric(placement_origin_x_mm)} "
                f"{format_numeric(placement_origin_y_mm)}) "
                f"scale({format_numeric(scale)}) "
                f"translate({format_numeric(-source_box.view_box_min_x)} "
                f"{format_numeric(-source_box.view_box_min_y)})"
            )
        },
    )
    existing_children = list(root_copy)
    for child in existing_children:
        root_copy.remove(child)
        wrapper.append(child)
    root_copy.append(wrapper)
    return ET.tostring(root_copy, encoding="unicode")


def qualify_svg_tag(root_tag: str, name: str) -> str:
    if root_tag.startswith("{"):
        namespace, _ = root_tag[1:].split("}", 1)
        return f"{{{namespace}}}{name}"
    return name


def classify_source_units(root: ET.Element) -> str:
    width_length = parse_svg_length(root.attrib.get("width"))
    height_length = parse_svg_length(root.attrib.get("height"))
    units = {
        length[1]
        for length in (width_length, height_length)
        if length is not None and length[1] is not None
    }
    if not units:
        if width_length is None and height_length is None:
            return "unknown"
        return "unitless"
    if len(units) > 1:
        return "mixed"
    return next(iter(units))


def parse_svg_length(value: Optional[str]) -> Optional[tuple[float, Optional[str]]]:
    if value is None:
        return None
    match = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*([A-Za-z%]+)?\s*$", value)
    if not match:
        return None
    unit = (match.group(2) or "").lower() or None
    if unit == "%":
        return None
    return float(match.group(1)), unit


def length_to_mm(length: Optional[tuple[float, Optional[str]]]) -> Optional[float]:
    if length is None:
        return None
    value, unit = length
    if unit == "mm":
        return value
    if unit == "cm":
        return value * 10.0
    if unit == "in":
        return value * 25.4
    return None


def parse_view_box(value: Optional[str]) -> Optional[tuple[float, float, float, float]]:
    if not value:
        return None
    parts = re.split(r"[,\s]+", value.strip())
    if len(parts) != 4:
        return None
    try:
        min_x, min_y, width, height = (float(part) for part in parts)
    except ValueError:
        return None
    return min_x, min_y, width, height


def format_numeric(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def format_mm(value: float) -> str:
    return format_numeric(value)
