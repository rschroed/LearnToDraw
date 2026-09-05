from __future__ import annotations

import math
import xml.etree.ElementTree as ET

import resvg_py

from learn_to_draw_api.models import InvalidArtifactError
from learn_to_draw_api.services.plot_workflow_preparation import (
    SVG_SHAPE_TAGS,
    extract_source_box,
    extract_source_content_ratios,
    parse_svg_root,
)


ALLOWED_ADVISOR_SVG_TAGS = SVG_SHAPE_TAGS | {"svg", "g", "title", "desc"}
DIMENSION_EPSILON_MM = 0.01
REVIEW_RENDER_LONG_SIDE_PX = 1600


def validate_and_normalize_advisor_svg(
    svg_text: str,
    *,
    drawable_width_mm: float,
    drawable_height_mm: float,
) -> str:
    root = parse_svg_root(svg_text)
    source_box = extract_source_box(root)
    dimensions = (
        source_box.physical_width_mm,
        source_box.physical_height_mm,
        source_box.view_box_min_x,
        source_box.view_box_min_y,
        source_box.view_box_width,
        source_box.view_box_height,
    )
    if not all(value is not None and math.isfinite(value) for value in dimensions):
        raise InvalidArtifactError(
            "Advisor SVG must declare finite physical dimensions and a viewBox."
        )
    if (
        abs((source_box.physical_width_mm or 0) - drawable_width_mm)
        > DIMENSION_EPSILON_MM
        or abs((source_box.physical_height_mm or 0) - drawable_height_mm)
        > DIMENSION_EPSILON_MM
        or abs(source_box.view_box_min_x) > DIMENSION_EPSILON_MM
        or abs(source_box.view_box_min_y) > DIMENSION_EPSILON_MM
        or abs(source_box.view_box_width - drawable_width_mm) > DIMENSION_EPSILON_MM
        or abs(source_box.view_box_height - drawable_height_mm) > DIMENSION_EPSILON_MM
    ):
        raise InvalidArtifactError(
            "Advisor SVG canvas must exactly match the current drawable area in millimeters."
        )
    shape_count = 0
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag not in ALLOWED_ADVISOR_SVG_TAGS:
            raise InvalidArtifactError(f"Advisor SVG element '{tag}' is not allowed.")
        for attribute in element.attrib:
            local_attribute = attribute.rsplit("}", 1)[-1].lower()
            if local_attribute.startswith("on") or local_attribute in {
                "href",
                "style",
                "class",
                "transform",
            }:
                raise InvalidArtifactError(
                    f"Advisor SVG attribute '{local_attribute}' is not allowed."
                )
        if tag in SVG_SHAPE_TAGS:
            shape_count += 1
            element.attrib["fill"] = "none"
            element.attrib["stroke"] = "black"
            element.attrib["stroke-width"] = "0.6"
    if shape_count == 0:
        raise InvalidArtifactError("Advisor SVG must contain at least one drawable mark.")
    content_ratios = extract_source_content_ratios(root, source_box=source_box)
    if content_ratios is None:
        raise InvalidArtifactError("Advisor SVG marks could not be bounded safely.")
    left, top, width, height = content_ratios
    if (
        left < -DIMENSION_EPSILON_MM
        or top < -DIMENSION_EPSILON_MM
        or left + width > 1 + DIMENSION_EPSILON_MM
        or top + height > 1 + DIMENSION_EPSILON_MM
    ):
        raise InvalidArtifactError("Advisor SVG contains marks outside the drawable area.")
    return ET.tostring(root, encoding="unicode")


def render_advisor_svg_png(
    svg_text: str,
    *,
    drawable_width_mm: float,
    drawable_height_mm: float,
) -> bytes:
    if drawable_width_mm >= drawable_height_mm:
        output_width = REVIEW_RENDER_LONG_SIDE_PX
        output_height = max(
            1,
            round(REVIEW_RENDER_LONG_SIDE_PX * drawable_height_mm / drawable_width_mm),
        )
    else:
        output_height = REVIEW_RENDER_LONG_SIDE_PX
        output_width = max(
            1,
            round(REVIEW_RENDER_LONG_SIDE_PX * drawable_width_mm / drawable_height_mm),
        )
    render_root = ET.fromstring(svg_text)
    render_root.attrib["width"] = str(output_width)
    render_root.attrib["height"] = str(output_height)
    render_svg = ET.tostring(render_root, encoding="unicode")
    try:
        return resvg_py.svg_to_bytes(
            svg_string=render_svg,
            width=output_width,
            height=output_height,
            background="#ffffff",
            dpi=96,
        )
    except (OSError, OverflowError, TypeError, ValueError) as exc:
        raise InvalidArtifactError(
            f"Advisor SVG could not be rendered for creative review: {exc}"
        ) from exc
