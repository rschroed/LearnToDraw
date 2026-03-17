from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional

from learn_to_draw_api.config import AppConfig
from learn_to_draw_api.models import (
    InvalidArtifactError,
    MarginsMm,
    PlotArea,
    PlotterWorkspace,
    PlotterWorkspaceRequest,
    SizeMm,
)
from learn_to_draw_api.services.plotter_device_settings import PlotterDeviceSettingsService


class PlotterWorkspaceStore:
    def __init__(self, workspace_dir: Path) -> None:
        self._workspace_dir = workspace_dir
        self._workspace_dir.mkdir(parents=True, exist_ok=True)
        self._file_path = self._workspace_dir / "plotter.json"
        self._lock = Lock()

    def load(self) -> Optional[PlotterWorkspace]:
        if not self._file_path.exists():
            return None
        return PlotterWorkspace.model_validate_json(self._file_path.read_text(encoding="utf-8"))

    def save(self, workspace: PlotterWorkspace) -> PlotterWorkspace:
        with self._lock:
            temp_path = self._file_path.with_suffix(".tmp")
            temp_path.write_text(workspace.model_dump_json(indent=2), encoding="utf-8")
            temp_path.replace(self._file_path)
        return workspace


class PlotterWorkspaceService:
    def __init__(
        self,
        *,
        store: PlotterWorkspaceStore,
        config: AppConfig,
        device_settings_service: PlotterDeviceSettingsService,
    ) -> None:
        self._store = store
        self._device_settings_service = device_settings_service
        self._default_request = PlotterWorkspaceRequest(
            page_width_mm=config.plot_page_width_mm,
            page_height_mm=config.plot_page_height_mm,
            margin_left_mm=config.plot_margin_left_mm,
            margin_top_mm=config.plot_margin_top_mm,
            margin_right_mm=config.plot_margin_right_mm,
            margin_bottom_mm=config.plot_margin_bottom_mm,
        )

    def current(self) -> PlotterWorkspace:
        persisted = self._store.load()
        if persisted is not None:
            return self._validate_workspace(persisted, source="persisted")
        return self._build_workspace(
            self._default_request,
            source="config_default",
            updated_at=datetime.now(timezone.utc),
        )

    def current_plot_area(self) -> PlotArea:
        return self.current().to_plot_area()

    def save(self, request: PlotterWorkspaceRequest) -> PlotterWorkspace:
        workspace = self._build_workspace(
            request,
            source="persisted",
            updated_at=datetime.now(timezone.utc),
        )
        self._store.save(workspace)
        return workspace

    def _build_workspace(
        self,
        request: PlotterWorkspaceRequest,
        *,
        source: str,
        updated_at: datetime,
    ) -> PlotterWorkspace:
        device_settings = self._device_settings_service.current()
        plot_area = PlotArea(
            page_width_mm=request.page_width_mm,
            page_height_mm=request.page_height_mm,
            margin_left_mm=request.margin_left_mm,
            margin_top_mm=request.margin_top_mm,
            margin_right_mm=request.margin_right_mm,
            margin_bottom_mm=request.margin_bottom_mm,
        )
        self._validate_plot_area(plot_area, device_settings.plotter_bounds_mm)
        return PlotterWorkspace(
            plotter_bounds_mm=device_settings.plotter_bounds_mm,
            page_size_mm=SizeMm(
                width_mm=plot_area.page_width_mm,
                height_mm=plot_area.page_height_mm,
            ),
            margins_mm=MarginsMm(
                left_mm=plot_area.margin_left_mm,
                top_mm=plot_area.margin_top_mm,
                right_mm=plot_area.margin_right_mm,
                bottom_mm=plot_area.margin_bottom_mm,
            ),
            drawable_area_mm=SizeMm(
                width_mm=round(plot_area.draw_width_mm, 3),
                height_mm=round(plot_area.draw_height_mm, 3),
            ),
            updated_at=updated_at,
            source=source,
        )

    def _validate_workspace(
        self,
        workspace: PlotterWorkspace,
        *,
        source: str,
    ) -> PlotterWorkspace:
        return self._build_workspace(
            PlotterWorkspaceRequest(
                page_width_mm=workspace.page_size_mm.width_mm,
                page_height_mm=workspace.page_size_mm.height_mm,
                margin_left_mm=workspace.margins_mm.left_mm,
                margin_top_mm=workspace.margins_mm.top_mm,
                margin_right_mm=workspace.margins_mm.right_mm,
                margin_bottom_mm=workspace.margins_mm.bottom_mm,
            ),
            source=source,
            updated_at=workspace.updated_at,
        )

    def _validate_plot_area(self, plot_area: PlotArea, plotter_bounds: SizeMm) -> None:
        if plot_area.page_width_mm > plotter_bounds.width_mm:
            raise InvalidArtifactError(
                "Configured page width exceeds the plotter bounds width."
            )
        if plot_area.page_height_mm > plotter_bounds.height_mm:
            raise InvalidArtifactError(
                "Configured page height exceeds the plotter bounds height."
            )
        if plot_area.draw_width_mm <= 0 or plot_area.draw_height_mm <= 0:
            raise InvalidArtifactError(
                "Configured margins must leave a positive drawable area."
            )
