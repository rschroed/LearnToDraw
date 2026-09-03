from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from learn_to_draw_api.models import NormalizationCorners


@dataclass(frozen=True)
class RegistrationProposalAttempt:
    corners: Optional[NormalizationCorners]
    stability_max_px: Optional[float]
    fallback_reason: Optional[str]


class CaptureRegistrationProposalService:
    _THRESHOLD_SHIFTS = (-12.0, -6.0, 0.0, 6.0, 12.0)
    _APPROXIMATION_RATIOS = (0.002, 0.003, 0.004, 0.006, 0.008, 0.01, 0.015, 0.02, 0.03)

    def propose(
        self,
        *,
        content: bytes,
        expected_width: int,
        expected_height: int,
    ) -> RegistrationProposalAttempt:
        image = self._decode_image(content)
        if image is None:
            return self._unavailable("capture_not_decodable")
        image_height, image_width = image.shape[:2]
        if (image_width, image_height) != (expected_width, expected_height):
            return self._unavailable("capture_dimensions_mismatch")

        luma = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)[:, :, 0]
        blurred_luma = cv2.GaussianBlur(luma, (0, 0), 5.0)
        otsu_threshold, _ = cv2.threshold(
            blurred_luma,
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU,
        )
        gray = cv2.GaussianBlur(
            cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32),
            (0, 0),
            1.0,
        )
        proposals = []
        rejection_reasons = []
        for shift in self._THRESHOLD_SHIFTS:
            proposal, rejection_reason = self._proposal_at_threshold(
                blurred_luma=blurred_luma,
                gray=gray,
                threshold=float(np.clip(otsu_threshold + shift, 25, 230)),
            )
            if proposal is None:
                rejection_reasons.append(rejection_reason or "proposal_unavailable")
            else:
                proposals.append(proposal)

        if len(proposals) != len(self._THRESHOLD_SHIFTS):
            return self._unavailable(self._most_common_reason(rejection_reasons))
        proposal_stack = np.stack(proposals)
        median_proposal = np.median(proposal_stack, axis=0)
        stability = np.linalg.norm(
            proposal_stack - median_proposal[None, :, :],
            axis=2,
        )
        stability_max_px = float(stability.max())
        stability_limit_px = max(2.0, max(image_width, image_height) / 384.0)
        if stability_max_px > stability_limit_px:
            return self._unavailable("unstable_across_thresholds")

        return RegistrationProposalAttempt(
            corners=self._numpy_to_corners(median_proposal),
            stability_max_px=round(stability_max_px, 3),
            fallback_reason=None,
        )

    def _proposal_at_threshold(
        self,
        *,
        blurred_luma: np.ndarray,
        gray: np.ndarray,
        threshold: float,
    ) -> tuple[Optional[np.ndarray], Optional[str]]:
        image_height, image_width = blurred_luma.shape
        _, bright_mask = cv2.threshold(
            blurred_luma,
            threshold,
            255,
            cv2.THRESH_BINARY,
        )
        close_size = self._odd_kernel_size(max(image_width, image_height) / 62.0, 7)
        open_size = self._odd_kernel_size(max(image_width, image_height) / 213.0, 3)
        bright_mask = cv2.morphologyEx(
            bright_mask,
            cv2.MORPH_CLOSE,
            np.ones((close_size, close_size), dtype=np.uint8),
            iterations=2,
        )
        bright_mask = cv2.morphologyEx(
            bright_mask,
            cv2.MORPH_OPEN,
            np.ones((open_size, open_size), dtype=np.uint8),
            iterations=1,
        )
        contours, _ = cv2.findContours(
            bright_mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_NONE,
        )
        image_area = float(image_width * image_height)
        candidates = sorted(contours, key=cv2.contourArea, reverse=True)
        contour = next(
            (
                candidate
                for candidate in candidates
                if cv2.contourArea(candidate) >= image_area * 0.12
            ),
            None,
        )
        if contour is None:
            return None, "no_large_bright_region"

        x, y, width, height = cv2.boundingRect(contour)
        border_count = sum(
            (
                x <= 1,
                y <= 1,
                x + width >= image_width - 1,
                y + height >= image_height - 1,
            )
        )
        if border_count >= 2:
            return None, "bright_region_touches_multiple_borders"

        hull = cv2.convexHull(contour)
        perimeter = cv2.arcLength(hull, True)
        coarse = None
        for ratio in self._APPROXIMATION_RATIOS:
            approximation = cv2.approxPolyDP(hull, ratio * perimeter, True).reshape(-1, 2)
            if len(approximation) == 4:
                coarse = self._order_corners(approximation.astype(np.float32))
                break
        if coarse is None:
            return None, "bright_region_not_quadrilateral"

        try:
            lines = [
                self._fit_side(gray, coarse[index], coarse[(index + 1) % 4])
                for index in range(4)
            ]
            refined = np.array(
                [
                    self._intersect(lines[3], lines[0]),
                    self._intersect(lines[0], lines[1]),
                    self._intersect(lines[1], lines[2]),
                    self._intersect(lines[2], lines[3]),
                ],
                dtype=np.float32,
            )
        except (cv2.error, ValueError, np.linalg.LinAlgError):
            return None, "edge_refinement_failed"
        if not np.isfinite(refined).all():
            return None, "edge_refinement_failed"
        if (
            np.any(refined[:, 0] < 0)
            or np.any(refined[:, 0] > image_width - 1)
            or np.any(refined[:, 1] < 0)
            or np.any(refined[:, 1] > image_height - 1)
        ):
            return None, "physical_corner_outside_capture"
        return refined, None

    def _fit_side(
        self,
        gray: np.ndarray,
        start: np.ndarray,
        end: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        vector = end.astype(np.float64) - start.astype(np.float64)
        length = float(np.linalg.norm(vector))
        if length < 8.0:
            raise ValueError("Candidate edge is too short.")
        tangent = vector / length
        normal = np.array([-tangent[1], tangent[0]])
        sample_count = max(100, int(round(length * 0.75)))
        positions = np.linspace(0.06, 0.94, sample_count)
        search_radius = max(gray.shape) * 42.0 / 1920.0
        offsets = np.linspace(-search_radius, search_radius, 337)
        centers = start[None, :] + positions[:, None] * vector[None, :]
        points = centers[:, None, :] + offsets[None, :, None] * normal[None, None, :]
        values = cv2.remap(
            gray,
            points[:, :, 0].astype(np.float32),
            points[:, :, 1].astype(np.float32),
            cv2.INTER_LINEAR,
        )
        gradient = np.abs(values[:, 4:] - values[:, :-4])
        indexes = np.argmax(gradient, axis=1) + 2
        rows = np.arange(sample_count)
        candidates = points[rows, indexes]
        strengths = gradient[rows, indexes - 2]
        chosen_offsets = offsets[indexes]

        strength_floor = np.percentile(strengths, 40)
        strong_offsets = chosen_offsets[strengths >= strength_floor]
        if strong_offsets.size == 0:
            raise ValueError("Candidate edge has no usable gradient samples.")
        median_offset = np.median(strong_offsets)
        selected = candidates[
            (strengths >= strength_floor)
            & (np.abs(chosen_offsets - median_offset) <= max(2.0, search_radius / 8.4))
        ]
        if len(selected) < 8:
            raise ValueError("Candidate edge has too few coherent samples.")
        for _ in range(3):
            fitted = cv2.fitLine(
                selected.astype(np.float32),
                cv2.DIST_HUBER,
                0,
                0.01,
                0.01,
            ).reshape(-1)
            direction = fitted[:2].astype(np.float64)
            origin = fitted[2:].astype(np.float64)
            delta = selected - origin
            residual = np.abs(direction[0] * delta[:, 1] - direction[1] * delta[:, 0])
            cutoff = max(1.0, float(np.percentile(residual, 80)))
            selected = selected[residual <= cutoff]
        return origin, direction / np.linalg.norm(direction)

    def _intersect(
        self,
        first: tuple[np.ndarray, np.ndarray],
        second: tuple[np.ndarray, np.ndarray],
    ) -> np.ndarray:
        first_origin, first_direction = first
        second_origin, second_direction = second
        parameters = np.linalg.solve(
            np.column_stack((first_direction, -second_direction)),
            second_origin - first_origin,
        )
        return first_origin + parameters[0] * first_direction

    def _order_corners(self, points: np.ndarray) -> np.ndarray:
        center = points.mean(axis=0)
        angles = np.arctan2(points[:, 1] - center[1], points[:, 0] - center[0])
        ordered = points[np.argsort(angles)]
        top_left_index = int(np.argmin(ordered.sum(axis=1)))
        return np.roll(ordered, -top_left_index, axis=0)

    def _numpy_to_corners(self, points: np.ndarray) -> NormalizationCorners:
        rounded = np.round(points.astype(np.float64), 3)
        return NormalizationCorners(
            top_left=tuple(rounded[0]),
            top_right=tuple(rounded[1]),
            bottom_right=tuple(rounded[2]),
            bottom_left=tuple(rounded[3]),
        )

    def _decode_image(self, content: bytes) -> Optional[np.ndarray]:
        buffer = np.frombuffer(content, dtype=np.uint8)
        if buffer.size == 0:
            return None
        return cv2.imdecode(buffer, cv2.IMREAD_COLOR)

    def _odd_kernel_size(self, raw_size: float, minimum: int) -> int:
        size = max(minimum, int(round(raw_size)))
        return size if size % 2 == 1 else size + 1

    def _most_common_reason(self, reasons: list[str]) -> str:
        if not reasons:
            return "proposal_unavailable"
        return max(set(reasons), key=lambda reason: (reasons.count(reason), reason))

    def _unavailable(self, reason: str) -> RegistrationProposalAttempt:
        return RegistrationProposalAttempt(
            corners=None,
            stability_max_px=None,
            fallback_reason=reason,
        )
