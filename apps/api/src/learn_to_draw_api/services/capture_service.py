from __future__ import annotations

import logging
from threading import Thread
from typing import Optional

from learn_to_draw_api.adapters.camera import CaptureArtifact
from learn_to_draw_api.models import (
    CaptureMetadata,
    CaptureReview,
    NormalizationCorners,
    NormalizationDiagnostics,
    NormalizationMethod,
    NormalizedCaptureArtifacts,
)
from learn_to_draw_api.services.capture_normalization import (
    CaptureNormalizationProposal,
    CaptureNormalizationService,
    NormalizationTarget,
)
from learn_to_draw_api.services.captures import CaptureStore


logger = logging.getLogger(__name__)


class CaptureService:
    def __init__(
        self,
        *,
        store: CaptureStore,
        normalization_service: CaptureNormalizationService,
    ) -> None:
        self._store = store
        self._normalization_service = normalization_service

    def persist_raw_capture(self, artifact: CaptureArtifact) -> CaptureMetadata:
        return self._store.save(artifact)

    def persist_capture(
        self,
        artifact: CaptureArtifact,
        *,
        normalization_target: Optional[NormalizationTarget],
        background: bool,
    ) -> CaptureMetadata:
        metadata = self._store.save(artifact)
        if normalization_target is None:
            return metadata
        if background:
            worker = Thread(
                target=self._normalize_and_store,
                kwargs={
                    "capture_id": metadata.id,
                    "content": artifact.content,
                    "normalization_target": normalization_target,
                },
                daemon=True,
            )
            worker.start()
            return metadata
        return self._normalize_and_store(
            capture_id=metadata.id,
            content=artifact.content,
            normalization_target=normalization_target,
        )

    def _normalize_and_store(
        self,
        *,
        capture_id: str,
        content: bytes,
        normalization_target: NormalizationTarget,
    ) -> CaptureMetadata:
        try:
            normalized = self._normalization_service.normalize(
                content=content,
                target=normalization_target,
            )
            return self._store_normalized_artifacts(
                capture_id,
                normalized=normalized,
            )
        except Exception:
            logger.exception("Capture normalization failed for '%s'.", capture_id)
            metadata = self._store.get(capture_id)
            if metadata is None:
                raise
            return metadata

    def inspect_capture(
        self,
        *,
        content: bytes,
        normalization_target: NormalizationTarget,
    ) -> CaptureNormalizationProposal:
        return self._normalization_service.inspect(
            content=content,
            target=normalization_target,
        )

    def save_capture_review(
        self,
        capture_id: str,
        *,
        review: CaptureReview,
    ) -> CaptureMetadata:
        return self._store.save_review(capture_id, review)

    def finalize_capture_with_review(
        self,
        *,
        capture_id: str,
        content: bytes,
        normalization_target: NormalizationTarget,
        corners: NormalizationCorners,
        method: NormalizationMethod,
        confidence: float,
        diagnostics: Optional[NormalizationDiagnostics],
        review: CaptureReview,
    ) -> CaptureMetadata:
        normalized = self._normalization_service.normalize_with_corners(
            content=content,
            target=normalization_target,
            corners=corners,
            method=method,
            confidence=confidence,
            diagnostics=diagnostics,
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
