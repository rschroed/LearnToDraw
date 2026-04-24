from __future__ import annotations

from typing import Optional

import cv2
import numpy as np

from .types import (
    MAX_ASPECT_LOG_ERROR,
    MAX_DETECTION_MARGIN_RATIO,
    MIN_QUAD_AREA_RATIO,
    REGION_MIN_MEAN_BORDER_SUPPORT,
    REGION_MIN_SIDE_SCORE,
    DetectionCandidate,
    DetectorCandidateDiagnostics,
    DetectorRunDiagnostics,
)


class ContourDetectorMixin:
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
