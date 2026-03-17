from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional

from learn_to_draw_api.adapters.axidraw_models import resolve_axidraw_model_info
from learn_to_draw_api.config import AppConfig
from learn_to_draw_api.models import (
    PlotterBoundsSource,
    PlotterDeviceSettings,
    PlotterModelDescriptor,
    SizeMm,
)


DEFAULT_CONFIG_BOUNDS = SizeMm(width_mm=210.0, height_mm=297.0)


class PlotterDeviceSettingsStore:
    def __init__(self, settings_dir: Path) -> None:
        self._settings_dir = settings_dir
        self._settings_dir.mkdir(parents=True, exist_ok=True)
        self._file_path = self._settings_dir / "plotter.json"
        self._lock = Lock()

    def load(self) -> Optional[PlotterDeviceSettings]:
        if not self._file_path.exists():
            return None
        return PlotterDeviceSettings.model_validate_json(
            self._file_path.read_text(encoding="utf-8")
        )

    def save(self, settings: PlotterDeviceSettings) -> PlotterDeviceSettings:
        with self._lock:
            temp_path = self._file_path.with_suffix(".tmp")
            temp_path.write_text(settings.model_dump_json(indent=2), encoding="utf-8")
            temp_path.replace(self._file_path)
        return settings


class PlotterDeviceSettingsService:
    def __init__(self, *, store: PlotterDeviceSettingsStore, config: AppConfig) -> None:
        self._store = store
        self._config = config

    def current(self) -> PlotterDeviceSettings:
        persisted = self._store.load()
        if persisted is not None:
            return self._validate_settings(persisted, source=persisted.source)
        settings = self._build_default_settings(source="config_default")
        self._store.save(settings)
        return settings

    def _validate_settings(
        self,
        settings: PlotterDeviceSettings,
        *,
        source: str,
    ) -> PlotterDeviceSettings:
        if self._config.plotter_driver.strip().lower() != "axidraw":
            return PlotterDeviceSettings(
                driver=settings.driver,
                plotter_model=None,
                plotter_bounds_mm=self._resolve_effective_bounds(DEFAULT_CONFIG_BOUNDS),
                plotter_bounds_source=self._resolve_bounds_source(
                    driver="mock",
                    has_model=False,
                ),
                updated_at=settings.updated_at,
                source=source,
            )

        model_code = settings.plotter_model.code if settings.plotter_model is not None else None
        model_info = resolve_axidraw_model_info(model_code or self._config.axidraw_model)
        use_model_bounds = source == "persisted" or self._config.axidraw_model is not None
        return PlotterDeviceSettings(
            driver=self._config.plotter_driver,
            plotter_model=PlotterModelDescriptor(code=model_info.code, label=model_info.label),
            plotter_bounds_mm=self._resolve_effective_bounds(
                SizeMm(
                    width_mm=model_info.bounds_width_mm,
                    height_mm=model_info.bounds_height_mm,
                )
                if use_model_bounds
                else DEFAULT_CONFIG_BOUNDS
            ),
            plotter_bounds_source=self._resolve_bounds_source(
                driver=self._config.plotter_driver,
                has_model=use_model_bounds,
            ),
            updated_at=settings.updated_at,
            source=source,
        )

    def _build_default_settings(self, *, source: str) -> PlotterDeviceSettings:
        driver = self._config.plotter_driver.strip().lower()
        updated_at = datetime.now(timezone.utc)
        if driver == "axidraw":
            model_info = resolve_axidraw_model_info(self._config.axidraw_model)
            use_model_bounds = self._config.axidraw_model is not None
            return PlotterDeviceSettings(
                driver=self._config.plotter_driver,
                plotter_model=PlotterModelDescriptor(
                    code=model_info.code,
                    label=model_info.label,
                ),
                plotter_bounds_mm=self._resolve_effective_bounds(
                    SizeMm(
                        width_mm=model_info.bounds_width_mm,
                        height_mm=model_info.bounds_height_mm,
                    )
                    if use_model_bounds
                    else DEFAULT_CONFIG_BOUNDS
                ),
                plotter_bounds_source=self._resolve_bounds_source(
                    driver=self._config.plotter_driver,
                    has_model=use_model_bounds,
                ),
                updated_at=updated_at,
                source=source,
            )
        return PlotterDeviceSettings(
            driver=self._config.plotter_driver,
            plotter_model=None,
            plotter_bounds_mm=self._resolve_effective_bounds(DEFAULT_CONFIG_BOUNDS),
            plotter_bounds_source=self._resolve_bounds_source(driver=driver, has_model=False),
            updated_at=updated_at,
            source=source,
        )

    def _resolve_effective_bounds(self, default_bounds: SizeMm) -> SizeMm:
        width_mm = (
            self._config.plotter_bounds_width_mm
            if self._config.plotter_bounds_width_mm is not None
            else default_bounds.width_mm
        )
        height_mm = (
            self._config.plotter_bounds_height_mm
            if self._config.plotter_bounds_height_mm is not None
            else default_bounds.height_mm
        )
        return SizeMm(width_mm=width_mm, height_mm=height_mm)

    def _resolve_bounds_source(self, *, driver: str, has_model: bool) -> PlotterBoundsSource:
        if (
            self._config.plotter_bounds_width_mm is not None
            or self._config.plotter_bounds_height_mm is not None
        ):
            return "config_override"
        if driver.strip().lower() == "axidraw" and has_model:
            return "model_default"
        return "config_default"
