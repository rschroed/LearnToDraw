from __future__ import annotations

from typing import Literal, Optional

import cv2
import numpy as np

from learn_to_draw_api.models import (
    InvalidArtifactError,
    NormalizationCorners,
    NormalizationFrame,
    NormalizationMetadata,
    NormalizationOutput,
    NormalizationTransform,
)

from .types import (
    CANONICAL_LONG_SIDE_PX,
    CANONICAL_PAGE_BACKGROUND_COLOR,
    NormalizationArtifacts,
    NormalizationTarget,
)


class CaptureNormalizationService:
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
        if np.any(np.linalg.norm(edges, axis=1) < 8.0):
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

    def _decode_image(self, content: bytes) -> Optional[np.ndarray]:
        buffer = np.frombuffer(content, dtype=np.uint8)
        if buffer.size == 0:
            return None
        return cv2.imdecode(buffer, cv2.IMREAD_COLOR)

    def _encode_png(self, image: np.ndarray) -> bytes:
        ok, encoded = cv2.imencode(".png", image)
        if not ok:
            raise InvalidArtifactError("Capture registration output could not be encoded.")
        return encoded.tobytes()

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
