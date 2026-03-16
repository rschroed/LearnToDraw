from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from threading import Lock, Thread
from typing import Optional
from urllib.parse import quote
from uuid import uuid4
import xml.etree.ElementTree as ET

from learn_to_draw_api.adapters.camera import CameraAdapter
from learn_to_draw_api.adapters.plotter import PlotterAdapter
from learn_to_draw_api.models import (
    AppConflictError,
    AppNotFoundError,
    CaptureMetadata,
    InvalidArtifactError,
    PatternAssetCreateRequest,
    PlotAsset,
    PlotRunCaptureMode,
    PlotRunPurpose,
    PlotDocument,
    PlotRun,
    PlotRunListResponse,
    PlotRunSummary,
    PlotStageState,
)
from learn_to_draw_api.services.captures import CaptureStore


ACTIVE_RUN_STATUSES = {"pending", "plotting", "capturing"}
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


class PlotRunStore:
    def __init__(self, runs_dir: Path) -> None:
        self._runs_dir = runs_dir
        self._runs_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, PlotRun] = {}
        self._lock = Lock()

    def save(self, run: PlotRun) -> PlotRun:
        with self._lock:
            metadata_path = self._runs_dir / f"{run.id}.json"
            metadata_path.write_text(run.model_dump_json(indent=2), encoding="utf-8")
            self._cache[run.id] = run
        return run

    def get(self, run_id: str) -> PlotRun:
        cached = self._cache.get(run_id)
        if cached is not None:
            return cached
        metadata_path = self._runs_dir / f"{run_id}.json"
        if not metadata_path.exists():
            raise AppNotFoundError(f"Plot run '{run_id}' was not found.")
        run = PlotRun.model_validate_json(metadata_path.read_text(encoding="utf-8"))
        self._cache[run_id] = run
        return run

    def latest(self) -> Optional[PlotRun]:
        runs = self.list_full_runs()
        return runs[0] if runs else None

    def list_full_runs(self) -> list[PlotRun]:
        runs: list[PlotRun] = []
        for metadata_path in self._runs_dir.glob("*.json"):
            run = PlotRun.model_validate_json(metadata_path.read_text(encoding="utf-8"))
            self._cache[run.id] = run
            runs.append(run)
        runs.sort(key=lambda run: run.created_at, reverse=True)
        return runs

    def list_summaries(self) -> PlotRunListResponse:
        return PlotRunListResponse(
            runs=[PlotRunSummary.from_run(run) for run in self.list_full_runs()]
        )


