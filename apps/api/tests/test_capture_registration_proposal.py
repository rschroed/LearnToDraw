from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from learn_to_draw_api.services.capture_normalization import (
    CaptureNormalizationService,
    target_from_page_size,
)
from learn_to_draw_api.services.capture_registration_proposal import (
    CaptureRegistrationProposalService,
)


FIXTURE_DIRECTORY = Path(__file__).parent / "fixtures" / "manual_registration_v2"


def _encode_jpeg(image: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok
    return encoded.tobytes()


def _synthetic_page(
    corners: np.ndarray,
    *,
    width: int = 960,
    height: int = 720,
) -> bytes:
    image = np.full((height, width, 3), 25, dtype=np.uint8)
    cv2.fillConvexPoly(image, corners.astype(np.int32), (235, 235, 235))
    return _encode_jpeg(image)


def test_proposal_finds_synthetic_light_page_without_manual_prior():
    expected = np.array(
        [[140.0, 80.0], [800.0, 60.0], [880.0, 640.0], [70.0, 670.0]],
        dtype=np.float32,
    )

    result = CaptureRegistrationProposalService().propose(
        content=_synthetic_page(expected),
        expected_width=960,
        expected_height=720,
    )

    assert result.fallback_reason is None
    assert result.corners is not None
    proposed = np.array(
        [
            result.corners.top_left,
            result.corners.top_right,
            result.corners.bottom_right,
            result.corners.bottom_left,
        ]
    )
    assert proposed == pytest.approx(expected, abs=1.0)
    assert result.stability_max_px is not None
    assert result.stability_max_px < 0.2


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        (
            _encode_jpeg(np.full((480, 640, 3), 245, dtype=np.uint8)),
            "bright_region_touches_multiple_borders",
        ),
        (
            _synthetic_page(
                np.array([[-30, 80], [800, 60], [880, 640], [-50, 670]]),
            ),
            "physical_corner_outside_capture",
        ),
    ],
)
def test_proposal_declines_missing_or_clipped_pages(content, reason):
    result = CaptureRegistrationProposalService().propose(
        content=content,
        expected_width=640 if reason.startswith("bright") else 960,
        expected_height=480 if reason.startswith("bright") else 720,
    )

    assert result.corners is None
    assert result.stability_max_px is None
    assert result.fallback_reason == reason


def test_proposal_declines_threshold_instability(monkeypatch):
    service = CaptureRegistrationProposalService()
    base = np.array(
        [[140.0, 80.0], [800.0, 60.0], [880.0, 640.0], [70.0, 670.0]],
        dtype=np.float32,
    )
    proposals = [base.copy() for _ in range(5)]
    proposals[-1][2] += np.array([30.0, 30.0])

    def unstable_proposal(**_kwargs):
        return proposals.pop(0), None

    monkeypatch.setattr(service, "_proposal_at_threshold", unstable_proposal)
    result = service.propose(
        content=_synthetic_page(base),
        expected_width=960,
        expected_height=720,
    )

    assert result.corners is None
    assert result.fallback_reason == "unstable_across_thresholds"


def test_real_fixture_proposal_improves_rigid_aligned_checkpoint_geometry():
    ground_truth = json.loads(
        (FIXTURE_DIRECTORY / "us_letter_landscape_c930e.json").read_text()
    )
    source = ground_truth["source"]
    capture = (FIXTURE_DIRECTORY / source["capture_file"]).read_bytes()
    proposal = CaptureRegistrationProposalService().propose(
        content=capture,
        expected_width=source["capture_width_px"],
        expected_height=source["capture_height_px"],
    )

    assert proposal.corners is not None
    assert proposal.fallback_reason is None
    assert proposal.stability_max_px == pytest.approx(0.711, abs=0.01)

    page = ground_truth["page"]
    normalized = CaptureNormalizationService().register_with_corners(
        content=capture,
        target=target_from_page_size(
            page_width_mm=page["width_mm"],
            page_height_mm=page["height_mm"],
            source="prepared_svg",
        ),
        corners=proposal.corners,
    )
    observed_raw = np.array(
        [[checkpoint["observed_raw_px"] for checkpoint in ground_truth["checkpoints"]]],
        dtype=np.float64,
    )
    observed_page_px = cv2.perspectiveTransform(
        observed_raw,
        np.array(normalized.metadata.transform.matrix),
    )[0]
    pixels_per_mm = np.array(
        [
            normalized.metadata.transform.pixels_per_mm_x,
            normalized.metadata.transform.pixels_per_mm_y,
        ]
    )
    observed_page_mm = observed_page_px / pixels_per_mm
    commanded_page_mm = np.array(
        [checkpoint["commanded_page_mm"] for checkpoint in ground_truth["checkpoints"]],
        dtype=np.float64,
    )
    commanded_centered = commanded_page_mm - commanded_page_mm.mean(axis=0)
    observed_centered = observed_page_mm - observed_page_mm.mean(axis=0)
    u, _, vt = np.linalg.svd(commanded_centered.T @ observed_centered)
    rotation = u @ vt
    translation = (
        observed_page_mm.mean(axis=0)
        - commanded_page_mm.mean(axis=0) @ rotation
    )
    checkpoint_errors_mm = np.linalg.norm(
        observed_page_mm - (commanded_page_mm @ rotation + translation),
        axis=1,
    )

    assert checkpoint_errors_mm == pytest.approx(
        [0.589, 0.481, 0.631, 0.631, 0.666],
        abs=0.01,
    )
    assert checkpoint_errors_mm.max() < 0.7
