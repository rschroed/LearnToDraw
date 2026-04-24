from __future__ import annotations

from typing import Literal, Optional

import cv2
import numpy as np

from learn_to_draw_api.models import (
    NormalizationCorners,
    NormalizationDiagnostics,
    NormalizationFrame,
    NormalizationMethod,
    NormalizationMethodDiagnostics,
    NormalizationMetadata,
    NormalizationOutput,
    NormalizationTransform,
)

from .contour_detector import ContourDetectorMixin
from .geometry import GeometryMixin
from .line_detector import LineDetectorMixin
from .region_detector import RegionDetectorMixin
from .rendering import RenderingMixin
from .types import (
    CaptureNormalizationProposal,
    DetectionCandidate,
    DetectionResult,
    DetectorRunDiagnostics,
    NormalizationArtifacts,
    NormalizationExperiment,
    NormalizationMode,
    NormalizationTarget,
    not_run_diagnostics,
)


class CaptureNormalizationService(
    RenderingMixin,
    GeometryMixin,
    RegionDetectorMixin,
    ContourDetectorMixin,
    LineDetectorMixin,
):
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
                contour_v3=not_run_diagnostics(),
                region_v2=not_run_diagnostics(),
                line_v1=not_run_diagnostics(),
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
                        else not_run_diagnostics()
                    ),
                    region_v2=(
                        self._to_method_diagnostics(region_diagnostics, status="used")
                        if self._experiment == "region_v2"
                        else not_run_diagnostics()
                    ),
                    line_v1=not_run_diagnostics(),
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
                        else not_run_diagnostics()
                    ),
                    region_v2=(
                        self._to_method_diagnostics(
                            region_diagnostics,
                            status="rejected" if region_diagnostics.candidate_count > 0 else "unavailable",
                        )
                        if self._experiment == "region_v2"
                        else not_run_diagnostics()
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
                        else not_run_diagnostics()
                    ),
                    region_v2=(
                        self._to_method_diagnostics(
                            region_diagnostics,
                            status="rejected" if region_diagnostics.candidate_count > 0 else "unavailable",
                        )
                        if self._experiment == "region_v2"
                        else not_run_diagnostics()
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
                    else not_run_diagnostics()
                ),
                region_v2=(
                    self._to_method_diagnostics(
                        region_diagnostics,
                        status="rejected" if region_diagnostics.candidate_count > 0 else "unavailable",
                    )
                    if self._experiment == "region_v2"
                    else not_run_diagnostics()
                ),
                line_v1=self._to_method_diagnostics(
                    line_diagnostics,
                    status="rejected" if line_diagnostics.candidate_count > 0 else "unavailable",
                ),
            ),
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
