from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Optional
from urllib.parse import quote
from uuid import uuid4

from learn_to_draw_api.models import AppNotFoundError, PlotAsset


SVG_MIME_TYPE = "image/svg+xml"


class PlotAssetStore:
    def __init__(self, assets_dir: Path, assets_url_prefix: str) -> None:
        self._assets_dir = assets_dir
        normalized_prefix = assets_url_prefix.strip() or "/plot-assets"
        if not normalized_prefix.startswith("/"):
            normalized_prefix = f"/{normalized_prefix}"
        self._assets_url_prefix = normalized_prefix.rstrip("/") or "/plot-assets"
        self._assets_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, PlotAsset] = {}

    def save_svg(
        self,
        *,
        svg_text: str,
        name: str,
        kind: str,
        pattern_id: Optional[str] = None,
    ) -> PlotAsset:
        timestamp = datetime.now(timezone.utc)
        asset_id = uuid4().hex
        safe_name = _slugify_name(name)
        filename = f"{asset_id}-{safe_name}.svg"
        file_path = self._assets_dir / filename
        metadata_path = self._assets_dir / f"{asset_id}.json"
        file_path.write_text(svg_text, encoding="utf-8")
        asset = PlotAsset(
            id=asset_id,
            kind=kind,
            pattern_id=pattern_id,
            name=name,
            timestamp=timestamp,
            file_path=str(file_path),
            public_url=f"{self._assets_url_prefix}/{quote(filename)}",
            mime_type=SVG_MIME_TYPE,
        )
        metadata_path.write_text(asset.model_dump_json(indent=2), encoding="utf-8")
        self._cache[asset_id] = asset
        return asset

    def get(self, asset_id: str) -> PlotAsset:
        cached = self._cache.get(asset_id)
        if cached is not None:
            return cached
        metadata_path = self._assets_dir / f"{asset_id}.json"
        if not metadata_path.exists():
            raise AppNotFoundError(f"Plot asset '{asset_id}' was not found.")
        asset = PlotAsset.model_validate_json(metadata_path.read_text(encoding="utf-8"))
        self._cache[asset_id] = asset
        return asset


def _slugify_name(name: str) -> str:
    stem = Path(name).stem or name
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-_.").lower()
    return normalized or "plot-asset"
