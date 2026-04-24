from __future__ import annotations

import math
from typing import Optional

import cv2
import numpy as np

from .types import (
    MIN_QUAD_AREA_RATIO,
    DetectionCandidate,
    DetectorCandidateDiagnostics,
    DetectorRunDiagnostics,
    LineCandidate,
)


class LineDetectorMixin:
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
