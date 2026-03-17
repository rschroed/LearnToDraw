from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Optional


MM_PER_INCH = 25.4


@dataclass(frozen=True)
class AxiDrawModelInfo:
    code: int
    label: str
    bounds_width_mm: float
    bounds_height_mm: float


_FALLBACK_MODELS: dict[int, tuple[str, float, float]] = {
    1: ("AxiDraw V2/V3/SE A4", 300.0, 218.0),
    2: ("AxiDraw V3/A3 or SE/A3", 430.0, 297.0),
    3: ("AxiDraw V3 XLX", 595.0, 218.0),
    4: ("AxiDraw MiniKit", 160.0, 101.6),
    5: ("AxiDraw SE/A1", 864.0, 594.0),
    6: ("AxiDraw SE/A2", 594.0, 432.0),
    7: ("AxiDraw V3/B6", 190.0, 140.0),
}


def default_axidraw_model_code() -> int:
    try:
        module = import_module("axidrawinternal.axidraw_conf")
    except Exception:
        return 1
    value = getattr(module, "model", None)
    return int(value) if isinstance(value, int) else 1


def axidraw_model_catalog() -> dict[int, AxiDrawModelInfo]:
    try:
        module = import_module("axidrawinternal.axidraw_conf")
    except Exception:
        return {
            code: AxiDrawModelInfo(code, label, width_mm, height_mm)
            for code, (label, width_mm, height_mm) in _FALLBACK_MODELS.items()
        }

    travel_lookup = {
        1: (
            "AxiDraw V2/V3/SE A4",
            getattr(module, "x_travel_default", None),
            getattr(module, "y_travel_default", None),
        ),
        2: (
            "AxiDraw V3/A3 or SE/A3",
            getattr(module, "x_travel_V3A3", None),
            getattr(module, "y_travel_V3A3", None),
        ),
        3: (
            "AxiDraw V3 XLX",
            getattr(module, "x_travel_V3XLX", None),
            getattr(module, "y_travel_V3XLX", None),
        ),
        4: (
            "AxiDraw MiniKit",
            getattr(module, "x_travel_MiniKit", None),
            getattr(module, "y_travel_MiniKit", None),
        ),
        5: (
            "AxiDraw SE/A1",
            getattr(module, "x_travel_SEA1", None),
            getattr(module, "y_travel_SEA1", None),
        ),
        6: (
            "AxiDraw SE/A2",
            getattr(module, "x_travel_SEA2", None),
            getattr(module, "y_travel_SEA2", None),
        ),
        7: (
            "AxiDraw V3/B6",
            getattr(module, "x_travel_V3B6", None),
            getattr(module, "y_travel_V3B6", None),
        ),
    }
    catalog: dict[int, AxiDrawModelInfo] = {}
    for code, (label, width_inches, height_inches) in travel_lookup.items():
        if isinstance(width_inches, (int, float)) and isinstance(height_inches, (int, float)):
            catalog[code] = AxiDrawModelInfo(
                code=code,
                label=label,
                bounds_width_mm=round(float(width_inches) * MM_PER_INCH, 3),
                bounds_height_mm=round(float(height_inches) * MM_PER_INCH, 3),
            )
            continue
        fallback = _FALLBACK_MODELS.get(code)
        if fallback is None:
            continue
        fallback_label, fallback_width_mm, fallback_height_mm = fallback
        catalog[code] = AxiDrawModelInfo(
            code=code,
            label=fallback_label,
            bounds_width_mm=fallback_width_mm,
            bounds_height_mm=fallback_height_mm,
        )
    return catalog


def resolve_axidraw_model_info(model_code: Optional[int]) -> AxiDrawModelInfo:
    code = model_code if model_code is not None else default_axidraw_model_code()
    catalog = axidraw_model_catalog()
    if code not in catalog:
        raise ValueError(f"Unsupported AxiDraw model code '{code}'.")
    return catalog[code]