class PlotWorkflowService:
    def __init__(
        self,
        *,
        plotter: PlotterAdapter,
        camera: CameraAdapter,
        capture_store: CaptureStore,
        asset_store: PlotAssetStore,
        run_store: PlotRunStore,
    ) -> None:
        self._plotter = plotter
        self._camera = camera
        self._capture_store = capture_store
        self._asset_store = asset_store
        self._run_store = run_store
        self._lock = Lock()
        self._active_run_id: Optional[str] = None

    def create_uploaded_asset(
        self,
        *,
        filename: str,
        content: bytes,
        content_type: Optional[str],
    ) -> PlotAsset:
        if not filename:
            raise InvalidArtifactError("An SVG filename is required.")
        if content_type and "svg" not in content_type.lower() and not filename.lower().endswith(
            ".svg"
        ):
            raise InvalidArtifactError("Only SVG uploads are supported.")
        try:
            svg_text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InvalidArtifactError("Uploaded SVG must be valid UTF-8.") from exc
        _parse_svg_root(svg_text)
        display_name = Path(filename).stem or filename
        return self._asset_store.save_svg(
            svg_text=svg_text,
            name=display_name,
            kind="uploaded_svg",
        )

    def create_pattern_asset(self, request: PatternAssetCreateRequest) -> PlotAsset:
        pattern = _pattern_definition(request.pattern_id)
        if pattern is None:
            raise InvalidArtifactError(f"Unsupported pattern_id '{request.pattern_id}'.")
        return self._asset_store.save_svg(
            svg_text=pattern["svg_text"],
            name=pattern["name"],
            kind="built_in_pattern",
            pattern_id=request.pattern_id,
        )

    def get_asset(self, asset_id: str) -> PlotAsset:
        return self._asset_store.get(asset_id)

    def create_run(
        self,
        asset_id: str,
        *,
        purpose: PlotRunPurpose = "normal",
        capture_mode: PlotRunCaptureMode = "auto",
    ) -> PlotRun:
        asset = self._asset_store.get(asset_id)
        now = datetime.now(timezone.utc)
        run = PlotRun(
            id=uuid4().hex,
            status="pending",
            purpose=purpose,
            capture_mode=capture_mode,
            created_at=now,
            updated_at=now,
            asset=asset,
            stage_states={
                "prepare": PlotStageState(status="pending"),
                "plot": PlotStageState(status="pending"),
                "capture": PlotStageState(status="pending"),
            },
        )
        with self._lock:
            active_run = self._get_active_run_locked()
            if active_run is not None and active_run.status in ACTIVE_RUN_STATUSES:
                raise AppConflictError("A plot run is already active.")
            self._active_run_id = run.id
            self._run_store.save(run)
            worker = Thread(target=self._execute_run, args=(run.id,), daemon=True)
            worker.start()
        return run

    def latest_run(self) -> Optional[PlotRun]:
        return self._run_store.latest()

    def list_runs(self) -> PlotRunListResponse:
        return self._run_store.list_summaries()

    def get_run(self, run_id: str) -> PlotRun:
        return self._run_store.get(run_id)

    def _execute_run(self, run_id: str) -> None:
        current_stage: Optional[str] = None
        run = self._run_store.get(run_id)
        try:
            current_stage = "prepare"
            run = self._set_stage_state(
                run,
                stage="prepare",
                status="in_progress",
                message="Preparing SVG document.",
            )
            document = self._load_document(run.asset)
            run = self._set_stage_state(
                run,
                stage="prepare",
                status="completed",
                message="SVG document prepared.",
            )

            current_stage = "plot"
            run.status = "plotting"
            run.updated_at = datetime.now(timezone.utc)
            run = self._set_stage_state(
                run,
                stage="plot",
                status="in_progress",
                message="Sending SVG to plotter.",
            )
            plot_result = self._plotter.plot(document)
            run.plotter_run_details = {
                "driver": self._plotter.driver,
                "document_id": plot_result.document_id,
                "duration_ms": _duration_ms(
                    plot_result.started_at,
                    plot_result.completed_at,
                ),
                "details": plot_result.details,
            }
            run = self._set_stage_state(
                run,
                stage="plot",
                status="completed",
                message="Plot completed.",
            )

            current_stage = "capture"
            if run.capture_mode == "skip":
                run.camera_run_details = {
                    "capture_mode": "skip",
                }
                run = self._set_stage_state(
                    run,
                    stage="capture",
                    status="completed",
                    message="Capture skipped for diagnostic run.",
                )
            else:
                run.status = "capturing"
                run.updated_at = datetime.now(timezone.utc)
                run = self._set_stage_state(
                    run,
                    stage="capture",
                    status="in_progress",
                    message="Capturing plotted page.",
                )
                capture_started = datetime.now(timezone.utc)
                capture_artifact = self._camera.capture()
                capture_completed = datetime.now(timezone.utc)
                capture_metadata = self._capture_store.save(capture_artifact)
                run.capture = capture_metadata
                run.camera_run_details = {
                    "driver": self._camera.driver,
                    "capture_id": capture_metadata.id,
                    "resolution": f"{capture_metadata.width}x{capture_metadata.height}",
                    "duration_ms": _duration_ms(capture_started, capture_completed),
                }
                run = self._set_stage_state(
                    run,
                    stage="capture",
                    status="completed",
                    message="Capture completed.",
                )

            run.status = "completed"
            run.error = None
            run.updated_at = datetime.now(timezone.utc)
            self._run_store.save(run)
        except Exception as exc:
            run.status = "failed"
            run.error = str(exc)
            run.updated_at = datetime.now(timezone.utc)
            if current_stage is not None:
                run = self._set_stage_state(
                    run,
                    stage=current_stage,
                    status="failed",
                    message=str(exc),
                )
            else:
                self._run_store.save(run)
        finally:
            with self._lock:
                if self._active_run_id == run_id:
                    self._active_run_id = None

    def _load_document(self, asset: PlotAsset) -> PlotDocument:
        svg_text = Path(asset.file_path).read_text(encoding="utf-8")
        root = _parse_svg_root(svg_text)
        width, height = _extract_svg_dimensions(root)
        return PlotDocument(
            asset_id=asset.id,
            name=asset.name,
            svg_text=svg_text,
            width=width,
            height=height,
        )

    def _set_stage_state(
        self,
        run: PlotRun,
        *,
        stage: str,
        status: str,
        message: str,
    ) -> PlotRun:
        previous = run.stage_states[stage]
        now = datetime.now(timezone.utc)
        run.stage_states[stage] = PlotStageState(
            status=status,
            started_at=previous.started_at or (now if status == "in_progress" else None),
            completed_at=now if status in {"completed", "failed"} else None,
            message=message,
        )
        run.updated_at = now
        self._run_store.save(run)
        return run

    def _get_active_run_locked(self) -> Optional[PlotRun]:
        if self._active_run_id is None:
            return None
        try:
            active_run = self._run_store.get(self._active_run_id)
        except AppNotFoundError:
            self._active_run_id = None
            return None
        if active_run.status not in ACTIVE_RUN_STATUSES:
            self._active_run_id = None
            return None
        return active_run


