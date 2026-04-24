from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal, Optional

import cv2
import numpy as np

from learn_to_draw_api.models import (
    NormalizationDiagnosticCandidate,
    NormalizationDiagnostics,
    NormalizationCorners,
    NormalizationFrame,
    NormalizationMethodDiagnostics,
    NormalizationMetadata,
    NormalizationMethod,
    NormalizationOutput,
    NormalizationTargetFrameSource,
    NormalizationTransform,
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


def _not_run_diagnostics() -> NormalizationMethodDiagnostics:
    return NormalizationMethodDiagnostics(
        status="not_run",
        candidate_count=0,
    )


class CaptureNormalizationService:
    def __init__(
        self,
        *,
        mode: NormalizationMode = "default",
        experiment: NormalizationExperiment = "region_v2",
    ) -> None:
        self._mode: NormalizationMode = (
            "region_only" if mode == "region_only" else "default"
        )
        self._experiment: NormalizationExperiment = (
            "contour_v3" if experiment == "contour_v3" else "region_v2"
        )

    def normalize(
        self,
        *,
        content: bytes,
        target: NormalizationTarget,
    ) -> NormalizationArtifacts:
        decoded = self._decode_image(content)
        if decoded is None:
            raise ValueError("Capture content is not a supported raster image.")

        detection_result = self._detect_paper(decoded, target_aspect_ratio=target.aspect_ratio)
        return self._normalize_from_detection_result(
            decoded,
            detection_result=detection_result,
            target=target,
        )

    def inspect(
        self,
        *,
        content: bytes,
        target: NormalizationTarget,
    ) -> CaptureNormalizationProposal:
        decoded = self._decode_image(content)
        if decoded is None:
            raise ValueError("Capture content is not a supported raster image.")
        detection_result = self._detect_paper(decoded, target_aspect_ratio=target.aspect_ratio)
        detection = detection_result.candidate
        return CaptureNormalizationProposal(
            corners=self._to_corners(detection.corners),
            confidence=float(round(detection.confidence, 6)),
            method=detection.method,
            diagnostics=detection_result.diagnostics,
        )

    def normalize_with_corners(
        self,
        *,
        content: bytes,
        target: NormalizationTarget,
        corners: NormalizationCorners,
        method: NormalizationMethod,
        confidence: float,
        diagnostics: Optional[NormalizationDiagnostics] = None,
    ) -> NormalizationArtifacts:
        decoded = self._decode_image(content)
        if decoded is None:
            raise ValueError("Capture content is not a supported raster image.")
        detection_result = DetectionResult(
            candidate=DetectionCandidate(
                corners=self._corners_to_numpy(corners),
                confidence=confidence,
                method=method,
            ),
            diagnostics=diagnostics
            or NormalizationDiagnostics(
                mode=self._mode,
                contour_v3=_not_run_diagnostics(),
                region_v2=_not_run_diagnostics(),
                line_v1=_not_run_diagnostics(),
            ),
        )
        return self._normalize_from_detection_result(
            decoded,
            detection_result=detection_result,
            target=target,
        )

    def _normalize_from_detection_result(
        self,
        decoded: np.ndarray,
        *,
        detection_result: DetectionResult,
        target: NormalizationTarget,
    ) -> NormalizationArtifacts:
        detection = detection_result.candidate
        rectified, matrix = self._rectify(decoded, detection.corners)
        if detection.method != "fallback_full_frame":
            rectified = self._trim_rectified_page(rectified)
        oriented = self._apply_orientation(rectified, target.aspect_ratio)
        resized = self._resize_to_canonical(oriented, target.aspect_ratio)
        grayscale = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        debug_overlay = self._build_debug_overlay(
            decoded,
            detection,
            diagnostics=detection_result.diagnostics,
        )

        rectified_color = self._encode_png(resized)
        rectified_grayscale = self._encode_png(grayscale)
        debug_overlay_png = self._encode_png(debug_overlay)
        return NormalizationArtifacts(
            rectified_color=rectified_color,
            rectified_grayscale=rectified_grayscale,
            debug_overlay=debug_overlay_png,
            metadata=NormalizationMetadata(
                method=detection.method,
                confidence=float(round(detection.confidence, 6)),
                corners=self._to_corners(detection.corners),
                transform=NormalizationTransform(
                    matrix=[
                        [float(round(value, 6)) for value in row]
                        for row in matrix.tolist()
                    ]
                ),
                output=NormalizationOutput(
                    width=int(resized.shape[1]),
                    height=int(resized.shape[0]),
                    aspect_ratio=float(round(target.aspect_ratio, 6)),
                ),
                target_frame_source=target.source,
                diagnostics=detection_result.diagnostics,
                frame=NormalizationFrame(
                    kind="page_aligned",
                    version=1,
                    page_width_mm=float(round(target.page_width_mm, 3)),
                    page_height_mm=float(round(target.page_height_mm, 3)),
                ),
            ),
        )

    def _decode_image(self, content: bytes) -> Optional[np.ndarray]:
        buffer = np.frombuffer(content, dtype=np.uint8)
        if buffer.size == 0:
            return None
        image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        return image

    def _detect_paper(
        self,
        image: np.ndarray,
        *,
        target_aspect_ratio: float,
    ) -> DetectionResult:
        scaled, scale = self._downscale_for_detection(image)
        image_area = float(scaled.shape[0] * scaled.shape[1])
        expected_shape_aspect_ratio = self._shape_aspect_ratio(target_aspect_ratio)
        contour_diagnostics = DetectorRunDiagnostics(status="not_run")
        region_diagnostics = DetectorRunDiagnostics(status="not_run")

        if self._experiment == "contour_v3":
            primary_candidate, contour_diagnostics = self._detect_contour_quad(
                scaled,
                image_area=image_area,
                expected_shape_aspect_ratio=expected_shape_aspect_ratio,
            )
            primary_method: NormalizationMethod = "paper_contour_v3"
        else:
            primary_candidate, region_diagnostics = self._detect_region_quad(
                scaled,
                image_area=image_area,
                expected_shape_aspect_ratio=expected_shape_aspect_ratio,
            )
            primary_method = "paper_region_v2"

        if primary_candidate is not None:
            ordered = self._order_corners(primary_candidate.corners / scale)
            return DetectionResult(
                candidate=DetectionCandidate(
                    corners=ordered,
                    confidence=float(max(0.0, min(1.0, primary_candidate.confidence))),
                    method=primary_method,
                ),
                diagnostics=NormalizationDiagnostics(
                    mode=self._mode,
                    contour_v3=(
                        self._to_method_diagnostics(contour_diagnostics, status="used")
                        if self._experiment == "contour_v3"
                        else _not_run_diagnostics()
                    ),
                    region_v2=(
                        self._to_method_diagnostics(region_diagnostics, status="used")
                        if self._experiment == "region_v2"
                        else _not_run_diagnostics()
                    ),
                    line_v1=_not_run_diagnostics(),
                ),
            )

        if self._mode == "region_only":
            return DetectionResult(
                candidate=DetectionCandidate(
                    corners=self._full_frame_corners(image),
                    confidence=0.0,
                    method="fallback_full_frame",
                ),
                diagnostics=NormalizationDiagnostics(
                    mode=self._mode,
                    contour_v3=(
                        self._to_method_diagnostics(
                            contour_diagnostics,
                            status="rejected" if contour_diagnostics.candidate_count > 0 else "unavailable",
                        )
                        if self._experiment == "contour_v3"
                        else _not_run_diagnostics()
                    ),
                    region_v2=(
                        self._to_method_diagnostics(
                            region_diagnostics,
                            status="rejected" if region_diagnostics.candidate_count > 0 else "unavailable",
                        )
                        if self._experiment == "region_v2"
                        else _not_run_diagnostics()
                    ),
                    line_v1=NormalizationMethodDiagnostics(
                        status="not_run",
                        rejection_reason="disabled_in_region_only_mode",
                        candidate_count=0,
                    ),
                ),
            )

        line_candidate, line_diagnostics = self._detect_line_quad(
            scaled,
            image_area=image_area,
            expected_shape_aspect_ratio=expected_shape_aspect_ratio,
        )
        if line_candidate is not None:
            ordered = self._order_corners(line_candidate.corners / scale)
            return DetectionResult(
                candidate=DetectionCandidate(
                    corners=ordered,
                    confidence=float(max(0.0, min(1.0, line_candidate.confidence))),
                    method="paper_edges_v1",
                ),
                diagnostics=NormalizationDiagnostics(
                    mode=self._mode,
                    contour_v3=(
                        self._to_method_diagnostics(
                            contour_diagnostics,
                            status="rejected" if contour_diagnostics.candidate_count > 0 else "unavailable",
                        )
                        if self._experiment == "contour_v3"
                        else _not_run_diagnostics()
                    ),
                    region_v2=(
                        self._to_method_diagnostics(
                            region_diagnostics,
                            status="rejected" if region_diagnostics.candidate_count > 0 else "unavailable",
                        )
                        if self._experiment == "region_v2"
                        else _not_run_diagnostics()
                    ),
                    line_v1=self._to_method_diagnostics(
                        line_diagnostics,
                        status="used",
                    ),
                ),
            )

        return DetectionResult(
            candidate=DetectionCandidate(
                corners=self._full_frame_corners(image),
                confidence=0.0,
                method="fallback_full_frame",
            ),
            diagnostics=NormalizationDiagnostics(
                mode=self._mode,
                contour_v3=(
                    self._to_method_diagnostics(
                        contour_diagnostics,
                        status="rejected" if contour_diagnostics.candidate_count > 0 else "unavailable",
                    )
                    if self._experiment == "contour_v3"
                    else _not_run_diagnostics()
                ),
                region_v2=(
                    self._to_method_diagnostics(
                        region_diagnostics,
                        status="rejected" if region_diagnostics.candidate_count > 0 else "unavailable",
                    )
                    if self._experiment == "region_v2"
                    else _not_run_diagnostics()
                ),
                line_v1=self._to_method_diagnostics(
                    line_diagnostics,
                    status="rejected" if line_diagnostics.candidate_count > 0 else "unavailable",
                ),
            ),
        )

    def _detect_region_quad(
        self,
        image: np.ndarray,
        *,
        image_area: float,
        expected_shape_aspect_ratio: float,
    ) -> tuple[Optional[DetectionCandidate], DetectorRunDiagnostics]:
        luma = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)[:, :, 0]
        blurred = cv2.GaussianBlur(luma, (7, 7), 0)
        gradient = self._gradient_magnitude(blurred)
        threshold_value, _ = cv2.threshold(
            blurred,
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU,
        )
        clamped_threshold = max(float(threshold_value), float(BRIGHT_REGION_FLOOR_LUMA))
        _, bright_mask = cv2.threshold(
            blurred,
            clamped_threshold,
            255,
            cv2.THRESH_BINARY,
        )
        bright_mask = cv2.morphologyEx(
            bright_mask,
            cv2.MORPH_CLOSE,
            np.ones((7, 7), dtype=np.uint8),
            iterations=1,
        )
        bright_mask = cv2.morphologyEx(
            bright_mask,
            cv2.MORPH_OPEN,
            np.ones((5, 5), dtype=np.uint8),
            iterations=1,
        )

        contours, _ = cv2.findContours(
            bright_mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        if not contours:
            return None, DetectorRunDiagnostics(
                status="unavailable",
                rejection_reason="no_region_contours",
                candidate_count=0,
            )

        minimum_area = image_area * MIN_QUAD_AREA_RATIO
        best_candidate: Optional[DetectionCandidate] = None
        best_score = -1.0
        best_rejected: Optional[DetectorCandidateDiagnostics] = None
        best_rejected_rank: tuple[int, float] = (-1, -1.0)
        candidate_count = 0
        height, width = image.shape[:2]
        for contour in contours:
            contour_bounds = cv2.boundingRect(contour)
            diagnostics = DetectorCandidateDiagnostics(bounds=contour_bounds)
            if self._touches_too_many_borders(
                contour_bounds,
                width=width,
                height=height,
            ):
                diagnostics = DetectorCandidateDiagnostics(
                    bounds=contour_bounds,
                    rejection_reason="touches_too_many_borders",
                )
                best_rejected, best_rejected_rank = self._consider_rejected_candidate(
                    diagnostics,
                    rank=(0, 0.0),
                    current=best_rejected,
                    current_rank=best_rejected_rank,
                )
                continue

            contour_mask = np.zeros(luma.shape, dtype=np.uint8)
            cv2.drawContours(contour_mask, [contour], -1, 255, thickness=-1)
            component_area = float(cv2.countNonZero(cv2.bitwise_and(contour_mask, bright_mask)))
            diagnostics = DetectorCandidateDiagnostics(
                bounds=contour_bounds,
                component_area=component_area,
            )
            if component_area < minimum_area:
                diagnostics = DetectorCandidateDiagnostics(
                    bounds=contour_bounds,
                    component_area=component_area,
                    rejection_reason="component_area_below_minimum",
                )
                best_rejected, best_rejected_rank = self._consider_rejected_candidate(
                    diagnostics,
                    rank=(1, component_area),
                    current=best_rejected,
                    current_rank=best_rejected_rank,
                )
                continue
            candidate_count += 1
            if self._is_oversized_top_band_region(
                contour_bounds,
                component_area=component_area,
                image_area=image_area,
                image_height=height,
            ):
                diagnostics = DetectorCandidateDiagnostics(
                    bounds=contour_bounds,
                    component_area=component_area,
                    rejection_reason="oversized_top_band_region",
                )
                best_rejected, best_rejected_rank = self._consider_rejected_candidate(
                    diagnostics,
                    rank=(2, component_area),
                    current=best_rejected,
                    current_rank=best_rejected_rank,
                )
                continue
            candidate_corners = self._fit_region_candidate_corners(contour)
            rect_width = float(np.linalg.norm(candidate_corners[1] - candidate_corners[0]))
            rect_height = float(np.linalg.norm(candidate_corners[3] - candidate_corners[0]))
            if rect_width <= 2.0 or rect_height <= 2.0:
                diagnostics = DetectorCandidateDiagnostics(
                    bounds=contour_bounds,
                    component_area=component_area,
                    corners=candidate_corners,
                    rejection_reason="candidate_side_too_small",
                )
                best_rejected, best_rejected_rank = self._consider_rejected_candidate(
                    diagnostics,
                    rank=(3, component_area),
                    current=best_rejected,
                    current_rank=best_rejected_rank,
                )
                continue
            rect_area = float(rect_width * rect_height)
            if rect_area <= 0.0:
                diagnostics = DetectorCandidateDiagnostics(
                    bounds=contour_bounds,
                    component_area=component_area,
                    corners=candidate_corners,
                    rejection_reason="candidate_rect_area_non_positive",
                )
                best_rejected, best_rejected_rank = self._consider_rejected_candidate(
                    diagnostics,
                    rank=(3, component_area),
                    current=best_rejected,
                    current_rank=best_rejected_rank,
                )
                continue
            fill_ratio = component_area / rect_area
            if fill_ratio < MIN_REGION_FILL_RATIO:
                diagnostics = DetectorCandidateDiagnostics(
                    bounds=contour_bounds,
                    component_area=component_area,
                    corners=candidate_corners,
                    rect_area=rect_area,
                    fill_ratio=fill_ratio,
                    rejection_reason="fill_ratio_too_low",
                )
                best_rejected, best_rejected_rank = self._consider_rejected_candidate(
                    diagnostics,
                    rank=(4, fill_ratio),
                    current=best_rejected,
                    current_rank=best_rejected_rank,
                )
                continue

            refined, border_metrics = self._refine_region_rectangle(
                gray=blurred,
                gradient=gradient,
                contour=contour,
                corners=candidate_corners,
            )
            if not self._corners_within_margin(
                refined,
                width=width,
                height=height,
                margin_ratio=MAX_DETECTION_MARGIN_RATIO,
            ):
                diagnostics = DetectorCandidateDiagnostics(
                    bounds=contour_bounds,
                    component_area=component_area,
                    corners=refined,
                    rect_area=rect_area,
                    fill_ratio=fill_ratio,
                    edge_support_score=border_metrics["mean_border_support"],
                    top_score=border_metrics["top_score"],
                    right_score=border_metrics["right_score"],
                    bottom_score=border_metrics["bottom_score"],
                    left_score=border_metrics["left_score"],
                    mean_border_support=border_metrics["mean_border_support"],
                    max_outward_expansion_px=border_metrics["max_outward_expansion_px"],
                    refined_area_ratio=border_metrics["refined_area_ratio"],
                    rejection_reason="corners_outside_margin",
                )
                best_rejected, best_rejected_rank = self._consider_rejected_candidate(
                    diagnostics,
                    rank=(5, border_metrics["mean_border_support"]),
                    current=best_rejected,
                    current_rank=best_rejected_rank,
                )
                continue
            area = abs(cv2.contourArea(refined.astype(np.float32)))
            if area < minimum_area:
                diagnostics = DetectorCandidateDiagnostics(
                    bounds=contour_bounds,
                    component_area=component_area,
                    corners=refined,
                    rect_area=rect_area,
                    fill_ratio=fill_ratio,
                    edge_support_score=border_metrics["mean_border_support"],
                    top_score=border_metrics["top_score"],
                    right_score=border_metrics["right_score"],
                    bottom_score=border_metrics["bottom_score"],
                    left_score=border_metrics["left_score"],
                    mean_border_support=border_metrics["mean_border_support"],
                    max_outward_expansion_px=border_metrics["max_outward_expansion_px"],
                    refined_area_ratio=border_metrics["refined_area_ratio"],
                    rejection_reason="candidate_area_below_minimum",
                )
                best_rejected, best_rejected_rank = self._consider_rejected_candidate(
                    diagnostics,
                    rank=(6, area),
                    current=best_rejected,
                    current_rank=best_rejected_rank,
                )
                continue
            side_scores = [
                ("weak_top_border", border_metrics["top_score"]),
                ("weak_right_border", border_metrics["right_score"]),
                ("weak_bottom_border", border_metrics["bottom_score"]),
                ("weak_left_border", border_metrics["left_score"]),
            ]
            weak_side_reason = next(
                (reason for reason, score in side_scores if score < REGION_MIN_SIDE_SCORE),
                None,
            )
            if weak_side_reason is not None:
                diagnostics = DetectorCandidateDiagnostics(
                    bounds=contour_bounds,
                    component_area=component_area,
                    corners=refined,
                    rect_area=rect_area,
                    fill_ratio=fill_ratio,
                    edge_support_score=border_metrics["mean_border_support"],
                    top_score=border_metrics["top_score"],
                    right_score=border_metrics["right_score"],
                    bottom_score=border_metrics["bottom_score"],
                    left_score=border_metrics["left_score"],
                    mean_border_support=border_metrics["mean_border_support"],
                    max_outward_expansion_px=border_metrics["max_outward_expansion_px"],
                    refined_area_ratio=border_metrics["refined_area_ratio"],
                    rejection_reason=weak_side_reason,
                )
                best_rejected, best_rejected_rank = self._consider_rejected_candidate(
                    diagnostics,
                    rank=(7, border_metrics["mean_border_support"]),
                    current=best_rejected,
                    current_rank=best_rejected_rank,
                )
                continue
            if border_metrics["mean_border_support"] < REGION_MIN_MEAN_BORDER_SUPPORT:
                diagnostics = DetectorCandidateDiagnostics(
                    bounds=contour_bounds,
                    component_area=component_area,
                    corners=refined,
                    rect_area=rect_area,
                    fill_ratio=fill_ratio,
                    edge_support_score=border_metrics["mean_border_support"],
                    top_score=border_metrics["top_score"],
                    right_score=border_metrics["right_score"],
                    bottom_score=border_metrics["bottom_score"],
                    left_score=border_metrics["left_score"],
                    mean_border_support=border_metrics["mean_border_support"],
                    max_outward_expansion_px=border_metrics["max_outward_expansion_px"],
                    refined_area_ratio=border_metrics["refined_area_ratio"],
                    rejection_reason="mean_border_support_too_low",
                )
                best_rejected, best_rejected_rank = self._consider_rejected_candidate(
                    diagnostics,
                    rank=(8, border_metrics["mean_border_support"]),
                    current=best_rejected,
                    current_rank=best_rejected_rank,
                )
                continue
            if border_metrics["outward_side_count"] >= 2:
                diagnostics = DetectorCandidateDiagnostics(
                    bounds=contour_bounds,
                    component_area=component_area,
                    corners=refined,
                    rect_area=rect_area,
                    fill_ratio=fill_ratio,
                    edge_support_score=border_metrics["mean_border_support"],
                    top_score=border_metrics["top_score"],
                    right_score=border_metrics["right_score"],
                    bottom_score=border_metrics["bottom_score"],
                    left_score=border_metrics["left_score"],
                    mean_border_support=border_metrics["mean_border_support"],
                    max_outward_expansion_px=border_metrics["max_outward_expansion_px"],
                    refined_area_ratio=border_metrics["refined_area_ratio"],
                    rejection_reason="excessive_outward_expansion",
                )
                best_rejected, best_rejected_rank = self._consider_rejected_candidate(
                    diagnostics,
                    rank=(9, 1.0 - min(1.0, border_metrics["max_outward_expansion_px"] / max(REGION_OUTWARD_EXPANSION_PX, 1.0))),
                    current=best_rejected,
                    current_rank=best_rejected_rank,
                )
                continue
            if border_metrics["refined_area_ratio"] > REGION_MAX_REFINED_AREA_RATIO:
                diagnostics = DetectorCandidateDiagnostics(
                    bounds=contour_bounds,
                    component_area=component_area,
                    corners=refined,
                    rect_area=rect_area,
                    fill_ratio=fill_ratio,
                    edge_support_score=border_metrics["mean_border_support"],
                    top_score=border_metrics["top_score"],
                    right_score=border_metrics["right_score"],
                    bottom_score=border_metrics["bottom_score"],
                    left_score=border_metrics["left_score"],
                    mean_border_support=border_metrics["mean_border_support"],
                    max_outward_expansion_px=border_metrics["max_outward_expansion_px"],
                    refined_area_ratio=border_metrics["refined_area_ratio"],
                    rejection_reason="refined_box_too_large_for_region",
                )
                best_rejected, best_rejected_rank = self._consider_rejected_candidate(
                    diagnostics,
                    rank=(10, 1.0 - min(1.0, border_metrics["refined_area_ratio"] / REGION_MAX_REFINED_AREA_RATIO)),
                    current=best_rejected,
                    current_rank=best_rejected_rank,
                )
                continue

            candidate_shape_aspect_ratio = self._shape_aspect_ratio(
                self._quadrilateral_aspect_ratio(refined),
            )
            occupancy_score = self._polygon_occupancy_score(bright_mask, refined)
            if occupancy_score < 0.58:
                diagnostics = DetectorCandidateDiagnostics(
                    bounds=contour_bounds,
                    component_area=component_area,
                    corners=refined,
                    rect_area=rect_area,
                    fill_ratio=fill_ratio,
                    occupancy_score=occupancy_score,
                    edge_support_score=border_metrics["mean_border_support"],
                    top_score=border_metrics["top_score"],
                    right_score=border_metrics["right_score"],
                    bottom_score=border_metrics["bottom_score"],
                    left_score=border_metrics["left_score"],
                    mean_border_support=border_metrics["mean_border_support"],
                    max_outward_expansion_px=border_metrics["max_outward_expansion_px"],
                    refined_area_ratio=border_metrics["refined_area_ratio"],
                    rejection_reason="occupancy_score_too_low",
                )
                best_rejected, best_rejected_rank = self._consider_rejected_candidate(
                    diagnostics,
                    rank=(11, occupancy_score),
                    current=best_rejected,
                    current_rank=best_rejected_rank,
                )
                continue
            aspect_log_error = self._aspect_log_error(
                candidate_shape_aspect_ratio,
                expected_shape_aspect_ratio,
            )
            if aspect_log_error > MAX_ASPECT_LOG_ERROR:
                diagnostics = DetectorCandidateDiagnostics(
                    bounds=contour_bounds,
                    component_area=component_area,
                    corners=refined,
                    rect_area=rect_area,
                    fill_ratio=fill_ratio,
                    occupancy_score=occupancy_score,
                    edge_support_score=border_metrics["mean_border_support"],
                    top_score=border_metrics["top_score"],
                    right_score=border_metrics["right_score"],
                    bottom_score=border_metrics["bottom_score"],
                    left_score=border_metrics["left_score"],
                    mean_border_support=border_metrics["mean_border_support"],
                    max_outward_expansion_px=border_metrics["max_outward_expansion_px"],
                    refined_area_ratio=border_metrics["refined_area_ratio"],
                    aspect_log_error=aspect_log_error,
                    rejection_reason="aspect_ratio_out_of_range",
                )
                best_rejected, best_rejected_rank = self._consider_rejected_candidate(
                    diagnostics,
                    rank=(12, 1.0 - min(1.0, aspect_log_error / MAX_ASPECT_LOG_ERROR)),
                    current=best_rejected,
                    current_rank=best_rejected_rank,
                )
                continue

            score = self._score_region_candidate(
                luma=blurred,
                bright_mask=bright_mask,
                contour_mask=contour_mask,
                corners=refined,
                component_area=component_area,
                rect_area=rect_area,
                image_area=image_area,
                expected_shape_aspect_ratio=expected_shape_aspect_ratio,
                edge_support_score=border_metrics["mean_border_support"],
                occupancy_score=occupancy_score,
            )
            if score > best_score:
                best_score = score
                best_candidate = DetectionCandidate(
                    corners=refined,
                    confidence=float(score),
                    method="paper_region_v2",
                )
                best_rejected = DetectorCandidateDiagnostics(
                    bounds=contour_bounds,
                    component_area=component_area,
                    corners=refined,
                    rect_area=rect_area,
                    fill_ratio=fill_ratio,
                    occupancy_score=occupancy_score,
                    edge_support_score=border_metrics["mean_border_support"],
                    top_score=border_metrics["top_score"],
                    right_score=border_metrics["right_score"],
                    bottom_score=border_metrics["bottom_score"],
                    left_score=border_metrics["left_score"],
                    mean_border_support=border_metrics["mean_border_support"],
                    max_outward_expansion_px=border_metrics["max_outward_expansion_px"],
                    refined_area_ratio=border_metrics["refined_area_ratio"],
                    aspect_log_error=aspect_log_error,
                    score=score,
                    confidence=score,
                )
                best_rejected_rank = (13, score)

        if best_candidate is not None:
            return best_candidate, DetectorRunDiagnostics(
                status="used",
                candidate_count=candidate_count,
                best_candidate=best_rejected,
            )
        return None, DetectorRunDiagnostics(
            status="rejected" if candidate_count > 0 else "unavailable",
            rejection_reason=(
                best_rejected.rejection_reason
                if best_rejected is not None and best_rejected.rejection_reason is not None
                else ("no_region_candidate_survived_scoring" if candidate_count > 0 else "no_plausible_region_candidate")
            ),
            candidate_count=candidate_count,
            best_candidate=best_rejected,
        )

    def _detect_contour_quad(
        self,
        image: np.ndarray,
        *,
        image_area: float,
        expected_shape_aspect_ratio: float,
    ) -> tuple[Optional[DetectionCandidate], DetectorRunDiagnostics]:
        normalized_gray = self._illumination_normalized_gray(image)
        blurred = cv2.GaussianBlur(normalized_gray, (5, 5), 0)
        gradient = self._gradient_magnitude(blurred)
        edges = cv2.Canny(blurred, 40, 120)
        edges = cv2.morphologyEx(
            edges,
            cv2.MORPH_CLOSE,
            np.ones((5, 5), dtype=np.uint8),
            iterations=1,
        )
        edges = cv2.dilate(edges, np.ones((3, 3), dtype=np.uint8), iterations=1)
        contours, _ = cv2.findContours(
            edges,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        if not contours:
            return None, DetectorRunDiagnostics(
                status="unavailable",
                rejection_reason="no_contour_edges",
                candidate_count=0,
            )

        minimum_area = image_area * MIN_QUAD_AREA_RATIO
        best_candidate: Optional[DetectionCandidate] = None
        best_score = -1.0
        best_rejected: Optional[DetectorCandidateDiagnostics] = None
        best_rejected_rank: tuple[int, float] = (-1, -1.0)
        candidate_count = 0
        height, width = image.shape[:2]
        for contour in contours:
            hull = cv2.convexHull(contour)
            contour_bounds = cv2.boundingRect(hull)
            diagnostics = DetectorCandidateDiagnostics(bounds=contour_bounds)
            if self._touches_too_many_borders(
                contour_bounds,
                width=width,
                height=height,
            ):
                diagnostics = DetectorCandidateDiagnostics(
                    bounds=contour_bounds,
                    rejection_reason="touches_too_many_borders",
                )
                best_rejected, best_rejected_rank = self._consider_rejected_candidate(
                    diagnostics,
                    rank=(0, 0.0),
                    current=best_rejected,
                    current_rank=best_rejected_rank,
                )
                continue

            component_area = float(abs(cv2.contourArea(hull.astype(np.float32))))
            diagnostics = DetectorCandidateDiagnostics(
                bounds=contour_bounds,
                component_area=component_area,
            )
            if component_area < minimum_area:
                diagnostics = DetectorCandidateDiagnostics(
                    bounds=contour_bounds,
                    component_area=component_area,
                    rejection_reason="component_area_below_minimum",
                )
                best_rejected, best_rejected_rank = self._consider_rejected_candidate(
                    diagnostics,
                    rank=(1, component_area),
                    current=best_rejected,
                    current_rank=best_rejected_rank,
                )
                continue
            candidate_count += 1

            candidate_corners = self._fit_region_candidate_corners(hull)
            rect_width = float(np.linalg.norm(candidate_corners[1] - candidate_corners[0]))
            rect_height = float(np.linalg.norm(candidate_corners[3] - candidate_corners[0]))
            if rect_width <= 2.0 or rect_height <= 2.0:
                diagnostics = DetectorCandidateDiagnostics(
                    bounds=contour_bounds,
                    component_area=component_area,
                    corners=candidate_corners,
                    rejection_reason="candidate_side_too_small",
                )
                best_rejected, best_rejected_rank = self._consider_rejected_candidate(
                    diagnostics,
                    rank=(2, component_area),
                    current=best_rejected,
                    current_rank=best_rejected_rank,
                )
                continue
            rect_area = float(rect_width * rect_height)
            fill_ratio = component_area / max(rect_area, 1.0)
            if fill_ratio < 0.52:
                diagnostics = DetectorCandidateDiagnostics(
                    bounds=contour_bounds,
                    component_area=component_area,
                    corners=candidate_corners,
                    rect_area=rect_area,
                    fill_ratio=fill_ratio,
                    rejection_reason="fill_ratio_too_low",
                )
                best_rejected, best_rejected_rank = self._consider_rejected_candidate(
                    diagnostics,
                    rank=(3, fill_ratio),
                    current=best_rejected,
                    current_rank=best_rejected_rank,
                )
                continue

            refined, border_metrics = self._refine_region_rectangle(
                gray=blurred,
                gradient=gradient,
                contour=hull,
                corners=candidate_corners,
            )
            diagnostics_common = dict(
                bounds=contour_bounds,
                component_area=component_area,
                corners=refined,
                rect_area=rect_area,
                fill_ratio=fill_ratio,
                edge_support_score=border_metrics["mean_border_support"],
                top_score=border_metrics["top_score"],
                right_score=border_metrics["right_score"],
                bottom_score=border_metrics["bottom_score"],
                left_score=border_metrics["left_score"],
                mean_border_support=border_metrics["mean_border_support"],
                max_outward_expansion_px=border_metrics["max_outward_expansion_px"],
                refined_area_ratio=border_metrics["refined_area_ratio"],
            )
            if not self._corners_within_margin(
                refined,
                width=width,
                height=height,
                margin_ratio=MAX_DETECTION_MARGIN_RATIO,
            ):
                diagnostics = DetectorCandidateDiagnostics(
                    **diagnostics_common,
                    rejection_reason="corners_outside_margin",
                )
                best_rejected, best_rejected_rank = self._consider_rejected_candidate(
                    diagnostics,
                    rank=(4, border_metrics["mean_border_support"]),
                    current=best_rejected,
                    current_rank=best_rejected_rank,
                )
                continue

            area = abs(cv2.contourArea(refined.astype(np.float32)))
            if area < minimum_area:
                diagnostics = DetectorCandidateDiagnostics(
                    **diagnostics_common,
                    rejection_reason="candidate_area_below_minimum",
                )
                best_rejected, best_rejected_rank = self._consider_rejected_candidate(
                    diagnostics,
                    rank=(5, area),
                    current=best_rejected,
                    current_rank=best_rejected_rank,
                )
                continue

            side_scores = [
                ("weak_top_border", border_metrics["top_score"]),
                ("weak_right_border", border_metrics["right_score"]),
                ("weak_bottom_border", border_metrics["bottom_score"]),
                ("weak_left_border", border_metrics["left_score"]),
            ]
            weak_side_reason = next(
                (reason for reason, score in side_scores if score < REGION_MIN_SIDE_SCORE),
                None,
            )
            if weak_side_reason is not None:
                diagnostics = DetectorCandidateDiagnostics(
                    **diagnostics_common,
                    rejection_reason=weak_side_reason,
                )
                best_rejected, best_rejected_rank = self._consider_rejected_candidate(
                    diagnostics,
                    rank=(6, border_metrics["mean_border_support"]),
                    current=best_rejected,
                    current_rank=best_rejected_rank,
                )
                continue
            if border_metrics["mean_border_support"] < REGION_MIN_MEAN_BORDER_SUPPORT:
                diagnostics = DetectorCandidateDiagnostics(
                    **diagnostics_common,
                    rejection_reason="mean_border_support_too_low",
                )
                best_rejected, best_rejected_rank = self._consider_rejected_candidate(
                    diagnostics,
                    rank=(7, border_metrics["mean_border_support"]),
                    current=best_rejected,
                    current_rank=best_rejected_rank,
                )
                continue

            candidate_shape_aspect_ratio = self._shape_aspect_ratio(
                self._quadrilateral_aspect_ratio(refined),
            )
            aspect_log_error = self._aspect_log_error(
                candidate_shape_aspect_ratio,
                expected_shape_aspect_ratio,
            )
            if aspect_log_error > MAX_ASPECT_LOG_ERROR:
                diagnostics = DetectorCandidateDiagnostics(
                    **diagnostics_common,
                    aspect_log_error=aspect_log_error,
                    rejection_reason="aspect_ratio_out_of_range",
                )
                best_rejected, best_rejected_rank = self._consider_rejected_candidate(
                    diagnostics,
                    rank=(8, 1.0 - min(1.0, aspect_log_error / MAX_ASPECT_LOG_ERROR)),
                    current=best_rejected,
                    current_rank=best_rejected_rank,
                )
                continue

            score = self._score_contour_candidate(
                corners=refined,
                component_area=component_area,
                rect_area=rect_area,
                image_area=image_area,
                expected_shape_aspect_ratio=expected_shape_aspect_ratio,
                border_support_score=border_metrics["mean_border_support"],
                fill_ratio=fill_ratio,
            )
            if score > best_score:
                best_score = score
                best_candidate = DetectionCandidate(
                    corners=refined,
                    confidence=float(score),
                    method="paper_contour_v3",
                )
                best_rejected = DetectorCandidateDiagnostics(
                    **diagnostics_common,
                    aspect_log_error=aspect_log_error,
                    score=score,
                    confidence=score,
                )
                best_rejected_rank = (9, score)

        if best_candidate is not None:
            return best_candidate, DetectorRunDiagnostics(
                status="used",
                candidate_count=candidate_count,
                best_candidate=best_rejected,
            )
        return None, DetectorRunDiagnostics(
            status="rejected" if candidate_count > 0 else "unavailable",
            rejection_reason=(
                best_rejected.rejection_reason
                if best_rejected is not None and best_rejected.rejection_reason is not None
                else ("no_contour_candidate_survived_scoring" if candidate_count > 0 else "no_plausible_contour_candidate")
            ),
            candidate_count=candidate_count,
            best_candidate=best_rejected,
        )

    def _detect_line_quad(
        self,
        image: np.ndarray,
        *,
        image_area: float,
        expected_shape_aspect_ratio: float,
    ) -> tuple[Optional[DetectionCandidate], DetectorRunDiagnostics]:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        min_line_length = int(round(max(image.shape[0], image.shape[1]) * 0.12))
        lines = cv2.HoughLinesP(
            edges,
            1,
            np.pi / 180,
            threshold=90,
            minLineLength=max(60, min_line_length),
            maxLineGap=30,
        )
        if lines is None:
            return None, DetectorRunDiagnostics(
                status="unavailable",
                rejection_reason="no_hough_lines",
                candidate_count=0,
            )

        parsed_lines = [self._build_line_candidate(line[0]) for line in lines]
        height, width = image.shape[:2]
        left = self._select_vertical_line(
            parsed_lines,
            width=width,
            band_min=0.05,
            band_max=0.55,
            prefer_right=False,
        )
        right = self._select_vertical_line(
            parsed_lines,
            width=width,
            band_min=0.45,
            band_max=0.9,
            prefer_right=True,
        )
        if left is None or right is None:
            return None, DetectorRunDiagnostics(
                status="rejected",
                rejection_reason="missing_vertical_edges",
                candidate_count=len(parsed_lines),
            )
        bottom = self._select_horizontal_line(
            parsed_lines,
            gray=gray,
            width=width,
            height=height,
            band_min=0.55,
            band_max=0.98,
            prefer_lower=True,
            expect_below_brighter=False,
        )
        if bottom is None:
            return None, DetectorRunDiagnostics(
                status="rejected",
                rejection_reason="missing_bottom_edge",
                candidate_count=len(parsed_lines),
            )
        top = self._select_top_line(
            parsed_lines,
            gray=gray,
            width=width,
            height=height,
            image_area=image_area,
            expected_shape_aspect_ratio=expected_shape_aspect_ratio,
            left=left,
            right=right,
            bottom=bottom,
        )
        if top is None:
            return None, DetectorRunDiagnostics(
                status="rejected",
                rejection_reason="missing_top_edge",
                candidate_count=len(parsed_lines),
            )

        corners = np.array(
            [
                self._line_intersection(top.points, left.points),
                self._line_intersection(top.points, right.points),
                self._line_intersection(bottom.points, right.points),
                self._line_intersection(bottom.points, left.points),
            ],
            dtype=np.float32,
        )
        if np.isnan(corners).any():
            return None, DetectorRunDiagnostics(
                status="rejected",
                rejection_reason="line_intersections_invalid",
                candidate_count=len(parsed_lines),
            )
        ordered = self._order_corners(corners)
        area = abs(cv2.contourArea(ordered.astype(np.float32)))
        if area < image_area * MIN_QUAD_AREA_RATIO:
            return None, DetectorRunDiagnostics(
                status="rejected",
                rejection_reason="line_quad_area_below_minimum",
                candidate_count=len(parsed_lines),
                best_candidate=DetectorCandidateDiagnostics(
                    corners=ordered,
                ),
            )

        margin = 0.08 * max(height, width)
        min_x = float(np.min(ordered[:, 0]))
        max_x = float(np.max(ordered[:, 0]))
        min_y = float(np.min(ordered[:, 1]))
        max_y = float(np.max(ordered[:, 1]))
        if min_x < -margin or min_y < -margin or max_x > (width - 1 + margin) or max_y > (height - 1 + margin):
            return None, DetectorRunDiagnostics(
                status="rejected",
                rejection_reason="line_quad_outside_margin",
                candidate_count=len(parsed_lines),
                best_candidate=DetectorCandidateDiagnostics(
                    corners=ordered,
                ),
            )

        line_strength = (
            top.length + bottom.length + left.length + right.length
        ) / (2.0 * (width + height))
        geometry_score = self._score_quadrilateral(
            ordered,
            area=area,
            image_area=image_area,
            expected_shape_aspect_ratio=expected_shape_aspect_ratio,
        )
        confidence = (min(1.0, line_strength) * 0.45) + (geometry_score * 0.55)
        candidate = DetectionCandidate(
            corners=ordered,
            confidence=float(confidence),
            method="paper_edges_v1",
        )
        return candidate, DetectorRunDiagnostics(
            status="used",
            candidate_count=len(parsed_lines),
            best_candidate=DetectorCandidateDiagnostics(
                corners=ordered,
                confidence=confidence,
                score=confidence,
            ),
        )

    def _downscale_for_detection(self, image: np.ndarray) -> tuple[np.ndarray, float]:
        height, width = image.shape[:2]
        longest_side = max(height, width)
        if longest_side <= MAX_DETECTION_DIMENSION_PX:
            return image.copy(), 1.0
        scale = MAX_DETECTION_DIMENSION_PX / float(longest_side)
        resized = cv2.resize(
            image,
            (
                max(1, int(round(width * scale))),
                max(1, int(round(height * scale))),
            ),
            interpolation=cv2.INTER_AREA,
        )
        return resized, scale

    def _score_quadrilateral(
        self,
        corners: np.ndarray,
        *,
        area: float,
        image_area: float,
        expected_shape_aspect_ratio: float,
    ) -> float:
        ordered = self._order_corners(corners)
        side_lengths = [
            float(np.linalg.norm(ordered[1] - ordered[0])),
            float(np.linalg.norm(ordered[2] - ordered[1])),
            float(np.linalg.norm(ordered[3] - ordered[2])),
            float(np.linalg.norm(ordered[0] - ordered[3])),
        ]
        if min(side_lengths) <= 0:
            return 0.0
        angle_penalty = 0.0
        for index in range(4):
            previous = ordered[index - 1] - ordered[index]
            following = ordered[(index + 1) % 4] - ordered[index]
            cosine = abs(
                np.dot(previous, following)
                / (np.linalg.norm(previous) * np.linalg.norm(following))
            )
            angle_penalty += cosine
        angle_score = max(0.0, 1.0 - (angle_penalty / 4.0))
        area_score = min(1.0, area / image_area)
        side_balance = min(side_lengths) / max(side_lengths)
        candidate_aspect_ratio = self._shape_aspect_ratio(
            self._quadrilateral_aspect_ratio(ordered),
        )
        aspect_score = self._aspect_score(
            candidate_aspect_ratio,
            expected_shape_aspect_ratio,
        )
        score = (
            (area_score * 0.35)
            + (angle_score * 0.25)
            + (side_balance * 0.15)
            + (aspect_score * 0.25)
        )
        return float(score)

    def _score_region_candidate(
        self,
        *,
        luma: np.ndarray,
        bright_mask: np.ndarray,
        contour_mask: np.ndarray,
        corners: np.ndarray,
        component_area: float,
        rect_area: float,
        image_area: float,
        expected_shape_aspect_ratio: float,
        edge_support_score: float,
        occupancy_score: float,
    ) -> float:
        inside_values = luma[contour_mask > 0]
        if inside_values.size == 0:
            return 0.0

        band_kernel = np.ones((15, 15), dtype=np.uint8)
        outer_ring_mask = cv2.dilate(contour_mask, band_kernel, iterations=1)
        outer_ring_mask = cv2.subtract(outer_ring_mask, contour_mask)
        outer_values = luma[outer_ring_mask > 0]

        area_score = min(1.0, component_area / max(1.0, image_area * 0.45))
        candidate_aspect_ratio = self._shape_aspect_ratio(
            self._quadrilateral_aspect_ratio(corners),
        )
        aspect_score = self._aspect_score(
            candidate_aspect_ratio,
            expected_shape_aspect_ratio,
        )
        rectangularity_score = max(
            0.0,
            min(1.0, (component_area / max(rect_area, 1.0) - 0.55) / 0.45),
        )
        rectangularity_score *= occupancy_score
        inside_mean = float(np.mean(inside_values))
        inside_std = float(np.std(inside_values))
        brightness_score = max(0.0, min(1.0, (inside_mean - BRIGHT_REGION_FLOOR_LUMA) / 80.0))
        variance_score = max(0.0, min(1.0, 1.0 - (inside_std / 38.0)))
        interior_uniformity_score = (brightness_score * 0.35) + (variance_score * 0.65)
        if outer_values.size > 0:
            contrast_score = max(
                0.0,
                min(1.0, ((inside_mean - float(np.mean(outer_values))) + 10.0) / 55.0),
            )
        else:
            contrast_score = brightness_score
        return float(
            (aspect_score * 0.2)
            + (rectangularity_score * 0.15)
            + (edge_support_score * 0.35)
            + (contrast_score * 0.1)
            + (area_score * 0.05)
            + (interior_uniformity_score * 0.05)
            + (occupancy_score * 0.1)
        )

    def _score_contour_candidate(
        self,
        *,
        corners: np.ndarray,
        component_area: float,
        rect_area: float,
        image_area: float,
        expected_shape_aspect_ratio: float,
        border_support_score: float,
        fill_ratio: float,
    ) -> float:
        candidate_aspect_ratio = self._shape_aspect_ratio(
            self._quadrilateral_aspect_ratio(corners),
        )
        aspect_score = self._aspect_score(
            candidate_aspect_ratio,
            expected_shape_aspect_ratio,
        )
        area_score = min(1.0, component_area / max(1.0, image_area * 0.45))
        rectangularity_score = max(
            0.0,
            min(1.0, (fill_ratio - 0.5) / 0.45),
        )
        geometry_score = self._score_quadrilateral(
            corners,
            area=abs(cv2.contourArea(corners.astype(np.float32))),
            image_area=image_area,
            expected_shape_aspect_ratio=expected_shape_aspect_ratio,
        )
        return float(
            (aspect_score * 0.3)
            + (border_support_score * 0.4)
            + (rectangularity_score * 0.15)
            + (geometry_score * 0.1)
            + (area_score * 0.05)
        )

    def _consider_rejected_candidate(
        self,
        diagnostics: DetectorCandidateDiagnostics,
        *,
        rank: tuple[int, float],
        current: Optional[DetectorCandidateDiagnostics],
        current_rank: tuple[int, float],
    ) -> tuple[Optional[DetectorCandidateDiagnostics], tuple[int, float]]:
        if rank > current_rank:
            return diagnostics, rank
        return current, current_rank

    def _to_method_diagnostics(
        self,
        diagnostics: DetectorRunDiagnostics,
        *,
        status: Literal["used", "rejected", "not_run", "unavailable"],
    ) -> NormalizationMethodDiagnostics:
        return NormalizationMethodDiagnostics(
            status=status,
            rejection_reason=diagnostics.rejection_reason,
            candidate_count=diagnostics.candidate_count,
            best_candidate=self._to_diagnostic_candidate(diagnostics.best_candidate),
        )

    def _to_diagnostic_candidate(
        self,
        candidate: Optional[DetectorCandidateDiagnostics],
    ) -> Optional[NormalizationDiagnosticCandidate]:
        if candidate is None:
            return None
        return NormalizationDiagnosticCandidate(
            corners=self._to_corners(candidate.corners) if candidate.corners is not None else None,
            bounds=(
                tuple(int(value) for value in candidate.bounds)
                if candidate.bounds is not None
                else None
            ),
            component_area=(
                float(round(candidate.component_area, 6))
                if candidate.component_area is not None
                else None
            ),
            rect_area=(
                float(round(candidate.rect_area, 6))
                if candidate.rect_area is not None
                else None
            ),
            fill_ratio=(
                float(round(candidate.fill_ratio, 6))
                if candidate.fill_ratio is not None
                else None
            ),
            occupancy_score=(
                float(round(candidate.occupancy_score, 6))
                if candidate.occupancy_score is not None
                else None
            ),
            edge_support_score=(
                float(round(candidate.edge_support_score, 6))
                if candidate.edge_support_score is not None
                else None
            ),
            top_score=(
                float(round(candidate.top_score, 6))
                if candidate.top_score is not None
                else None
            ),
            right_score=(
                float(round(candidate.right_score, 6))
                if candidate.right_score is not None
                else None
            ),
            bottom_score=(
                float(round(candidate.bottom_score, 6))
                if candidate.bottom_score is not None
                else None
            ),
            left_score=(
                float(round(candidate.left_score, 6))
                if candidate.left_score is not None
                else None
            ),
            mean_border_support=(
                float(round(candidate.mean_border_support, 6))
                if candidate.mean_border_support is not None
                else None
            ),
            max_outward_expansion_px=(
                float(round(candidate.max_outward_expansion_px, 6))
                if candidate.max_outward_expansion_px is not None
                else None
            ),
            refined_area_ratio=(
                float(round(candidate.refined_area_ratio, 6))
                if candidate.refined_area_ratio is not None
                else None
            ),
            aspect_log_error=(
                float(round(candidate.aspect_log_error, 6))
                if candidate.aspect_log_error is not None
                else None
            ),
            score=(
                float(round(candidate.score, 6))
                if candidate.score is not None
                else None
            ),
            confidence=(
                float(round(candidate.confidence, 6))
                if candidate.confidence is not None
                else None
            ),
            rejection_reason=candidate.rejection_reason,
        )

    def _refine_region_rectangle(
        self,
        gray: np.ndarray,
        gradient: np.ndarray,
        contour: np.ndarray,
        corners: np.ndarray,
    ) -> tuple[np.ndarray, dict[str, float]]:
        ordered = self._order_corners(corners)
        width_vector = ordered[1] - ordered[0]
        height_vector = ordered[3] - ordered[0]
        width_length = float(np.linalg.norm(width_vector))
        height_length = float(np.linalg.norm(height_vector))
        if width_length <= 1.0 or height_length <= 1.0:
            return ordered, {
                "top_score": 0.0,
                "right_score": 0.0,
                "bottom_score": 0.0,
                "left_score": 0.0,
                "mean_border_support": 0.0,
                "max_outward_expansion_px": 0.0,
                "outward_side_count": 0.0,
                "refined_area_ratio": 1.0,
            }

        center = np.mean(ordered, axis=0).astype(np.float32)
        u = width_vector / width_length
        v = height_vector / height_length
        contour_points = contour.reshape(-1, 2).astype(np.float32)
        relative_points = contour_points - center
        width_projections = relative_points @ u
        height_projections = relative_points @ v

        left_anchor = float(np.percentile(width_projections, SNAP_BOX_QUANTILE))
        right_anchor = float(np.percentile(width_projections, 100.0 - SNAP_BOX_QUANTILE))
        top_anchor = float(np.percentile(height_projections, SNAP_BOX_QUANTILE))
        bottom_anchor = float(np.percentile(height_projections, 100.0 - SNAP_BOX_QUANTILE))
        anchor_width = max(1.0, right_anchor - left_anchor)
        anchor_height = max(1.0, bottom_anchor - top_anchor)
        anchor_area = anchor_width * anchor_height

        top_pos, top_metrics = self._snap_region_edge_position(
            gray=gray,
            gradient=gradient,
            center=center,
            u=u,
            v=v,
            contour_points=contour_points,
            contour_parallel=width_projections,
            contour_orthogonal=height_projections,
            fixed_axis="horizontal",
            anchor_position=top_anchor,
            span=anchor_width / 2.0,
            min_delta=-REGION_OUTWARD_EXPANSION_PX,
            max_delta=REGION_INWARD_EXPANSION_PX,
            inward_sign=1.0,
        )
        bottom_pos, bottom_metrics = self._snap_region_edge_position(
            gray=gray,
            gradient=gradient,
            center=center,
            u=u,
            v=v,
            contour_points=contour_points,
            contour_parallel=width_projections,
            contour_orthogonal=height_projections,
            fixed_axis="horizontal",
            anchor_position=bottom_anchor,
            span=anchor_width / 2.0,
            min_delta=-REGION_INWARD_EXPANSION_PX,
            max_delta=REGION_OUTWARD_EXPANSION_PX,
            inward_sign=-1.0,
        )
        left_pos, left_metrics = self._snap_region_edge_position(
            gray=gray,
            gradient=gradient,
            center=center,
            u=u,
            v=v,
            contour_points=contour_points,
            contour_parallel=height_projections,
            contour_orthogonal=width_projections,
            fixed_axis="vertical",
            anchor_position=left_anchor,
            span=anchor_height / 2.0,
            min_delta=-REGION_OUTWARD_EXPANSION_PX,
            max_delta=REGION_INWARD_EXPANSION_PX,
            inward_sign=1.0,
        )
        right_pos, right_metrics = self._snap_region_edge_position(
            gray=gray,
            gradient=gradient,
            center=center,
            u=u,
            v=v,
            contour_points=contour_points,
            contour_parallel=height_projections,
            contour_orthogonal=width_projections,
            fixed_axis="vertical",
            anchor_position=right_anchor,
            span=anchor_height / 2.0,
            min_delta=-REGION_INWARD_EXPANSION_PX,
            max_delta=REGION_OUTWARD_EXPANSION_PX,
            inward_sign=-1.0,
        )

        snapped_area = max(1.0, (right_pos - left_pos) * (bottom_pos - top_pos))
        refined_area_ratio = float(snapped_area / max(anchor_area, 1.0))
        outward_expansions = [
            max(0.0, top_anchor - top_pos),
            max(0.0, right_pos - right_anchor),
            max(0.0, bottom_pos - bottom_anchor),
            max(0.0, left_anchor - left_pos),
        ]
        outward_side_count = float(
            sum(
                1
                for expansion in outward_expansions
                if expansion > REGION_ALLOWED_OUTWARD_EXPANSION_PX
            )
        )
        max_outward_expansion_px = float(max(outward_expansions))
        mean_border_support = float(
            np.mean(
                [
                    top_metrics["score"],
                    right_metrics["score"],
                    bottom_metrics["score"],
                    left_metrics["score"],
                ]
            )
        )

        inset = min(
            REGION_FINAL_INSET_PX,
            max(1.0, min(right_pos - left_pos, bottom_pos - top_pos) * 0.005),
        )
        top_pos += inset
        bottom_pos -= inset
        left_pos += inset
        right_pos -= inset

        refined = np.array(
            [
                center + (left_pos * u) + (top_pos * v),
                center + (right_pos * u) + (top_pos * v),
                center + (right_pos * u) + (bottom_pos * v),
                center + (left_pos * u) + (bottom_pos * v),
            ],
            dtype=np.float32,
        )
        return self._order_corners(refined), {
            "top_score": top_metrics["score"],
            "right_score": right_metrics["score"],
            "bottom_score": bottom_metrics["score"],
            "left_score": left_metrics["score"],
            "mean_border_support": max(0.0, min(1.0, mean_border_support)),
            "max_outward_expansion_px": max_outward_expansion_px,
            "outward_side_count": outward_side_count,
            "refined_area_ratio": refined_area_ratio,
        }

    def _fit_region_candidate_corners(self, contour: np.ndarray) -> np.ndarray:
        rect = cv2.minAreaRect(contour)
        base = self._order_corners(cv2.boxPoints(rect).astype(np.float32))
        width_vector = base[1] - base[0]
        height_vector = base[3] - base[0]
        width_length = float(np.linalg.norm(width_vector))
        height_length = float(np.linalg.norm(height_vector))
        if width_length <= 1.0 or height_length <= 1.0:
            return base

        u = width_vector / width_length
        v = height_vector / height_length
        center = np.mean(base, axis=0).astype(np.float32)
        contour_points = contour.reshape(-1, 2).astype(np.float32)
        relative_points = contour_points - center
        width_projections = relative_points @ u
        height_projections = relative_points @ v

        left = float(np.percentile(width_projections, REGION_BOX_QUANTILE))
        right = float(np.percentile(width_projections, 100.0 - REGION_BOX_QUANTILE))
        top = float(np.percentile(height_projections, REGION_BOX_QUANTILE))
        bottom = float(np.percentile(height_projections, 100.0 - REGION_BOX_QUANTILE))
        clipped = np.array(
            [
                center + (left * u) + (top * v),
                center + (right * u) + (top * v),
                center + (right * u) + (bottom * v),
                center + (left * u) + (bottom * v),
            ],
            dtype=np.float32,
        )
        return self._order_corners(clipped)

    def _snap_region_edge_position(
        self,
        *,
        gray: np.ndarray,
        gradient: np.ndarray,
        center: np.ndarray,
        u: np.ndarray,
        v: np.ndarray,
        contour_points: np.ndarray,
        contour_parallel: np.ndarray,
        contour_orthogonal: np.ndarray,
        fixed_axis: Literal["horizontal", "vertical"],
        anchor_position: float,
        span: float,
        min_delta: float,
        max_delta: float,
        inward_sign: float,
    ) -> tuple[float, dict[str, float]]:
        best_position = anchor_position
        best_score = -1.0
        best_metrics = {
            "score": 0.0,
            "contour_coverage_score": 0.0,
            "border_contrast_score": 0.0,
            "gradient_score": 0.0,
        }
        for delta in np.linspace(min_delta, max_delta, 13):
            position = anchor_position + float(delta)
            metrics = self._sample_region_border_metrics(
                gray=gray,
                gradient=gradient,
                center=center,
                u=u,
                v=v,
                contour_points=contour_points,
                contour_parallel=contour_parallel,
                contour_orthogonal=contour_orthogonal,
                fixed_axis=fixed_axis,
                position=position,
                span=span,
                inward_sign=inward_sign,
            )
            score = metrics["score"] - (max(0.0, abs(float(delta)) - 2.0) / max(max_delta - min_delta, 1.0) * 0.03)
            if score > best_score:
                best_score = score
                best_position = position
                best_metrics = metrics
        return best_position, best_metrics

    def _sample_region_border_metrics(
        self,
        *,
        gray: np.ndarray,
        gradient: np.ndarray,
        center: np.ndarray,
        u: np.ndarray,
        v: np.ndarray,
        contour_points: np.ndarray,
        contour_parallel: np.ndarray,
        contour_orthogonal: np.ndarray,
        fixed_axis: Literal["horizontal", "vertical"],
        position: float,
        span: float,
        inward_sign: float,
    ) -> dict[str, float]:
        usable_span = max(6.0, span * 0.88)
        sample_count = max(14, min(48, int(round(usable_span / 18.0))))
        offset = REGION_EDGE_SAMPLE_OFFSET_PX
        gradient_values: list[float] = []
        inside_values: list[float] = []
        outside_values: list[float] = []

        for index in range(sample_count):
            t = ((index + 0.5) / sample_count * 2.0) - 1.0
            along = float(t * usable_span)
            if fixed_axis == "horizontal":
                point = center + (along * u) + (position * v)
                inside_point = center + (along * u) + ((position + (inward_sign * offset)) * v)
                outside_point = center + (along * u) + ((position - (inward_sign * offset)) * v)
            else:
                point = center + (position * u) + (along * v)
                inside_point = center + ((position + (inward_sign * offset)) * u) + (along * v)
                outside_point = center + ((position - (inward_sign * offset)) * u) + (along * v)

            px, py = self._clip_point(gray, point)
            ix, iy = self._clip_point(gray, inside_point)
            ox, oy = self._clip_point(gray, outside_point)
            gradient_values.append(float(gradient[py, px]))
            inside_values.append(float(gray[iy, ix]))
            outside_values.append(float(gray[oy, ox]))

        mean_gradient = float(np.mean(gradient_values))
        mean_inside = float(np.mean(inside_values))
        mean_outside = float(np.mean(outside_values))
        gradient_score = max(0.0, min(1.0, mean_gradient / 38.0))
        contrast_score = max(0.0, min(1.0, ((mean_inside - mean_outside) + 8.0) / 36.0))
        contour_band = REGION_EDGE_ORTHOGONAL_BAND_PX
        contour_mask = (np.abs(contour_orthogonal - position) <= contour_band) & (
            np.abs(contour_parallel) <= usable_span
        )
        contour_hits = float(np.count_nonzero(contour_mask))
        expected_hits = max(3.0, usable_span / 60.0)
        contour_coverage_score = max(0.0, min(1.0, contour_hits / expected_hits))
        score = (
            contour_coverage_score * 0.5
            + contrast_score * 0.3
            + gradient_score * 0.2
        )
        return {
            "score": max(0.0, min(1.0, score)),
            "contour_coverage_score": contour_coverage_score,
            "border_contrast_score": contrast_score,
            "gradient_score": gradient_score,
        }

    def _gradient_magnitude(self, gray: np.ndarray) -> np.ndarray:
        grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        return cv2.magnitude(grad_x, grad_y)

    def _illumination_normalized_gray(self, image: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
        normalized = clahe.apply(gray)
        background = cv2.GaussianBlur(normalized, (0, 0), sigmaX=21, sigmaY=21)
        leveled = cv2.addWeighted(normalized, 1.6, background, -0.6, 8.0)
        return np.clip(leveled, 0, 255).astype(np.uint8)

    def _trim_rectified_page(self, image: np.ndarray) -> np.ndarray:
        luma = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)[:, :, 0]
        blurred = cv2.GaussianBlur(luma, (5, 5), 0)
        threshold_value, _ = cv2.threshold(
            blurred,
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU,
        )
        clamped_threshold = max(float(threshold_value), float(BRIGHT_REGION_FLOOR_LUMA))
        _, mask = cv2.threshold(blurred, clamped_threshold, 255, cv2.THRESH_BINARY)
        points = cv2.findNonZero(mask)
        if points is None:
            return image
        x, y, width, height = cv2.boundingRect(points)
        if width < image.shape[1] * 0.7 or height < image.shape[0] * 0.7:
            return image
        pad = 2
        x0 = max(0, x - pad)
        y0 = max(0, y - pad)
        x1 = min(image.shape[1], x + width + pad)
        y1 = min(image.shape[0], y + height + pad)
        return image[y0:y1, x0:x1]

    def _clip_point(self, image: np.ndarray, point: np.ndarray) -> tuple[int, int]:
        x = int(round(max(0.0, min(float(image.shape[1] - 1), float(point[0])))))
        y = int(round(max(0.0, min(float(image.shape[0] - 1), float(point[1])))))
        return x, y

    def _quadrilateral_aspect_ratio(self, corners: np.ndarray) -> float:
        ordered = self._order_corners(corners)
        width = (
            float(np.linalg.norm(ordered[1] - ordered[0]))
            + float(np.linalg.norm(ordered[2] - ordered[3]))
        ) / 2.0
        height = (
            float(np.linalg.norm(ordered[3] - ordered[0]))
            + float(np.linalg.norm(ordered[2] - ordered[1]))
        ) / 2.0
        if width <= 0.0 or height <= 0.0:
            return 1.0
        return width / height

    def _shape_aspect_ratio(self, aspect_ratio: float) -> float:
        if aspect_ratio <= 0.0:
            return 1.0
        return aspect_ratio if aspect_ratio >= 1.0 else (1.0 / aspect_ratio)

    def _aspect_log_error(self, candidate: float, expected: float) -> float:
        safe_candidate = max(candidate, 1e-6)
        safe_expected = max(expected, 1e-6)
        return abs(math.log(safe_candidate / safe_expected))

    def _aspect_score(self, candidate: float, expected: float) -> float:
        error = self._aspect_log_error(candidate, expected)
        return max(0.0, min(1.0, 1.0 - (error / MAX_ASPECT_LOG_ERROR)))

    def _corners_within_margin(
        self,
        corners: np.ndarray,
        *,
        width: int,
        height: int,
        margin_ratio: float,
    ) -> bool:
        margin = max(width, height) * margin_ratio
        min_x = float(np.min(corners[:, 0]))
        max_x = float(np.max(corners[:, 0]))
        min_y = float(np.min(corners[:, 1]))
        max_y = float(np.max(corners[:, 1]))
        return (
            min_x >= -margin
            and min_y >= -margin
            and max_x <= (width - 1 + margin)
            and max_y <= (height - 1 + margin)
        )

    def _polygon_occupancy_score(self, bright_mask: np.ndarray, corners: np.ndarray) -> float:
        polygon_mask = np.zeros(bright_mask.shape, dtype=np.uint8)
        cv2.fillConvexPoly(polygon_mask, self._order_corners(corners).astype(np.int32), 255)
        polygon_pixels = cv2.countNonZero(polygon_mask)
        if polygon_pixels <= 0:
            return 0.0

        overlap_pixels = cv2.countNonZero(cv2.bitwise_and(bright_mask, polygon_mask))
        overlap_score = float(overlap_pixels / polygon_pixels)
        row_scores: list[float] = []
        column_scores: list[float] = []

        for y in range(bright_mask.shape[0]):
            row = polygon_mask[y] > 0
            if row.any():
                row_scores.append(float(np.count_nonzero((bright_mask[y] > 0) & row) / np.count_nonzero(row)))
        for x in range(bright_mask.shape[1]):
            column = polygon_mask[:, x] > 0
            if column.any():
                column_scores.append(
                    float(
                        np.count_nonzero((bright_mask[:, x] > 0) & column)
                        / np.count_nonzero(column)
                    )
                )

        if not row_scores or not column_scores:
            return max(0.0, min(1.0, overlap_score))
        row_score = float(np.percentile(row_scores, 5))
        column_score = float(np.percentile(column_scores, 5))
        continuity_score = (row_score * 0.55) + (column_score * 0.45)
        return max(
            0.0,
            min(1.0, (overlap_score * 0.7) + (continuity_score * 0.3)),
        )

    def _touches_too_many_borders(
        self,
        bounds: tuple[int, int, int, int],
        *,
        width: int,
        height: int,
    ) -> bool:
        x, y, box_width, box_height = bounds
        margin = max(4, int(round(min(width, height) * 0.012)))
        touches = 0
        if x <= margin:
            touches += 1
        if y <= margin:
            touches += 1
        if (x + box_width) >= (width - margin):
            touches += 1
        if (y + box_height) >= (height - margin):
            touches += 1
        return touches >= 2

    def _is_oversized_top_band_region(
        self,
        bounds: tuple[int, int, int, int],
        *,
        component_area: float,
        image_area: float,
        image_height: int,
    ) -> bool:
        _, y, _, _ = bounds
        return y <= (image_height * 0.08) and component_area >= (image_area * 0.55)

    def _build_line_candidate(self, line: np.ndarray) -> LineCandidate:
        x1, y1, x2, y2 = [float(value) for value in line.tolist()]
        dx = x2 - x1
        dy = y2 - y1
        angle = abs(math.degrees(math.atan2(dy, dx)))
        if angle > 90.0:
            angle = 180.0 - angle
        return LineCandidate(
            points=np.array([[x1, y1], [x2, y2]], dtype=np.float32),
            length=float(math.hypot(dx, dy)),
            midpoint_x=(x1 + x2) / 2.0,
            midpoint_y=(y1 + y2) / 2.0,
            angle_degrees=angle,
        )

    def _select_horizontal_line(
        self,
        lines: list[LineCandidate],
        *,
        gray: np.ndarray,
        width: int,
        height: int,
        band_min: float,
        band_max: float,
        prefer_lower: bool,
        expect_below_brighter: bool,
    ) -> Optional[LineCandidate]:
        candidates = [
            line
            for line in lines
            if line.angle_degrees <= 15.0
            and (height * band_min) <= line.midpoint_y <= (height * band_max)
        ]
        if not candidates:
            return None

        def score(line: LineCandidate) -> float:
            length_score = min(1.0, line.length / max(1.0, width * 0.45))
            center_score = max(0.0, 1.0 - abs(line.midpoint_x - (width / 2.0)) / (width / 2.0))
            vertical_fraction = line.midpoint_y / max(1.0, float(height))
            position_score = vertical_fraction if prefer_lower else (1.0 - vertical_fraction)
            contrast_score = self._horizontal_edge_polarity_score(
                gray,
                line,
                expect_below_brighter=expect_below_brighter,
            )
            return (
                (length_score * 0.4)
                + (center_score * 0.1)
                + (position_score * 0.15)
                + (contrast_score * 0.35)
            )

        return max(candidates, key=score)

    def _select_top_line(
        self,
        lines: list[LineCandidate],
        *,
        gray: np.ndarray,
        width: int,
        height: int,
        image_area: float,
        expected_shape_aspect_ratio: float,
        left: LineCandidate,
        right: LineCandidate,
        bottom: LineCandidate,
    ) -> Optional[LineCandidate]:
        candidates = [
            line
            for line in lines
            if line.angle_degrees <= 15.0
            and (height * 0.12) <= line.midpoint_y <= (height * 0.55)
        ]
        if not candidates:
            return None

        best_line: Optional[LineCandidate] = None
        best_score = -1.0
        left_top_y = min(float(left.points[0][1]), float(left.points[1][1]))
        right_top_y = min(float(right.points[0][1]), float(right.points[1][1]))
        extension_budget = max(40.0, height * 0.22)

        for line in candidates:
            top_left = self._line_intersection(line.points, left.points)
            top_right = self._line_intersection(line.points, right.points)
            bottom_right = self._line_intersection(bottom.points, right.points)
            bottom_left = self._line_intersection(bottom.points, left.points)
            corners = np.array(
                [top_left, top_right, bottom_right, bottom_left],
                dtype=np.float32,
            )
            if np.isnan(corners).any():
                continue
            ordered = self._order_corners(corners)
            if ordered[0][0] >= ordered[1][0]:
                continue
            if ordered[0][1] >= ordered[3][1] or ordered[1][1] >= ordered[2][1]:
                continue

            area = abs(cv2.contourArea(ordered.astype(np.float32)))
            if area < image_area * MIN_QUAD_AREA_RATIO:
                continue

            contrast_score = self._horizontal_edge_polarity_score(
                gray,
                line,
                expect_below_brighter=True,
            )
            length_score = min(1.0, line.length / max(1.0, width * 0.4))
            geometry_score = self._score_quadrilateral(
                ordered,
                area=area,
                image_area=image_area,
                expected_shape_aspect_ratio=expected_shape_aspect_ratio,
            )
            left_extension = max(0.0, left_top_y - float(ordered[0][1]))
            right_extension = max(0.0, right_top_y - float(ordered[1][1]))
            extension_score = max(
                0.0,
                1.0
                - (
                    ((left_extension * 0.35) + (right_extension * 0.65))
                    / extension_budget
                ),
            )
            top_width = float(np.linalg.norm(ordered[1] - ordered[0]))
            bottom_width = float(np.linalg.norm(ordered[2] - ordered[3]))
            width_ratio = top_width / max(bottom_width, 1.0)
            width_score = max(0.0, 1.0 - abs(width_ratio - 0.78) / 0.32)
            score = (
                (contrast_score * 0.35)
                + (extension_score * 0.3)
                + (geometry_score * 0.2)
                + (width_score * 0.1)
                + (length_score * 0.05)
            )
            if score > best_score:
                best_score = score
                best_line = line

        return best_line

    def _select_vertical_line(
        self,
        lines: list[LineCandidate],
        *,
        width: int,
        band_min: float,
        band_max: float,
        prefer_right: bool,
    ) -> Optional[LineCandidate]:
        candidates = [
            line
            for line in lines
            if 55.0 <= line.angle_degrees <= 89.0
            and (width * band_min) <= line.midpoint_x <= (width * band_max)
        ]
        if not candidates:
            return None

        def score(line: LineCandidate) -> float:
            length_score = min(1.0, line.length / max(1.0, width * 0.2))
            horizontal_fraction = line.midpoint_x / max(1.0, float(width))
            ideal_fraction = 0.75 if prefer_right else 0.25
            position_score = max(
                0.0,
                1.0 - (abs(horizontal_fraction - ideal_fraction) / 0.25),
            )
            return (length_score * 0.7) + (position_score * 0.3)

        return max(candidates, key=score)

    def _line_intersection(self, first: np.ndarray, second: np.ndarray) -> tuple[float, float]:
        x1, y1 = first[0]
        x2, y2 = first[1]
        x3, y3 = second[0]
        x4, y4 = second[1]
        denominator = ((x1 - x2) * (y3 - y4)) - ((y1 - y2) * (x3 - x4))
        if abs(denominator) < 1e-6:
            return (float("nan"), float("nan"))
        determinant_first = (x1 * y2) - (y1 * x2)
        determinant_second = (x3 * y4) - (y3 * x4)
        x = (
            (determinant_first * (x3 - x4))
            - ((x1 - x2) * determinant_second)
        ) / denominator
        y = (
            (determinant_first * (y3 - y4))
            - ((y1 - y2) * determinant_second)
        ) / denominator
        return (float(x), float(y))

    def _horizontal_edge_polarity_score(
        self,
        gray: np.ndarray,
        line: LineCandidate,
        *,
        expect_below_brighter: bool,
    ) -> float:
        sample_count = max(12, min(40, int(round(line.length / 30.0))))
        offset = max(6.0, min(24.0, gray.shape[0] * 0.012))
        above_values: list[float] = []
        below_values: list[float] = []
        for index in range(sample_count):
            t = (index + 0.5) / sample_count
            x = float(line.points[0][0] + ((line.points[1][0] - line.points[0][0]) * t))
            y = float(line.points[0][1] + ((line.points[1][1] - line.points[0][1]) * t))
            xi = int(round(max(0.0, min(gray.shape[1] - 1.0, x))))
            above_y = int(round(max(0.0, min(gray.shape[0] - 1.0, y - offset))))
            below_y = int(round(max(0.0, min(gray.shape[0] - 1.0, y + offset))))
            above_values.append(float(gray[above_y, xi]))
            below_values.append(float(gray[below_y, xi]))

        mean_above = float(np.mean(above_values))
        mean_below = float(np.mean(below_values))
        contrast = (mean_below - mean_above) if expect_below_brighter else (mean_above - mean_below)
        return max(0.0, min(1.0, (contrast + 12.0) / 48.0))

    def _full_frame_corners(self, image: np.ndarray) -> np.ndarray:
        height, width = image.shape[:2]
        return np.array(
            [
                [0.0, 0.0],
                [float(width - 1), 0.0],
                [float(width - 1), float(height - 1)],
                [0.0, float(height - 1)],
            ],
            dtype=np.float32,
        )

    def _order_corners(self, corners: np.ndarray) -> np.ndarray:
        ordered = np.zeros((4, 2), dtype=np.float32)
        sums = corners.sum(axis=1)
        diffs = np.diff(corners, axis=1).reshape(-1)
        ordered[0] = corners[np.argmin(sums)]
        ordered[2] = corners[np.argmax(sums)]
        ordered[1] = corners[np.argmin(diffs)]
        ordered[3] = corners[np.argmax(diffs)]
        return ordered

    def _rectify(self, image: np.ndarray, corners: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        ordered = self._order_corners(corners)
        width_top = np.linalg.norm(ordered[1] - ordered[0])
        width_bottom = np.linalg.norm(ordered[2] - ordered[3])
        height_right = np.linalg.norm(ordered[2] - ordered[1])
        height_left = np.linalg.norm(ordered[3] - ordered[0])
        width = max(2, int(round(max(width_top, width_bottom))))
        height = max(2, int(round(max(height_right, height_left))))
        destination = np.array(
            [
                [0.0, 0.0],
                [float(width - 1), 0.0],
                [float(width - 1), float(height - 1)],
                [0.0, float(height - 1)],
            ],
            dtype=np.float32,
        )
        matrix = cv2.getPerspectiveTransform(ordered, destination)
        rectified = cv2.warpPerspective(
            image,
            matrix,
            (width, height),
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=CANONICAL_PAGE_BACKGROUND_COLOR,
        )
        return rectified, matrix

    def _apply_orientation(self, image: np.ndarray, target_aspect_ratio: float) -> np.ndarray:
        oriented = image
        if oriented.shape[0] > oriented.shape[1]:
            oriented = cv2.rotate(oriented, cv2.ROTATE_90_CLOCKWISE)
        target_is_portrait = target_aspect_ratio < 1
        if target_is_portrait and oriented.shape[1] >= oriented.shape[0]:
            oriented = cv2.rotate(oriented, cv2.ROTATE_90_COUNTERCLOCKWISE)
        if not target_is_portrait and oriented.shape[0] > oriented.shape[1]:
            oriented = cv2.rotate(oriented, cv2.ROTATE_90_CLOCKWISE)
        return oriented

    def _resize_to_canonical(self, image: np.ndarray, aspect_ratio: float) -> np.ndarray:
        if aspect_ratio >= 1:
            target_width = CANONICAL_LONG_SIDE_PX
            target_height = max(1, int(round(target_width / aspect_ratio)))
        else:
            target_height = CANONICAL_LONG_SIDE_PX
            target_width = max(1, int(round(target_height * aspect_ratio)))
        return cv2.resize(image, (target_width, target_height), interpolation=cv2.INTER_AREA)

    def _build_debug_overlay(
        self,
        image: np.ndarray,
        detection: DetectionCandidate,
        *,
        diagnostics: NormalizationDiagnostics,
    ) -> np.ndarray:
        overlay = image.copy()
        rejected_contour = diagnostics.contour_v3.best_candidate if diagnostics.contour_v3 is not None else None
        if (
            detection.method != "paper_contour_v3"
            and rejected_contour is not None
            and rejected_contour.corners is not None
        ):
            contour_corners = np.array(
                [
                    rejected_contour.corners.top_left,
                    rejected_contour.corners.top_right,
                    rejected_contour.corners.bottom_right,
                    rejected_contour.corners.bottom_left,
                ],
                dtype=np.int32,
            )
            contour_polygon = contour_corners.reshape((-1, 1, 2))
            cv2.polylines(
                overlay,
                [contour_polygon],
                isClosed=True,
                color=(255, 0, 255),
                thickness=2,
                lineType=cv2.LINE_AA,
            )
            contour_rejection = (
                rejected_contour.rejection_reason
                or diagnostics.contour_v3.rejection_reason
                or "rejected"
            )
            cv2.putText(
                overlay,
                f"contour_v3 rejected: {contour_rejection}",
                (24, 104),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.68,
                (255, 0, 255),
                2,
                cv2.LINE_AA,
            )
        rejected_region = diagnostics.region_v2.best_candidate
        if (
            detection.method != "paper_region_v2"
            and rejected_region is not None
            and rejected_region.corners is not None
        ):
            rejected_corners = np.array(
                [
                    rejected_region.corners.top_left,
                    rejected_region.corners.top_right,
                    rejected_region.corners.bottom_right,
                    rejected_region.corners.bottom_left,
                ],
                dtype=np.int32,
            )
            rejected_polygon = rejected_corners.reshape((-1, 1, 2))
            cv2.polylines(
                overlay,
                [rejected_polygon],
                isClosed=True,
                color=(255, 255, 0),
                thickness=2,
                lineType=cv2.LINE_AA,
            )
            rejection_text = rejected_region.rejection_reason or diagnostics.region_v2.rejection_reason or "rejected"
            cv2.putText(
                overlay,
                f"region_v2 rejected: {rejection_text}",
                (24, 76),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.68,
                (255, 255, 0),
                2,
                cv2.LINE_AA,
            )
        polygon = detection.corners.astype(np.int32).reshape((-1, 1, 2))
        color = (60, 210, 240) if detection.confidence >= LOW_CONFIDENCE_THRESHOLD else (0, 170, 255)
        cv2.polylines(overlay, [polygon], isClosed=True, color=color, thickness=4)
        labels = [
            ("TL", detection.corners[0]),
            ("TR", detection.corners[1]),
            ("BR", detection.corners[2]),
            ("BL", detection.corners[3]),
        ]
        for label, point in labels:
            x, y = int(point[0]), int(point[1])
            cv2.circle(overlay, (x, y), 10, (255, 120, 80), thickness=-1)
            cv2.putText(
                overlay,
                label,
                (x + 12, y - 12),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )
        cv2.putText(
            overlay,
            f"{detection.method}  confidence={detection.confidence:.2f}",
            (24, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        return overlay

    def _encode_png(self, image: np.ndarray) -> bytes:
        ok, encoded = cv2.imencode(".png", image)
        if not ok:
            raise ValueError("Failed to encode normalization artifact.")
        return encoded.tobytes()

    def _to_corners(self, corners: np.ndarray) -> NormalizationCorners:
        return NormalizationCorners(
            top_left=(float(round(corners[0][0], 3)), float(round(corners[0][1], 3))),
            top_right=(float(round(corners[1][0], 3)), float(round(corners[1][1], 3))),
            bottom_right=(float(round(corners[2][0], 3)), float(round(corners[2][1], 3))),
            bottom_left=(float(round(corners[3][0], 3)), float(round(corners[3][1], 3))),
        )

    def _corners_to_numpy(self, corners: NormalizationCorners) -> np.ndarray:
        return np.array(
            [
                corners.top_left,
                corners.top_right,
                corners.bottom_right,
                corners.bottom_left,
            ],
            dtype=np.float32,
        )


def target_from_page_size(
    *,
    page_width_mm: float,
    page_height_mm: float,
    source: Literal["prepared_svg", "workspace_drawable_area"],
) -> NormalizationTarget:
    if page_width_mm <= 0 or page_height_mm <= 0:
        raise ValueError("Normalization target page size must be positive.")
    return NormalizationTarget(
        page_width_mm=page_width_mm,
        page_height_mm=page_height_mm,
        source=source,
    )
