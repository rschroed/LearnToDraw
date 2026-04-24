from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal, Optional

import numpy as np

from learn_to_draw_api.models import (
    NormalizationDiagnostics,
    NormalizationCorners,
    NormalizationMethodDiagnostics,
    NormalizationMetadata,
    NormalizationMethod,
    NormalizationTargetFrameSource,
)


CANONICAL_LONG_SIDE_PX = 2048
MAX_DETECTION_DIMENSION_PX = 1600
MIN_QUAD_AREA_RATIO = 0.15
LOW_CONFIDENCE_THRESHOLD = 0.55
CANONICAL_PAGE_BACKGROUND_COLOR = (255, 255, 255)
BRIGHT_REGION_FLOOR_LUMA = 104
MIN_REGION_FILL_RATIO = 0.58
MAX_DETECTION_MARGIN_RATIO = 0.06
MAX_ASPECT_LOG_ERROR = math.log(1.8)
REGION_BOX_QUANTILE = 5.0
SNAP_BOX_QUANTILE = 2.0
REGION_OUTWARD_EXPANSION_PX = 3.0
REGION_INWARD_EXPANSION_PX = 18.0
REGION_ALLOWED_OUTWARD_EXPANSION_PX = 2.0
REGION_EDGE_ORTHOGONAL_BAND_PX = 12.0
REGION_EDGE_SAMPLE_OFFSET_PX = 8.0
REGION_MIN_SIDE_SCORE = 0.28
REGION_MIN_MEAN_BORDER_SUPPORT = 0.45
REGION_MAX_REFINED_AREA_RATIO = 1.12
REGION_FINAL_INSET_PX = 4.0
NormalizationMode = Literal["default", "region_only"]
NormalizationExperiment = Literal["region_v2", "contour_v3"]


@dataclass(frozen=True)
class NormalizationTarget:
    page_width_mm: float
    page_height_mm: float
    source: NormalizationTargetFrameSource

    @property
    def aspect_ratio(self) -> float:
        return self.page_width_mm / self.page_height_mm


@dataclass(frozen=True)
class NormalizationArtifacts:
    rectified_color: bytes
    rectified_grayscale: bytes
    debug_overlay: bytes
    metadata: NormalizationMetadata


@dataclass(frozen=True)
class CaptureNormalizationProposal:
    corners: NormalizationCorners
    confidence: float
    method: NormalizationMethod
    diagnostics: NormalizationDiagnostics


@dataclass(frozen=True)
class DetectionCandidate:
    corners: np.ndarray
    confidence: float
    method: NormalizationMethod


@dataclass(frozen=True)
class LineCandidate:
    points: np.ndarray
    length: float
    midpoint_x: float
    midpoint_y: float
    angle_degrees: float


@dataclass(frozen=True)
class DetectorCandidateDiagnostics:
    corners: Optional[np.ndarray] = None
    bounds: Optional[tuple[int, int, int, int]] = None
    component_area: Optional[float] = None
    rect_area: Optional[float] = None
    fill_ratio: Optional[float] = None
    occupancy_score: Optional[float] = None
    edge_support_score: Optional[float] = None
    top_score: Optional[float] = None
    right_score: Optional[float] = None
    bottom_score: Optional[float] = None
    left_score: Optional[float] = None
    mean_border_support: Optional[float] = None
    max_outward_expansion_px: Optional[float] = None
    refined_area_ratio: Optional[float] = None
    aspect_log_error: Optional[float] = None
    score: Optional[float] = None
    confidence: Optional[float] = None
    rejection_reason: Optional[str] = None


@dataclass(frozen=True)
class DetectorRunDiagnostics:
    status: Literal["used", "rejected", "not_run", "unavailable"]
    rejection_reason: Optional[str] = None
    candidate_count: int = 0
    best_candidate: Optional[DetectorCandidateDiagnostics] = None


@dataclass(frozen=True)
class DetectionResult:
    candidate: DetectionCandidate
    diagnostics: NormalizationDiagnostics


def not_run_diagnostics() -> NormalizationMethodDiagnostics:
    return NormalizationMethodDiagnostics(
        status="not_run",
        candidate_count=0,
    )
