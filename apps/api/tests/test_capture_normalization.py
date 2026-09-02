from __future__ import annotations

import cv2
import numpy as np
import pytest

from learn_to_draw_api.models import (
    CaptureReview,
    InvalidArtifactError,
    NormalizationCorners,
    NormalizationMetadata,
)
from learn_to_draw_api.services.capture_normalization import (
    CaptureNormalizationService,
    target_from_page_size,
)


def _encode_png(image: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    return encoded.tobytes()


def _decode_png(content: bytes) -> np.ndarray:
    image = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    assert image is not None
    return image


@pytest.mark.parametrize(
    ("page_width_mm", "page_height_mm", "expected_size"),
    [
        (210.0, 297.0, (1448, 2048)),
        (297.0, 210.0, (2048, 1448)),
    ],
)
def test_manual_registration_maps_directly_to_canonical_page(
    page_width_mm,
    page_height_mm,
    expected_size,
):
    service = CaptureNormalizationService()
    image = np.full((720, 960, 3), 245, dtype=np.uint8)
    corners = NormalizationCorners(
        top_left=(120.0, 80.0),
        top_right=(850.0, 105.0),
        bottom_right=(900.0, 650.0),
        bottom_left=(75.0, 675.0),
    )

    result = service.register_with_corners(
        content=_encode_png(image),
        target=target_from_page_size(
            page_width_mm=page_width_mm,
            page_height_mm=page_height_mm,
            source="prepared_svg",
        ),
        corners=corners,
    )

    width, height = expected_size
    assert (result.metadata.output.width, result.metadata.output.height) == expected_size
    assert _decode_png(result.rectified_color).shape[:2] == (height, width)
    assert _decode_png(result.rectified_grayscale).shape[:2] == (height, width)
    assert result.metadata.method == "manual_corners_v2"
    assert result.metadata.confidence is None
    assert result.metadata.frame is not None
    assert result.metadata.frame.version == 2
    assert result.metadata.frame.origin == "top-left"
    assert result.metadata.transform.source_space == "raw_capture_px"
    assert result.metadata.transform.destination_space == "page_px"
    assert result.metadata.transform.pixels_per_mm_x == pytest.approx(
        (width - 1) / page_width_mm
    )
    assert result.metadata.transform.pixels_per_mm_y == pytest.approx(
        (height - 1) / page_height_mm
    )

    matrix = np.array(result.metadata.transform.matrix)
    inverse = np.array(result.metadata.transform.inverse_matrix)
    assert matrix @ inverse == pytest.approx(np.eye(3), abs=1e-6)
    source = np.array(
        [[corners.top_left, corners.top_right, corners.bottom_right, corners.bottom_left]],
        dtype=np.float64,
    )
    projected = cv2.perspectiveTransform(source, matrix)[0]
    assert projected == pytest.approx(
        np.array(
            [
                [0.0, 0.0],
                [float(width - 1), 0.0],
                [float(width - 1), float(height - 1)],
                [0.0, float(height - 1)],
            ]
        ),
        abs=1e-3,
    )


def test_manual_registration_preserves_selected_page_boundary():
    service = CaptureNormalizationService()
    image = np.zeros((300, 400, 3), dtype=np.uint8)
    corners = NormalizationCorners(
        top_left=(40.0, 30.0),
        top_right=(359.0, 30.0),
        bottom_right=(359.0, 269.0),
        bottom_left=(40.0, 269.0),
    )
    cv2.circle(image, (40, 30), 6, (0, 0, 255), thickness=-1)
    cv2.circle(image, (359, 30), 6, (0, 255, 0), thickness=-1)
    cv2.circle(image, (359, 269), 6, (255, 0, 0), thickness=-1)
    cv2.circle(image, (40, 269), 6, (255, 255, 255), thickness=-1)

    result = service.register_with_corners(
        content=_encode_png(image),
        target=target_from_page_size(
            page_width_mm=200.0,
            page_height_mm=150.0,
            source="prepared_svg",
        ),
        corners=corners,
    )
    rectified = _decode_png(result.rectified_color)

    assert rectified[2, 2, 2] > 180
    assert rectified[2, -3, 1] > 180
    assert rectified[-3, -3, 0] > 180
    assert rectified[-3, 2].mean() > 180


def test_manual_registration_seeds_five_percent_inset_quad():
    corners = CaptureNormalizationService().initial_registration_corners(
        image_width=1001,
        image_height=501,
    )

    assert corners == NormalizationCorners(
        top_left=(50.0, 25.0),
        top_right=(950.0, 25.0),
        bottom_right=(950.0, 475.0),
        bottom_left=(50.0, 475.0),
    )


@pytest.mark.parametrize(
    ("corners", "message"),
    [
        (
            NormalizationCorners(
                top_left=(-1.0, 20.0),
                top_right=(180.0, 20.0),
                bottom_right=(180.0, 180.0),
                bottom_left=(20.0, 180.0),
            ),
            "inside the capture bounds",
        ),
        (
            NormalizationCorners(
                top_left=(20.0, 20.0),
                top_right=(180.0, 180.0),
                bottom_right=(180.0, 20.0),
                bottom_left=(20.0, 180.0),
            ),
            "convex, non-crossing",
        ),
        (
            NormalizationCorners(
                top_left=(20.0, 20.0),
                top_right=(180.0, 20.0),
                bottom_right=(100.0, 80.0),
                bottom_left=(20.0, 180.0),
            ),
            "convex, non-crossing",
        ),
        (
            NormalizationCorners(
                top_left=(20.0, 20.0),
                top_right=(20.0, 20.0),
                bottom_right=(180.0, 180.0),
                bottom_left=(20.0, 180.0),
            ),
            "at least 8 pixels",
        ),
        (
            NormalizationCorners(
                top_left=(20.0, 20.0),
                top_right=(25.0, 20.0),
                bottom_right=(25.0, 180.0),
                bottom_left=(20.0, 180.0),
            ),
            "at least 8 pixels",
        ),
        (
            NormalizationCorners(
                top_left=(20.0, 20.0),
                top_right=(35.0, 20.0),
                bottom_right=(35.0, 35.0),
                bottom_left=(20.0, 35.0),
            ),
            "at least 1%",
        ),
        (
            NormalizationCorners(
                top_left=(float("nan"), 20.0),
                top_right=(180.0, 20.0),
                bottom_right=(180.0, 180.0),
                bottom_left=(20.0, 180.0),
            ),
            "finite coordinates",
        ),
    ],
)
def test_manual_registration_rejects_invalid_quads(corners, message):
    with pytest.raises(InvalidArtifactError, match=message):
        CaptureNormalizationService().validate_registration_corners(
            corners=corners,
            image_width=200,
            image_height=200,
        )


def test_legacy_capture_models_remain_parseable():
    review = CaptureReview.model_validate(
        {
            "review_required": True,
            "review_status": "pending",
            "proposed_corners": {
                "top_left": [10.0, 10.0],
                "top_right": [190.0, 10.0],
                "bottom_right": [190.0, 190.0],
                "bottom_left": [10.0, 190.0],
            },
            "detector_method": "paper_edges_v1",
            "detector_confidence": 0.42,
            "reuse_last_available": True,
        }
    )
    metadata = NormalizationMetadata.model_validate(
        {
            "method": "paper_edges_v1",
            "confidence": 0.42,
            "corners": review.proposed_corners.model_dump(),
            "transform": {
                "matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
            },
            "output": {"width": 200, "height": 200, "aspect_ratio": 1.0},
            "target_frame_source": "prepared_svg",
            "frame": {
                "kind": "page_aligned",
                "version": 1,
                "page_width_mm": 200.0,
                "page_height_mm": 200.0,
            },
        }
    )

    assert review.registration_version == 1
    assert review.review_mode is None
    assert metadata.frame is not None and metadata.frame.version == 1
    assert metadata.transform.inverse_matrix is None
    assert metadata.transform.source_space is None
