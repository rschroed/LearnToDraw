from __future__ import annotations

from typing import Optional

import cv2
import numpy as np

from .types import (
    BRIGHT_REGION_FLOOR_LUMA,
    MAX_ASPECT_LOG_ERROR,
    MAX_DETECTION_MARGIN_RATIO,
    MIN_QUAD_AREA_RATIO,
    MIN_REGION_FILL_RATIO,
    REGION_MAX_REFINED_AREA_RATIO,
    REGION_MIN_MEAN_BORDER_SUPPORT,
    REGION_MIN_SIDE_SCORE,
    REGION_OUTWARD_EXPANSION_PX,
    DetectionCandidate,
    DetectorCandidateDiagnostics,
    DetectorRunDiagnostics,
)


class RegionDetectorMixin:
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
