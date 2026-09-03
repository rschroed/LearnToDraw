from __future__ import annotations

from typing import Optional

from learn_to_draw_api.adapters.camera import CaptureArtifact
from learn_to_draw_api.models import (
    CaptureMetadata,
    CaptureReview,
    CaptureReviewProposal,
    InvalidArtifactError,
    NormalizationCorners,
    NormalizedCaptureArtifacts,
)
from learn_to_draw_api.services.capture_registration_proposal import (
    CaptureRegistrationProposalService,
)
from learn_to_draw_api.services.capture_normalization import (
    CaptureNormalizationService,
    NormalizationTarget,
)
from learn_to_draw_api.services.captures import CaptureStore


class CaptureService:
    def __init__(
        self,
        *,
        store: CaptureStore,
        normalization_service: CaptureNormalizationService,
        proposal_service: CaptureRegistrationProposalService,
    ) -> None:
        self._store = store
        self._normalization_service = normalization_service
        self._proposal_service = proposal_service

    def persist_raw_capture(self, artifact: CaptureArtifact) -> CaptureMetadata:
        return self._store.save(artifact)

    def initial_registration_corners(
        self,
        *,
        image_width: int,
        image_height: int,
    ) -> NormalizationCorners:
        return self._normalization_service.initial_registration_corners(
            image_width=image_width,
            image_height=image_height,
        )

    def propose_registration_corners(
        self,
        *,
        content: bytes,
        image_width: int,
        image_height: int,
    ) -> tuple[NormalizationCorners, CaptureReviewProposal]:
        attempt = self._proposal_service.propose(
            content=content,
            expected_width=image_width,
            expected_height=image_height,
        )
        if attempt.corners is not None:
            try:
                self._normalization_service.validate_registration_corners(
                    corners=attempt.corners,
                    image_width=image_width,
                    image_height=image_height,
                )
            except InvalidArtifactError:
                fallback_reason = "invalid_proposal_geometry"
            else:
                return attempt.corners, CaptureReviewProposal(
                    status="suggested",
                    method="light_page_edges_v1",
                    stability_max_px=attempt.stability_max_px,
                    fallback_reason=None,
                )
        else:
            fallback_reason = attempt.fallback_reason or "proposal_unavailable"

        return self.initial_registration_corners(
            image_width=image_width,
            image_height=image_height,
        ), CaptureReviewProposal(
            status="fallback",
            method="inset_5_percent_v1",
            stability_max_px=None,
            fallback_reason=fallback_reason,
        )

    def save_capture_review(
        self,
        capture_id: str,
        *,
        review: CaptureReview,
    ) -> CaptureMetadata:
        return self._store.save_review(capture_id, review)

    def validate_registration_corners(
        self,
        *,
        corners: NormalizationCorners,
        image_width: int,
        image_height: int,
    ) -> None:
        self._normalization_service.validate_registration_corners(
            corners=corners,
            image_width=image_width,
            image_height=image_height,
        )

    def finalize_capture_with_review(
        self,
        *,
        capture_id: str,
        content: bytes,
        normalization_target: NormalizationTarget,
        corners: NormalizationCorners,
        review: CaptureReview,
    ) -> CaptureMetadata:
        normalized = self._normalization_service.register_with_corners(
            content=content,
            target=normalization_target,
            corners=corners,
        )
        return self._store_normalized_artifacts(
            capture_id,
            normalized=normalized,
            review=review,
        )

    def _store_normalized_artifacts(
        self,
        capture_id: str,
        *,
        normalized,
        review: Optional[CaptureReview] = None,
    ) -> CaptureMetadata:
        stored_artifacts = NormalizedCaptureArtifacts(
            rectified_color_url=self._store.public_url_for_filename(
                f"{capture_id}-rectified-color.png"
            ),
            rectified_grayscale_url=self._store.public_url_for_filename(
                f"{capture_id}-rectified-grayscale.png"
            ),
            debug_overlay_url=self._store.public_url_for_filename(
                f"{capture_id}-debug-overlay.png"
            ),
            metadata=normalized.metadata,
        )
        return self._store.save_normalized(
            capture_id,
            rectified_color=normalized.rectified_color,
            rectified_grayscale=normalized.rectified_grayscale,
            debug_overlay=normalized.debug_overlay,
            normalized=stored_artifacts,
            review=review,
        )
