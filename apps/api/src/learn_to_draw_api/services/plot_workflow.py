from __future__ import annotations

import copy
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
    PlotPreparationMetadata,
    PlotRun,
    PlotRunListResponse,
    PlotSizingMode,
    PlotRunSummary,
    PlotStageState,
    PlotterDeviceSettings,
    PlotterWorkspace,
)
from learn_to_draw_api.services.captures import CaptureStore
from learn_to_draw_api.services.plotter_calibration import PlotterCalibrationService
from learn_to_draw_api.services.plotter_device_settings import PlotterDeviceSettingsService
from learn_to_draw_api.services.plotter_workspace import PlotterWorkspaceService


ACTIVE_RUN_STATUSES = {"pending", "plotting", "capturing"}
SVG_MIME_TYPE = "image/svg+xml"
PATTERNS_DIR = Path(__file__).resolve().parent.parent / "assets" / "patterns"

ET.register_namespace("", "http://www.w3.org/2000/svg")


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

    def save_prepared_svg(self, run_id: str, svg_text: str) -> Path:
        with self._lock:
            prepared_path = self._runs_dir / f"{run_id}-prepared.svg"
            prepared_path.write_text(svg_text, encoding="utf-8")
        return prepared_path

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
        calibration_service: PlotterCalibrationService,
        device_settings_service: PlotterDeviceSettingsService,
        workspace_service: PlotterWorkspaceService,
    ) -> None:
        self._plotter = plotter
        self._camera = camera
        self._capture_store = capture_store
        self._asset_store = asset_store
        self._run_store = run_store
        self._calibration_service = calibration_service
        self._device_settings_service = device_settings_service
        self._workspace_service = workspace_service
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
        sizing_mode: PlotSizingMode = "native",
    ) -> PlotRun:
        asset = self._asset_store.get(asset_id)
        now = datetime.now(timezone.utc)
        run = PlotRun(
            id=uuid4().hex,
            status="pending",
            purpose=purpose,
            capture_mode=capture_mode,
            sizing_mode=sizing_mode,
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
            workspace = self._workspace_service.current()
            device_settings = self._device_settings_service.current()
            document, preparation = self._load_document(
                run.asset,
                sizing_mode=run.sizing_mode,
                workspace=workspace,
                device_settings=device_settings,
            )
            prepared_svg_path = self._run_store.save_prepared_svg(run.id, document.svg_text)
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
            effective_calibration = self._calibration_service.current()
            run.plotter_run_details = {
                "driver": self._plotter.driver,
                "document_id": plot_result.document_id,
                "prepared_svg_path": str(prepared_svg_path),
                "preparation": preparation.model_dump(mode="json"),
                "calibration": effective_calibration.model_dump(mode="json"),
                "device": device_settings.model_dump(mode="json"),
                "workspace": workspace.model_dump(mode="json"),
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

    def _load_document(
        self,
        asset: PlotAsset,
        *,
        sizing_mode: PlotSizingMode,
        workspace: PlotterWorkspace,
        device_settings: PlotterDeviceSettings,
    ) -> tuple[PlotDocument, PlotPreparationMetadata]:
        if self._plotter.driver == "axidraw-pyapi" and sizing_mode == "fit_to_draw_area":
            raise InvalidArtifactError(
                "Fit within drawable area is temporarily disabled for real AxiDraw plotting "
                "because the prepared SVG can exceed safe machine bounds. Use authored size "
                "only for SVGs with explicit physical units."
            )
        svg_text = Path(asset.file_path).read_text(encoding="utf-8")
        root = _parse_svg_root(svg_text)
        prepared_svg_text, preparation = _prepare_svg_for_plotting(
            svg_text,
            root,
            sizing_mode=sizing_mode,
            plot_area=workspace.to_plot_area(),
            device_settings=device_settings,
        )
        width, height = _extract_svg_dimensions(root)
        document = PlotDocument(
            asset_id=asset.id,
            name=asset.name,
            svg_text=prepared_svg_text,
            width=width,
            height=height,
            prepared_width_mm=preparation.prepared_width_mm,
            prepared_height_mm=preparation.prepared_height_mm,
        )
        return document, preparation

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
    view_box = _parse_view_box(root.attrib.get("viewBox"))
    if view_box:
        width = width or max(1, int(round(view_box[2])))
        height = height or max(1, int(round(view_box[3])))
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


def _prepare_svg_for_plotting(
    svg_text: str,
    root: ET.Element,
    *,
    sizing_mode: PlotSizingMode,
    plot_area: PlotArea,
    device_settings: PlotterDeviceSettings,
) -> tuple[str, PlotPreparationMetadata]:
    source_box = _extract_source_box(root)
    source_units = _classify_source_units(root)
    units_inferred = source_units in {"unitless", "px", "unknown"}

    if sizing_mode == "native":
        if source_box.physical_width_mm is None or source_box.physical_height_mm is None:
            raise InvalidArtifactError(
                "Native sizing requires explicit physical SVG dimensions such as mm, cm, or in."
            )
        prepared_width_mm = source_box.physical_width_mm
        prepared_height_mm = source_box.physical_height_mm
        if (
            prepared_width_mm > plot_area.draw_width_mm
            or prepared_height_mm > plot_area.draw_height_mm
        ):
            raise InvalidArtifactError(
                "Authored SVG size "
                f"{_format_mm(prepared_width_mm)} x {_format_mm(prepared_height_mm)} mm "
                "exceeds the current drawable area of "
                f"{_format_mm(plot_area.draw_width_mm)} x {_format_mm(plot_area.draw_height_mm)} mm."
            )
        prepared_svg_text = svg_text
    else:
        if source_box.view_box_width <= 0 or source_box.view_box_height <= 0:
            raise InvalidArtifactError("SVG content is missing usable size information.")
        scale = min(
            plot_area.draw_width_mm / source_box.view_box_width,
            plot_area.draw_height_mm / source_box.view_box_height,
        )
        prepared_width_mm = source_box.view_box_width * scale
        prepared_height_mm = source_box.view_box_height * scale
        prepared_svg_text = _build_prepared_svg(
            root,
            plot_area=plot_area,
            source_box=source_box,
            scale=scale,
        )
    return (
        prepared_svg_text,
        PlotPreparationMetadata(
            source_width=source_box.reported_width,
            source_height=source_box.reported_height,
            source_units=source_units,
            prepared_width_mm=round(prepared_width_mm, 3),
            prepared_height_mm=round(prepared_height_mm, 3),
            page_width_mm=round(plot_area.page_width_mm, 3),
            page_height_mm=round(plot_area.page_height_mm, 3),
            drawable_width_mm=round(plot_area.draw_width_mm, 3),
            drawable_height_mm=round(plot_area.draw_height_mm, 3),
            plotter_bounds_width_mm=round(device_settings.plotter_bounds_mm.width_mm, 3),
            plotter_bounds_height_mm=round(device_settings.plotter_bounds_mm.height_mm, 3),
            plotter_bounds_source=device_settings.plotter_bounds_source,
            plotter_model_code=(
                device_settings.plotter_model.code
                if device_settings.plotter_model is not None
                else None
            ),
            plotter_model_label=(
                device_settings.plotter_model.label
                if device_settings.plotter_model is not None
                else None
            ),
            sizing_mode=sizing_mode,
            units_inferred=units_inferred,
        ),
    )


class _SourceBox:
    def __init__(
        self,
        *,
        reported_width: float,
        reported_height: float,
        physical_width_mm: Optional[float],
        physical_height_mm: Optional[float],
        view_box_min_x: float,
        view_box_min_y: float,
        view_box_width: float,
        view_box_height: float,
    ) -> None:
        self.reported_width = reported_width
        self.reported_height = reported_height
        self.physical_width_mm = physical_width_mm
        self.physical_height_mm = physical_height_mm
        self.view_box_min_x = view_box_min_x
        self.view_box_min_y = view_box_min_y
        self.view_box_width = view_box_width
        self.view_box_height = view_box_height


def _extract_source_box(root: ET.Element) -> _SourceBox:
    width_length = _parse_svg_length(root.attrib.get("width"))
    height_length = _parse_svg_length(root.attrib.get("height"))
    view_box = _parse_view_box(root.attrib.get("viewBox"))

    if view_box is not None:
        min_x, min_y, view_box_width, view_box_height = view_box
    else:
        if width_length is None or height_length is None:
            raise InvalidArtifactError("SVG content is missing width/height or viewBox values.")
        min_x = 0.0
        min_y = 0.0
        view_box_width = width_length[0]
        view_box_height = height_length[0]

    reported_width = width_length[0] if width_length is not None else view_box_width
    reported_height = height_length[0] if height_length is not None else view_box_height
    physical_width_mm = _length_to_mm(width_length)
    physical_height_mm = _length_to_mm(height_length)

    return _SourceBox(
        reported_width=reported_width,
        reported_height=reported_height,
        physical_width_mm=physical_width_mm,
        physical_height_mm=physical_height_mm,
        view_box_min_x=min_x,
        view_box_min_y=min_y,
        view_box_width=view_box_width,
        view_box_height=view_box_height,
    )


def _build_prepared_svg(
    root: ET.Element,
    *,
    plot_area: PlotArea,
    source_box: _SourceBox,
    scale: float,
) -> str:
    page_width_mm = _format_mm(plot_area.page_width_mm)
    page_height_mm = _format_mm(plot_area.page_height_mm)
    expanded_view_box_width = plot_area.page_width_mm / scale
    expanded_view_box_height = plot_area.page_height_mm / scale
    expanded_view_box_min_x = source_box.view_box_min_x - (plot_area.margin_left_mm / scale)
    expanded_view_box_min_y = source_box.view_box_min_y - (plot_area.margin_top_mm / scale)

    root_copy = copy.deepcopy(root)
    root_copy.attrib["width"] = f"{page_width_mm}mm"
    root_copy.attrib["height"] = f"{page_height_mm}mm"
    root_copy.attrib["viewBox"] = (
        f"{_format_numeric(expanded_view_box_min_x)} "
        f"{_format_numeric(expanded_view_box_min_y)} "
        f"{_format_numeric(expanded_view_box_width)} "
        f"{_format_numeric(expanded_view_box_height)}"
    )
    return ET.tostring(root_copy, encoding="unicode")


def _classify_source_units(root: ET.Element) -> str:
    width_length = _parse_svg_length(root.attrib.get("width"))
    height_length = _parse_svg_length(root.attrib.get("height"))
    units = {
        length[1]
        for length in (width_length, height_length)
        if length is not None and length[1] is not None
    }
    if not units:
        if width_length is None and height_length is None:
            return "unknown"
        return "unitless"
    if len(units) > 1:
        return "mixed"
    return next(iter(units))


def _parse_svg_length(value: Optional[str]) -> Optional[tuple[float, Optional[str]]]:
    if value is None:
        return None
    match = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*([A-Za-z%]+)?\s*$", value)
    if not match:
        return None
    unit = (match.group(2) or "").lower() or None
    if unit == "%":
        return None
    return float(match.group(1)), unit


def _length_to_mm(length: Optional[tuple[float, Optional[str]]]) -> Optional[float]:
    if length is None:
        return None
    value, unit = length
    if unit == "mm":
        return value
    if unit == "cm":
        return value * 10.0
    if unit == "in":
        return value * 25.4
    return None


def _parse_view_box(value: Optional[str]) -> Optional[tuple[float, float, float, float]]:
    if not value:
        return None
    parts = re.split(r"[,\s]+", value.strip())
    if len(parts) != 4:
        return None
    try:
        min_x, min_y, width, height = (float(part) for part in parts)
    except ValueError:
        return None
    return min_x, min_y, width, height


def _format_numeric(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _format_mm(value: float) -> str:
    return _format_numeric(value)


def _pattern_definition(pattern_id: str) -> Optional[dict[str, str]]:
    patterns = {
        "test-grid": {
            "name": "Test grid",
            "filename": "test-grid.svg",
        },
        "tiny-square": {
            "name": "Tiny square",
            "filename": "tiny-square.svg",
        },
        "dash-row": {
            "name": "Dash row",
            "filename": "dash-row.svg",
        },
        "double-box": {
            "name": "Double box",
            "filename": "double-box.svg",
        },
    }
    pattern = patterns.get(pattern_id)
    if pattern is None:
        return None
    return {
        "name": pattern["name"],
        "svg_text": (PATTERNS_DIR / pattern["filename"]).read_text(encoding="utf-8"),
    }
