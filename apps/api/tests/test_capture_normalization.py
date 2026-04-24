from __future__ import annotations

import cv2
import numpy as np

from learn_to_draw_api.services.capture_normalization import (
    CaptureNormalizationService,
    LOW_CONFIDENCE_THRESHOLD,
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


def _build_perspective_paper_image(
    *,
    width: int = 1400,
    height: int = 1000,
    destination: np.ndarray | None = None,
) -> bytes:
    frame = np.full((height, width, 3), (26, 30, 28), dtype=np.uint8)
    paper_width = 760
    paper_height = 980
    paper = np.full((paper_height, paper_width, 3), 244, dtype=np.uint8)
    cv2.rectangle(paper, (0, 0), (paper_width - 1, paper_height - 1), (222, 217, 208), 6)
    cv2.line(paper, (90, 180), (paper_width - 90, 180), (34, 40, 48), 8)
    cv2.rectangle(paper, (110, 250), (paper_width - 110, paper_height - 160), (26, 32, 40), 6)
    cv2.polylines(
        paper,
        [
            np.array(
                [
                    (120, 760),
                    (220, 460),
                    (360, 620),
                    (500, 400),
                    (640, 730),
                ],
                dtype=np.int32,
            )
        ],
        isClosed=False,
        color=(38, 44, 52),
        thickness=8,
    )
    source = np.array(
        [
            [0.0, 0.0],
            [float(paper_width - 1), 0.0],
            [float(paper_width - 1), float(paper_height - 1)],
            [0.0, float(paper_height - 1)],
        ],
        dtype=np.float32,
    )
    if destination is None:
        destination = np.array(
            [
                [260.0, 90.0],
                [1060.0, 110.0],
                [1120.0, 910.0],
                [220.0, 940.0],
            ],
            dtype=np.float32,
        )
    matrix = cv2.getPerspectiveTransform(source, destination)
    warped_paper = cv2.warpPerspective(paper, matrix, (width, height))
    warped_mask = cv2.warpPerspective(
        np.full((paper_height, paper_width), 255, dtype=np.uint8),
        matrix,
        (width, height),
    )
    mask = warped_mask > 0
    frame[mask] = warped_paper[mask]
    return _encode_png(frame)


def _build_connected_bright_rail_image() -> bytes:
    width = 1600
    height = 1100
    frame = np.full((height, width, 3), (28, 31, 30), dtype=np.uint8)

    for x in range(0, width, 70):
        cv2.line(frame, (x, 0), (x, height - 1), (56, 60, 58), 1)
    for y in range(0, height, 70):
        cv2.line(frame, (0, y), (width - 1, y), (56, 60, 58), 1)

    paper_quad = np.array(
        [
            [300, 250],
            [1210, 230],
            [1450, 1010],
            [120, 1020],
        ],
        dtype=np.int32,
    )
    cv2.fillConvexPoly(frame, paper_quad, (245, 243, 239))
    cv2.polylines(frame, [paper_quad], isClosed=True, color=(228, 223, 214), thickness=6)
    cv2.rectangle(frame, (460, 310), (920, 660), (76, 92, 182), 5)
    cv2.line(frame, (470, 620), (900, 360), (76, 92, 182), 5)
    cv2.circle(frame, (580, 430), 48, (76, 92, 182), 4)

    cv2.rectangle(frame, (170, 55), (1515, 180), (242, 241, 238), thickness=-1)
    cv2.rectangle(frame, (860, 180), (955, 305), (242, 241, 238), thickness=-1)
    cv2.rectangle(frame, (1325, 250), (1505, 980), (235, 235, 232), thickness=-1)
    return _encode_png(frame)


def _build_perspective_paper_with_glare() -> bytes:
    content = _build_perspective_paper_image()
    image = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert image is not None
    cv2.ellipse(image, (980, 360), (210, 130), -18, 0, 360, (255, 255, 255), thickness=-1)
    return _encode_png(image)


def _build_perspective_paper_with_partial_edge_loss() -> bytes:
    content = _build_perspective_paper_image()
    image = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert image is not None
    cv2.rectangle(image, (220, 180), (310, 930), (242, 242, 242), thickness=-1)
    return _encode_png(image)


def _build_dense_plotted_paper_image() -> bytes:
    width = 1700
    height = 1200
    frame = np.full((height, width, 3), (24, 28, 27), dtype=np.uint8)
    paper = np.full((900, 1220, 3), 244, dtype=np.uint8)
    cv2.rectangle(paper, (0, 0), (1219, 899), (224, 220, 214), 6)
    cv2.rectangle(paper, (110, 120), (930, 660), (38, 46, 58), 6)
    for x in range(170, 931, 100):
        cv2.line(paper, (x, 120), (x, 660), (86, 92, 102), 4)
    for y in range(190, 661, 70):
        cv2.line(paper, (110, y), (930, y), (86, 92, 102), 3)
    cv2.circle(paper, (220, 230), 72, (56, 64, 78), 5)
    cv2.circle(paper, (760, 250), 64, (56, 64, 78), 5)
    cv2.line(paper, (170, 640), (840, 150), (56, 64, 78), 5)
    cv2.ellipse(paper, (500, 570), (260, 110), 0, 190, 350, (56, 64, 78), 5)
    cv2.putText(
        paper,
        "Dense Pattern Check",
        (120, 82),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.2,
        (120, 88, 52),
        3,
        cv2.LINE_AA,
    )
    source = np.array(
        [
            [0.0, 0.0],
            [1219.0, 0.0],
            [1219.0, 899.0],
            [0.0, 899.0],
        ],
        dtype=np.float32,
    )
    destination = np.array(
        [
            [270.0, 220.0],
            [1430.0, 170.0],
            [1510.0, 1010.0],
            [180.0, 1110.0],
        ],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(source, destination)
    warped_paper = cv2.warpPerspective(paper, matrix, (width, height))
    warped_mask = cv2.warpPerspective(
        np.full((900, 1220), 255, dtype=np.uint8),
        matrix,
        (width, height),
    )
    mask = warped_mask > 0
    frame[mask] = warped_paper[mask]
    cv2.rectangle(frame, (0, 250), (95, 980), (226, 226, 223), thickness=-1)
    cv2.rectangle(frame, (780, 0), (1310, 140), (232, 232, 229), thickness=-1)
    return _encode_png(frame)


def _build_off_axis_dense_paper_image() -> bytes:
    width = 1920
    height = 1080
    frame = np.full((height, width, 3), (28, 31, 30), dtype=np.uint8)
    for x in range(0, width, 68):
        cv2.line(frame, (x, 0), (x, height - 1), (54, 58, 56), 1)
    for y in range(0, height, 68):
        cv2.line(frame, (0, y), (width - 1, y), (54, 58, 56), 1)
    cv2.rectangle(frame, (0, 0), (width - 1, 180), (36, 38, 40), thickness=-1)

    paper = np.full((820, 1220, 3), 244, dtype=np.uint8)
    cv2.rectangle(paper, (0, 0), (1219, 819), (225, 222, 215), 6)
    cv2.rectangle(paper, (130, 110), (760, 520), (70, 88, 170), 4)
    for x in range(180, 761, 90):
        cv2.line(paper, (x, 110), (x, 520), (88, 96, 108), 3)
    for y in range(170, 521, 55):
        cv2.line(paper, (130, y), (760, y), (88, 96, 108), 2)
    cv2.circle(paper, (240, 220), 52, (88, 96, 108), 4)
    cv2.circle(paper, (650, 230), 52, (88, 96, 108), 4)
    cv2.line(paper, (160, 480), (770, 150), (88, 96, 108), 4)
    cv2.ellipse(paper, (460, 450), (210, 90), 0, 190, 350, (88, 96, 108), 4)

    source = np.array(
        [
            [0.0, 0.0],
            [1219.0, 0.0],
            [1219.0, 819.0],
            [0.0, 819.0],
        ],
        dtype=np.float32,
    )
    destination = np.array(
        [
            [520.0, 330.0],
            [1760.0, 270.0],
            [1830.0, 995.0],
            [600.0, 1060.0],
        ],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(source, destination)
    warped_paper = cv2.warpPerspective(paper, matrix, (width, height))
    warped_mask = cv2.warpPerspective(
        np.full((820, 1220), 255, dtype=np.uint8),
        matrix,
        (width, height),
    )
    mask = warped_mask > 0
    frame[mask] = warped_paper[mask]
    return _encode_png(frame)


def _build_off_axis_paper_with_left_extension() -> bytes:
    image = cv2.imdecode(
        np.frombuffer(_build_off_axis_dense_paper_image(), dtype=np.uint8),
        cv2.IMREAD_COLOR,
    )
    assert image is not None
    cv2.rectangle(image, (220, 300), (600, 1060), (243, 243, 240), thickness=-1)
    return _encode_png(image)


def _build_off_axis_paper_with_bottom_extension() -> bytes:
    image = cv2.imdecode(
        np.frombuffer(_build_off_axis_dense_paper_image(), dtype=np.uint8),
        cv2.IMREAD_COLOR,
    )
    assert image is not None
    cv2.rectangle(image, (560, 900), (1830, 1060), (243, 243, 240), thickness=-1)
    return _encode_png(image)


def _build_outline_only_rectangle_image() -> bytes:
    width = 1500
    height = 1100
    frame = np.full((height, width, 3), (24, 28, 26), dtype=np.uint8)
    corners = np.array(
        [
            [250, 160],
            [1180, 180],
            [1290, 980],
            [180, 1010],
        ],
        dtype=np.int32,
    )
    cv2.polylines(frame, [corners], isClosed=True, color=(236, 236, 236), thickness=10)
    cv2.line(frame, tuple(corners[0]), tuple(corners[2]), (245, 245, 245), thickness=4)
    return _encode_png(frame)


def _assert_corners_within_margin(
    result,
    *,
    width: int,
    height: int,
    margin: float,
) -> None:
    corners = result.metadata.corners
    xs = [
        corners.top_left[0],
        corners.top_right[0],
        corners.bottom_right[0],
        corners.bottom_left[0],
    ]
    ys = [
        corners.top_left[1],
        corners.top_right[1],
        corners.bottom_right[1],
        corners.bottom_left[1],
    ]
    assert min(xs) >= -margin
    assert min(ys) >= -margin
    assert max(xs) <= width - 1 + margin
    assert max(ys) <= height - 1 + margin


def test_capture_normalization_detects_confident_paper_region():
    service = CaptureNormalizationService()

    result = service.normalize(
        content=_build_perspective_paper_image(),
        target=target_from_page_size(
            page_width_mm=210.0,
            page_height_mm=200.0,
            source="prepared_svg",
        ),
    )
    grayscale = _decode_png(result.rectified_grayscale)

    assert result.metadata.method == "paper_region_v2"
    assert result.metadata.confidence >= LOW_CONFIDENCE_THRESHOLD
    assert result.metadata.output.width == 2048
    assert result.metadata.output.height == 1950
    assert result.metadata.target_frame_source == "prepared_svg"
    assert result.metadata.frame is not None
    assert result.metadata.frame.kind == "page_aligned"
    assert result.metadata.frame.page_width_mm == 210.0
    assert result.metadata.frame.page_height_mm == 200.0
    assert result.metadata.diagnostics is not None
    assert result.metadata.diagnostics.mode == "default"
    assert result.metadata.diagnostics.region_v2.status == "used"
    assert result.metadata.diagnostics.line_v1.status == "not_run"
    assert result.metadata.transform.matrix[0][0] != 0
    assert len(result.rectified_grayscale) > 0
    assert len(result.debug_overlay) > 0
    assert int(grayscale[grayscale.shape[0] // 2, grayscale.shape[1] // 2]) > 120
    _assert_corners_within_margin(result, width=1400, height=1000, margin=40.0)


def test_capture_normalization_contour_experiment_detects_perspective_page():
    service = CaptureNormalizationService(experiment="contour_v3")

    result = service.normalize(
        content=_build_perspective_paper_image(),
        target=target_from_page_size(
            page_width_mm=210.0,
            page_height_mm=200.0,
            source="prepared_svg",
        ),
    )

    assert result.metadata.method == "paper_contour_v3"
    assert result.metadata.confidence > 0.0
    assert result.metadata.diagnostics is not None
    assert result.metadata.diagnostics.mode == "default"
    assert result.metadata.diagnostics.contour_v3.status == "used"
    assert result.metadata.diagnostics.region_v2.status == "not_run"
    assert result.metadata.diagnostics.line_v1.status == "not_run"
    _assert_corners_within_margin(result, width=1400, height=1000, margin=45.0)


def test_capture_normalization_contour_experiment_detects_off_axis_page():
    service = CaptureNormalizationService(experiment="contour_v3")

    result = service.normalize(
        content=_build_off_axis_dense_paper_image(),
        target=target_from_page_size(
            page_width_mm=210.0,
            page_height_mm=200.0,
            source="prepared_svg",
        ),
    )

    assert result.metadata.method == "paper_contour_v3"
    assert result.metadata.confidence > 0.0
    assert result.metadata.diagnostics is not None
    assert result.metadata.diagnostics.contour_v3.status == "used"
    candidate = result.metadata.diagnostics.contour_v3.best_candidate
    assert candidate is not None
    assert candidate.mean_border_support is not None and candidate.mean_border_support >= 0.5
    _assert_corners_within_margin(result, width=1920, height=1080, margin=85.0)


def test_capture_normalization_keeps_best_region_candidate_for_strong_skew():
    service = CaptureNormalizationService()
    result = service.normalize(
        content=_build_perspective_paper_image(
            destination=np.array(
                [
                    [430.0, 120.0],
                    [840.0, 260.0],
                    [780.0, 860.0],
                    [360.0, 800.0],
                ],
                dtype=np.float32,
            )
        ),
        target=target_from_page_size(
            page_width_mm=210.0,
            page_height_mm=200.0,
            source="workspace_drawable_area",
        ),
    )

    assert result.metadata.method == "paper_region_v2"
    assert result.metadata.confidence > 0.0
    assert result.metadata.output.width == 2048
    assert result.metadata.output.height == 1950
    assert result.metadata.target_frame_source == "workspace_drawable_area"
    assert result.metadata.frame is not None
    assert result.metadata.frame.kind == "page_aligned"
    _assert_corners_within_margin(result, width=1400, height=1000, margin=40.0)


def test_capture_normalization_uses_line_fallback_when_bright_rail_region_is_not_credible():
    service = CaptureNormalizationService()

    result = service.normalize(
        content=_build_connected_bright_rail_image(),
        target=target_from_page_size(
            page_width_mm=210.0,
            page_height_mm=200.0,
            source="prepared_svg",
        ),
    )

    assert result.metadata.method == "paper_edges_v1"
    assert result.metadata.confidence > 0.0
    assert result.metadata.output.width == 2048
    assert result.metadata.output.height == 1950
    assert result.metadata.diagnostics is not None
    assert result.metadata.diagnostics.region_v2.status == "rejected"
    assert result.metadata.diagnostics.region_v2.best_candidate is not None
    assert result.metadata.diagnostics.region_v2.best_candidate.rejection_reason is not None
    assert result.metadata.diagnostics.line_v1.status == "used"
    _assert_corners_within_margin(result, width=1600, height=1100, margin=120.0)
    assert result.metadata.corners.top_left[0] > 180.0
    assert result.metadata.corners.top_left[1] > 180.0
    assert result.metadata.corners.bottom_left[0] > 120.0


def test_capture_normalization_keeps_region_fit_under_glare():
    service = CaptureNormalizationService()

    result = service.normalize(
        content=_build_perspective_paper_with_glare(),
        target=target_from_page_size(
            page_width_mm=210.0,
            page_height_mm=200.0,
            source="prepared_svg",
        ),
    )

    assert result.metadata.method == "paper_region_v2"
    assert result.metadata.confidence > 0.0
    _assert_corners_within_margin(result, width=1400, height=1000, margin=50.0)


def test_capture_normalization_keeps_region_fit_with_partial_edge_loss():
    service = CaptureNormalizationService()

    result = service.normalize(
        content=_build_perspective_paper_with_partial_edge_loss(),
        target=target_from_page_size(
            page_width_mm=210.0,
            page_height_mm=200.0,
            source="prepared_svg",
        ),
    )

    assert result.metadata.method == "paper_region_v2"
    assert result.metadata.confidence > 0.0
    _assert_corners_within_margin(result, width=1400, height=1000, margin=55.0)


def test_capture_normalization_keeps_region_fit_with_dense_internal_strokes():
    service = CaptureNormalizationService()

    result = service.normalize(
        content=_build_dense_plotted_paper_image(),
        target=target_from_page_size(
            page_width_mm=210.0,
            page_height_mm=200.0,
            source="prepared_svg",
        ),
    )

    assert result.metadata.method == "paper_region_v2"
    assert result.metadata.confidence > 0.0
    _assert_corners_within_margin(result, width=1700, height=1200, margin=75.0)


def test_capture_normalization_keeps_region_fit_tight_on_off_axis_page():
    service = CaptureNormalizationService()

    result = service.normalize(
        content=_build_off_axis_dense_paper_image(),
        target=target_from_page_size(
            page_width_mm=210.0,
            page_height_mm=200.0,
            source="prepared_svg",
        ),
    )

    assert result.metadata.method == "paper_region_v2"
    assert result.metadata.confidence > 0.0
    _assert_corners_within_margin(result, width=1920, height=1080, margin=80.0)
    assert result.metadata.corners.top_left[0] > 500.0
    assert result.metadata.corners.bottom_left[0] > 540.0
    assert result.metadata.diagnostics is not None
    candidate = result.metadata.diagnostics.region_v2.best_candidate
    assert candidate is not None
    assert candidate.top_score is not None and candidate.top_score >= 0.95
    assert candidate.right_score is not None and candidate.right_score >= 0.95
    assert candidate.bottom_score is not None and candidate.bottom_score >= 0.95
    assert candidate.left_score is not None and candidate.left_score >= 0.95
    assert candidate.mean_border_support is not None and candidate.mean_border_support >= 0.95
    assert candidate.refined_area_ratio is not None and candidate.refined_area_ratio < 1.05
    assert candidate.max_outward_expansion_px is not None and candidate.max_outward_expansion_px <= 2.1


def test_capture_normalization_region_only_rejects_weak_left_border_candidate():
    service = CaptureNormalizationService(mode="region_only")

    result = service.normalize(
        content=_build_off_axis_paper_with_left_extension(),
        target=target_from_page_size(
            page_width_mm=210.0,
            page_height_mm=200.0,
            source="prepared_svg",
        ),
    )

    assert result.metadata.method == "fallback_full_frame"
    assert result.metadata.confidence == 0.0
    assert result.metadata.diagnostics is not None
    assert result.metadata.diagnostics.mode == "region_only"
    assert result.metadata.diagnostics.region_v2.status == "rejected"
    assert result.metadata.diagnostics.region_v2.rejection_reason == "weak_left_border"
    candidate = result.metadata.diagnostics.region_v2.best_candidate
    assert candidate is not None
    assert candidate.rejection_reason == "weak_left_border"
    assert candidate.left_score is not None and candidate.left_score < 0.28
    assert candidate.top_score is not None and candidate.top_score >= 0.95
    assert candidate.right_score is not None and candidate.right_score >= 0.95
    assert candidate.bottom_score is not None and candidate.bottom_score >= 0.95
    assert result.metadata.diagnostics.line_v1.status == "not_run"


def test_capture_normalization_region_only_rejects_weak_bottom_border_candidate():
    service = CaptureNormalizationService(mode="region_only")

    result = service.normalize(
        content=_build_off_axis_paper_with_bottom_extension(),
        target=target_from_page_size(
            page_width_mm=210.0,
            page_height_mm=200.0,
            source="prepared_svg",
        ),
    )

    assert result.metadata.method == "fallback_full_frame"
    assert result.metadata.confidence == 0.0
    assert result.metadata.diagnostics is not None
    assert result.metadata.diagnostics.mode == "region_only"
    assert result.metadata.diagnostics.region_v2.status == "rejected"
    assert result.metadata.diagnostics.region_v2.rejection_reason == "weak_bottom_border"
    candidate = result.metadata.diagnostics.region_v2.best_candidate
    assert candidate is not None
    assert candidate.rejection_reason == "weak_bottom_border"
    assert candidate.bottom_score is not None and candidate.bottom_score < 0.28
    assert candidate.top_score is not None and candidate.top_score >= 0.95
    assert candidate.right_score is not None and candidate.right_score >= 0.95
    assert candidate.left_score is not None and candidate.left_score >= 0.95
    assert result.metadata.diagnostics.line_v1.status == "not_run"


def test_capture_normalization_uses_line_fallback_when_no_bright_region_exists():
    service = CaptureNormalizationService()

    result = service.normalize(
        content=_build_outline_only_rectangle_image(),
        target=target_from_page_size(
            page_width_mm=210.0,
            page_height_mm=200.0,
            source="prepared_svg",
        ),
    )

    assert result.metadata.method == "paper_edges_v1"
    assert result.metadata.confidence > 0.0
    _assert_corners_within_margin(result, width=1500, height=1100, margin=120.0)
    assert result.metadata.diagnostics is not None
    assert result.metadata.diagnostics.region_v2.status in {"rejected", "unavailable"}
    assert result.metadata.diagnostics.line_v1.status == "used"


def test_capture_normalization_region_only_mode_skips_line_fallback():
    service = CaptureNormalizationService(mode="region_only")

    result = service.normalize(
        content=_build_outline_only_rectangle_image(),
        target=target_from_page_size(
            page_width_mm=210.0,
            page_height_mm=200.0,
            source="prepared_svg",
        ),
    )

    assert result.metadata.method == "fallback_full_frame"
    assert result.metadata.confidence == 0.0
    assert result.metadata.diagnostics is not None
    assert result.metadata.diagnostics.mode == "region_only"
    assert result.metadata.diagnostics.line_v1.status == "not_run"
    assert result.metadata.diagnostics.line_v1.rejection_reason == "disabled_in_region_only_mode"


def test_capture_normalization_falls_back_to_full_frame_when_no_rectangle_found():
    service = CaptureNormalizationService()
    image = np.full((900, 1200, 3), (25, 28, 26), dtype=np.uint8)
    cv2.circle(image, (400, 420), 120, (70, 90, 110), thickness=-1)
    cv2.line(image, (100, 120), (1040, 780), (110, 120, 130), 18)

    result = service.normalize(
        content=_encode_png(image),
        target=target_from_page_size(
            page_width_mm=210.0,
            page_height_mm=200.0,
            source="prepared_svg",
        ),
    )

    assert result.metadata.method == "fallback_full_frame"
    assert result.metadata.confidence == 0.0
    assert result.metadata.output.width == 2048
    assert result.metadata.output.height == 1950
    assert result.metadata.corners.top_left == (0.0, 0.0)
