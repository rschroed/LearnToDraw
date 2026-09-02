from __future__ import annotations

from dataclasses import dataclass

from learn_to_draw_api.models import (
    NormalizationMetadata,
    NormalizationTargetFrameSource,
)


CANONICAL_LONG_SIDE_PX = 2048
CANONICAL_PAGE_BACKGROUND_COLOR = (255, 255, 255)


@dataclass(frozen=True)
class NormalizationTarget:
    page_width_mm: float
    page_height_mm: float
    source: NormalizationTargetFrameSource

    @property
    def aspect_ratio(self) -> float:
        return self.page_width_mm / self.page_height_mm


@dataclass(frozen=True)
class NormalizationArtifacts:
    rectified_color: bytes
    rectified_grayscale: bytes
    debug_overlay: bytes
    metadata: NormalizationMetadata