def _slugify_name(name: str) -> str:
    stem = Path(name).stem or name
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-_.").lower()
    return normalized or "plot-asset"


def _parse_svg_root(svg_text: str) -> ET.Element:
    if not svg_text.strip():
        raise InvalidArtifactError("SVG content cannot be empty.")
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as exc:
        raise InvalidArtifactError("Provided content is not valid XML/SVG.") from exc
    if not root.tag.lower().endswith("svg"):
        raise InvalidArtifactError("Provided content is not an SVG document.")
    return root


def _extract_svg_dimensions(root: ET.Element) -> tuple[int, int]:
    width = _coerce_svg_dimension(root.attrib.get("width"))
    height = _coerce_svg_dimension(root.attrib.get("height"))
    if width and height:
        return width, height
    view_box = root.attrib.get("viewBox")
    if view_box:
        parts = re.split(r"[,\s]+", view_box.strip())
        if len(parts) == 4:
            width = width or _coerce_svg_dimension(parts[2])
            height = height or _coerce_svg_dimension(parts[3])
    return width or 1000, height or 1000


def _coerce_svg_dimension(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    match = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)", value)
    if not match:
        return None
    return max(1, int(round(float(match.group(1)))))


def _duration_ms(started_at: datetime, completed_at: datetime) -> int:
    return int((completed_at - started_at).total_seconds() * 1000)


def _pattern_definition(pattern_id: str) -> Optional[dict[str, str]]:
    patterns = {
        "test-grid": {
            "name": "Test grid",
            "svg_text": _build_test_grid_svg(),
        },
        "tiny-square": {
            "name": "Tiny square",
            "svg_text": _build_tiny_square_svg(),
        },
        "dash-row": {
            "name": "Dash row",
            "svg_text": _build_dash_row_svg(),
        },
        "double-box": {
            "name": "Double box",
            "svg_text": _build_double_box_svg(),
        },
    }
    return patterns.get(pattern_id)


def _build_test_grid_svg() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" width="960" height="720" viewBox="0 0 960 720">
  <rect width="100%" height="100%" fill="#f8f3ea" />
  <g stroke="#d0c0aa" stroke-width="1">
    <path d="M 80 100 H 880" />
    <path d="M 80 180 H 880" />
    <path d="M 80 260 H 880" />
    <path d="M 80 340 H 880" />
    <path d="M 80 420 H 880" />
    <path d="M 80 500 H 880" />
    <path d="M 80 580 H 880" />
    <path d="M 160 80 V 640" />
    <path d="M 280 80 V 640" />
    <path d="M 400 80 V 640" />
    <path d="M 520 80 V 640" />
    <path d="M 640 80 V 640" />
    <path d="M 760 80 V 640" />
  </g>
  <g stroke="#1f2933" stroke-width="5" fill="none">
    <rect x="80" y="80" width="800" height="560" rx="18" />
    <circle cx="240" cy="220" r="78" />
    <circle cx="720" cy="220" r="78" />
    <path d="M 220 500 C 330 380, 630 380, 740 500" />
    <path d="M 160 620 L 800 100" />
  </g>
  <g fill="#8b5e34" font-family="Menlo, monospace" font-size="28">
    <text x="96" y="54">Built-in Test Pattern: test-grid</text>
  </g>
</svg>"""


def _build_tiny_square_svg() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120" viewBox="0 0 120 120">
  <rect width="100%" height="100%" fill="#fbf7f0" />
  <path d="M 30 30 H 90 V 90 H 30 Z" stroke="#1f2933" stroke-width="4" fill="none" />
</svg>"""


def _build_dash_row_svg() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" width="180" height="80" viewBox="0 0 180 80">
  <rect width="100%" height="100%" fill="#fbf7f0" />
  <g stroke="#1f2933" stroke-width="4" fill="none">
    <path d="M 18 40 H 30" />
    <path d="M 48 40 H 60" />
    <path d="M 78 40 H 90" />
    <path d="M 108 40 H 120" />
    <path d="M 138 40 H 150" />
  </g>
</svg>"""


def _build_double_box_svg() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" width="180" height="110" viewBox="0 0 180 110">
  <rect width="100%" height="100%" fill="#fbf7f0" />
  <g stroke="#1f2933" stroke-width="4" fill="none">
    <path d="M 20 25 H 68 V 73 H 20 Z" />
    <path d="M 112 25 H 160 V 73 H 112 Z" />
  </g>
</svg>"""
