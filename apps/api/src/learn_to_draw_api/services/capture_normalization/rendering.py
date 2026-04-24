from __future__ import annotations

from typing import Optional

import cv2
import numpy as np

from learn_to_draw_api.models import NormalizationCorners, NormalizationDiagnostics

from .types import (
    BRIGHT_REGION_FLOOR_LUMA,
    CANONICAL_LONG_SIDE_PX,
    CANONICAL_PAGE_BACKGROUND_COLOR,
    LOW_CONFIDENCE_THRESHOLD,
    DetectionCandidate,
)


class RenderingMixin:
    def _decode_image(self, content: bytes) -> Optional[np.ndarray]:
        buffer = np.frombuffer(content, dtype=np.uint8)
        if buffer.size == 0:
            return None
        image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        return image

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
