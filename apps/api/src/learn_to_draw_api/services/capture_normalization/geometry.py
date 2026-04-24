from __future__ import annotations

import math
from typing import Literal, Optional

import cv2
import numpy as np

from learn_to_draw_api.models import (
    NormalizationDiagnosticCandidate,
    NormalizationMethodDiagnostics,
)

from .types import (
    MAX_ASPECT_LOG_ERROR,
    MAX_DETECTION_DIMENSION_PX,
    REGION_ALLOWED_OUTWARD_EXPANSION_PX,
    REGION_BOX_QUANTILE,
    REGION_EDGE_ORTHOGONAL_BAND_PX,
    REGION_EDGE_SAMPLE_OFFSET_PX,
    REGION_FINAL_INSET_PX,
    REGION_INWARD_EXPANSION_PX,
    REGION_OUTWARD_EXPANSION_PX,
    SNAP_BOX_QUANTILE,
    DetectorCandidateDiagnostics,
    DetectorRunDiagnostics,
)


class GeometryMixin:
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

    def _order_corners(self, corners: np.ndarray) -> np.ndarray:
        ordered = np.zeros((4, 2), dtype=np.float32)
        sums = corners.sum(axis=1)
        diffs = np.diff(corners, axis=1).reshape(-1)
        ordered[0] = corners[np.argmin(sums)]
        ordered[2] = corners[np.argmax(sums)]
        ordered[1] = corners[np.argmin(diffs)]
        ordered[3] = corners[np.argmax(diffs)]
        return ordered
