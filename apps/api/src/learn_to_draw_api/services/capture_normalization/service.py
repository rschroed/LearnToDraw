from __future__ import annotations

from typing import Literal, Optional

import cv2
import numpy as np

from learn_to_draw_api.models import (
    InvalidArtifactError,
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
    CANONICAL_LONG_SIDE_PX,
    CANONICAL_PAGE_BACKGROUND_COLOR,
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

    def initial_registration_corners(
        self,
        *,
        image_width: int,
        image_height: int,
    ) -> NormalizationCorners:
        if image_width < 2 or image_height < 2:
            raise InvalidArtifactError("Capture dimensions must be at least 2 by 2 pixels.")
        max_x = float(image_width - 1)
        max_y = float(image_height - 1)
        inset_x = max_x * 0.05
        inset_y = max_y * 0.05
        return NormalizationCorners(
            top_left=(round(inset_x, 3), round(inset_y, 3)),
            top_right=(round(max_x - inset_x, 3), round(inset_y, 3)),
            bottom_right=(round(max_x - inset_x, 3), round(max_y - inset_y, 3)),
            bottom_left=(round(inset_x, 3), round(max_y - inset_y, 3)),
        )

    def validate_registration_corners(
        self,
        *,
        corners: NormalizationCorners,
        image_width: int,
        image_height: int,
    ) -> np.ndarray:
        if image_width < 2 or image_height < 2:
            raise InvalidArtifactError("Capture dimensions must be at least 2 by 2 pixels.")
        points = self._corners_to_numpy(corners).astype(np.float64)
        if not np.isfinite(points).all():
            raise InvalidArtifactError("Registration corners must contain finite coordinates.")

        max_x = float(image_width - 1)
        max_y = float(image_height - 1)
        if (
            np.any(points[:, 0] < 0)
            or np.any(points[:, 0] > max_x)
            or np.any(points[:, 1] < 0)
            or np.any(points[:, 1] > max_y)
        ):
            raise InvalidArtifactError("Registration corners must be inside the capture bounds.")

        edges = np.roll(points, -1, axis=0) - points
        edge_lengths = np.linalg.norm(edges, axis=1)
        if np.any(edge_lengths < 8.0):
            raise InvalidArtifactError("Every registration edge must be at least 8 pixels long.")

        next_edges = np.roll(edges, -1, axis=0)
        cross_products = (
            edges[:, 0] * next_edges[:, 1] - edges[:, 1] * next_edges[:, 0]
        )
        if np.any(cross_products <= 0):
            raise InvalidArtifactError(
                "Registration corners must form a convex, non-crossing TL/TR/BR/BL quad."
            )

        area = 0.5 * abs(
            float(
                np.dot(points[:, 0], np.roll(points[:, 1], -1))
                - np.dot(points[:, 1], np.roll(points[:, 0], -1))
            )
        )
        if area < float(image_width * image_height) * 0.01:
            raise InvalidArtifactError(
                "Registration quad must cover at least 1% of the capture area."
            )
        return points.astype(np.float32)

    def register_with_corners(
        self,
        *,
        content: bytes,
        target: NormalizationTarget,
        corners: NormalizationCorners,
    ) -> NormalizationArtifacts:
        decoded = self._decode_image(content)
        if decoded is None:
            raise InvalidArtifactError("Capture content is not a supported raster image.")
        image_height, image_width = decoded.shape[:2]
        source = self.validate_registration_corners(
            corners=corners,
            image_width=image_width,
            image_height=image_height,
        )
        output_width, output_height = self._canonical_output_size(target.aspect_ratio)
        destination = np.array(
            [
                [0.0, 0.0],
                [float(output_width - 1), 0.0],
                [float(output_width - 1), float(output_height - 1)],
                [0.0, float(output_height - 1)],
            ],
            dtype=np.float32,
        )
        matrix = cv2.getPerspectiveTransform(source, destination)
        inverse_matrix = np.linalg.inv(matrix)
        rectified = cv2.warpPerspective(
            decoded,
            matrix,
            (output_width, output_height),
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=CANONICAL_PAGE_BACKGROUND_COLOR,
        )
        grayscale = cv2.cvtColor(rectified, cv2.COLOR_BGR2GRAY)
        debug_overlay = self._build_registration_overlay(decoded, source)
        return NormalizationArtifacts(
            rectified_color=self._encode_png(rectified),
            rectified_grayscale=self._encode_png(grayscale),
            debug_overlay=self._encode_png(debug_overlay),
            metadata=NormalizationMetadata(
                method="manual_corners_v2",
                confidence=None,
                corners=corners,
                transform=NormalizationTransform(
                    matrix=self._rounded_matrix(matrix),
                    inverse_matrix=self._rounded_matrix(inverse_matrix),
                    source_space="raw_capture_px",
                    destination_space="page_px",
                    pixels_per_mm_x=(output_width - 1) / target.page_width_mm,
                    pixels_per_mm_y=(output_height - 1) / target.page_height_mm,
                ),
                output=NormalizationOutput(
                    width=output_width,
                    height=output_height,
                    aspect_ratio=target.aspect_ratio,
                ),
                target_frame_source=target.source,
                diagnostics=None,
                frame=NormalizationFrame(
                    kind="page_aligned",
                    version=2,
                    page_width_mm=target.page_width_mm,
                    page_height_mm=target.page_height_mm,
                    origin="top-left",
                ),
            ),
        )

    def _canonical_output_size(self, aspect_ratio: float) -> tuple[int, int]:
        if aspect_ratio >= 1:
            return CANONICAL_LONG_SIDE_PX, max(
                1, int(round(CANONICAL_LONG_SIDE_PX / aspect_ratio))
            )
        return (
            max(1, int(round(CANONICAL_LONG_SIDE_PX * aspect_ratio))),
            CANONICAL_LONG_SIDE_PX,
        )

    def _rounded_matrix(self, matrix: np.ndarray) -> list[list[float]]:
        return [[float(round(value, 9)) for value in row] for row in matrix.tolist()]

    def _build_registration_overlay(
        self,
        image: np.ndarray,
        corners: np.ndarray,
    ) -> np.ndarray:
        overlay = image.copy()
        polygon = np.round(corners).astype(np.int32).reshape((-1, 1, 2))
        thickness = max(2, int(round(max(image.shape[:2]) / 600)))
        cv2.polylines(
            overlay,
            [polygon],
            isClosed=True,
            color=(20, 210, 20),
            thickness=thickness,
            lineType=cv2.LINE_AA,
        )
        for point, label in zip(corners, ("TL", "TR", "BR", "BL")):
            x, y = (int(round(point[0])), int(round(point[1])))
            cv2.circle(overlay, (x, y), thickness * 3, (20, 210, 20), thickness=-1)
            cv2.putText(
                overlay,
                label,
                (x + thickness * 4, y - thickness * 4),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (20, 210, 20),
                thickness,
                cv2.LINE_AA,
            )
        return overlay

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
