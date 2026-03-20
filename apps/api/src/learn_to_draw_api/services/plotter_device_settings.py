from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional

from learn_to_draw_api.adapters.axidraw_models import (
    AxiDrawModelInfo,
    resolve_axidraw_model_info,
)
from learn_to_draw_api.config import AppConfig
from learn_to_draw_api.models import (
    HardwareUnavailableError,
    InvalidArtifactError,
    NominalPlotterBoundsSource,
    PlotterBoundsSource,
    PlotterDeviceSettings,
    PlotterDeviceSettingsRecord,
    PlotterModelDescriptor,
    SizeMm,
)


DEFAULT_CONFIG_BOUNDS = SizeMm(width_mm=210.0, height_mm=297.0)
DEFAULT_SAFE_CLEARANCE_RIGHT_MM = 10.0
DEFAULT_SAFE_CLEARANCE_BOTTOM_MM = 10.0


class PlotterDeviceSettingsStore:
    def __init__(self, settings_dir: Path) -> None:
        self._settings_dir = settings_dir
        self._settings_dir.mkdir(parents=True, exist_ok=True)
        self._file_path = self._settings_dir / "plotter.json"
        self._lock = Lock()

    def load(self) -> Optional[PlotterDeviceSettingsRecord]:
        if not self._file_path.exists():
            return None
        return PlotterDeviceSettingsRecord.model_validate_json(
            self._file_path.read_text(encoding="utf-8")
        )

    def save(self, settings: PlotterDeviceSettingsRecord) -> PlotterDeviceSettingsRecord:
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
        driver = self._config.plotter_driver.strip().lower()
        persisted = self._store.load()
        if driver == "axidraw":
            settings = self._build_current_axidraw_settings(
                source=persisted.source if persisted is not None else "config_default",
                updated_at=persisted.updated_at if persisted is not None else datetime.now(timezone.utc),
                manual_safe_bounds_override_mm=(
                    persisted.manual_safe_bounds_override_mm if persisted is not None else None
                ),
            )
            self._store.save(
                PlotterDeviceSettingsRecord(
                    source=settings.source,
                    updated_at=settings.updated_at,
                    manual_safe_bounds_override_mm=(
                        persisted.manual_safe_bounds_override_mm if persisted is not None else None
                    ),
                )
            )
            return settings
        if persisted is not None:
            return self._validate_settings(persisted, source=persisted.source)
        settings = self._build_default_settings(source="config_default")
        self._store.save(
            PlotterDeviceSettingsRecord(
                source=settings.source,
                updated_at=settings.updated_at,
                manual_safe_bounds_override_mm=None,
            )
        )
        return settings

    def save_safe_bounds_override(
        self,
        *,
        width_mm: Optional[float],
        height_mm: Optional[float],
    ) -> PlotterDeviceSettings:
        if self._config.plotter_driver.strip().lower() != "axidraw":
            raise InvalidArtifactError(
                "Operational safe bounds can only be updated for the real AxiDraw driver."
            )
        if (width_mm is None) != (height_mm is None):
            raise InvalidArtifactError(
                "Provide both width_mm and height_mm, or clear both values."
            )

        nominal_bounds, nominal_bounds_source, model_info = self._resolve_axidraw_nominal_bounds()
        manual_override = (
            None
            if width_mm is None
            else self._validate_safe_bounds_override(
                width_mm=width_mm,
                height_mm=height_mm,
                nominal_bounds=nominal_bounds,
            )
        )
        updated_at = datetime.now(timezone.utc)
        record = PlotterDeviceSettingsRecord(
            source="persisted",
            updated_at=updated_at,
            manual_safe_bounds_override_mm=manual_override,
        )
        self._store.save(record)
        return self._build_axidraw_settings(
            nominal_bounds=nominal_bounds,
            nominal_bounds_source=nominal_bounds_source,
            model_info=model_info,
            manual_safe_bounds_override_mm=manual_override,
            source=record.source,
            updated_at=updated_at,
        )

    def _validate_settings(
        self,
        settings: PlotterDeviceSettingsRecord,
        *,
        source: str,
    ) -> PlotterDeviceSettings:
        driver = self._config.plotter_driver.strip().lower()
        if driver != "axidraw":
            return PlotterDeviceSettings(
                driver=self._config.plotter_driver,
                plotter_model=None,
                nominal_plotter_bounds_mm=self._resolve_effective_bounds(DEFAULT_CONFIG_BOUNDS),
                nominal_plotter_bounds_source="config_default",
                plotter_bounds_mm=self._resolve_effective_bounds(DEFAULT_CONFIG_BOUNDS),
                plotter_bounds_source=self._resolve_bounds_source(
                    driver="mock",
                    has_override=False,
                ),
                updated_at=settings.updated_at,
                source=source,
            )
        return self._build_current_axidraw_settings(
            source=source,
            updated_at=settings.updated_at,
            manual_safe_bounds_override_mm=settings.manual_safe_bounds_override_mm,
        )

    def _build_default_settings(self, *, source: str) -> PlotterDeviceSettings:
        driver = self._config.plotter_driver.strip().lower()
        updated_at = datetime.now(timezone.utc)
        if driver == "axidraw":
            return self._build_current_axidraw_settings(
                source=source,
                updated_at=updated_at,
                manual_safe_bounds_override_mm=None,
            )
        return PlotterDeviceSettings(
            driver=self._config.plotter_driver,
            plotter_model=None,
            nominal_plotter_bounds_mm=self._resolve_effective_bounds(DEFAULT_CONFIG_BOUNDS),
            nominal_plotter_bounds_source="config_default",
            plotter_bounds_mm=self._resolve_effective_bounds(DEFAULT_CONFIG_BOUNDS),
            plotter_bounds_source=self._resolve_bounds_source(driver=driver, has_override=False),
            updated_at=updated_at,
            source=source,
        )

    def _build_current_axidraw_settings(
        self,
        *,
        source: str,
        updated_at: datetime,
        manual_safe_bounds_override_mm: Optional[SizeMm],
    ) -> PlotterDeviceSettings:
        nominal_bounds, nominal_bounds_source, model_info = self._resolve_axidraw_nominal_bounds()
        return self._build_axidraw_settings(
            nominal_bounds=nominal_bounds,
            nominal_bounds_source=nominal_bounds_source,
            model_info=model_info,
            manual_safe_bounds_override_mm=manual_safe_bounds_override_mm,
            source=source,
            updated_at=updated_at,
        )

    def _resolve_axidraw_nominal_bounds(
        self,
    ) -> tuple[SizeMm, NominalPlotterBoundsSource, Optional[AxiDrawModelInfo]]:
        if (
            self._config.plotter_bounds_width_mm is None
            and self._config.plotter_bounds_height_mm is not None
        ) or (
            self._config.plotter_bounds_width_mm is not None
            and self._config.plotter_bounds_height_mm is None
        ):
            raise HardwareUnavailableError(
                "Real AxiDraw requires explicit machine bounds configuration. Set both "
                "LEARN_TO_DRAW_PLOTTER_BOUNDS_WIDTH_MM and "
                "LEARN_TO_DRAW_PLOTTER_BOUNDS_HEIGHT_MM, or set LEARN_TO_DRAW_AXIDRAW_MODEL."
            )
        if (
            self._config.plotter_bounds_width_mm is None
            and self._config.plotter_bounds_height_mm is None
            and self._config.axidraw_model is None
        ):
            raise HardwareUnavailableError(
                "Real AxiDraw requires explicit machine bounds configuration. Set "
                "LEARN_TO_DRAW_PLOTTER_BOUNDS_WIDTH_MM and "
                "LEARN_TO_DRAW_PLOTTER_BOUNDS_HEIGHT_MM, or set LEARN_TO_DRAW_AXIDRAW_MODEL."
            )

        explicit_bounds = (
            self._config.plotter_bounds_width_mm is not None
            and self._config.plotter_bounds_height_mm is not None
        )
        model_info = (
            resolve_axidraw_model_info(self._config.axidraw_model)
            if self._config.axidraw_model is not None
            else None
        )

        if explicit_bounds:
            bounds = SizeMm(
                width_mm=self._config.plotter_bounds_width_mm,
                height_mm=self._config.plotter_bounds_height_mm,
            )
            bounds_source: NominalPlotterBoundsSource = "config_override"
        else:
            assert model_info is not None
            bounds = SizeMm(
                width_mm=model_info.bounds_width_mm,
                height_mm=model_info.bounds_height_mm,
            )
            bounds_source = "model_default"
        return bounds, bounds_source, model_info

    def _build_axidraw_settings(
        self,
        *,
        nominal_bounds: SizeMm,
        nominal_bounds_source: NominalPlotterBoundsSource,
        model_info: Optional[AxiDrawModelInfo],
        manual_safe_bounds_override_mm: Optional[SizeMm],
        source: str,
        updated_at: datetime,
    ) -> PlotterDeviceSettings:
        operational_bounds = (
            manual_safe_bounds_override_mm
            if manual_safe_bounds_override_mm is not None
            else self._default_safe_bounds(nominal_bounds)
        )
        operational_bounds_source: PlotterBoundsSource = (
            "manual_override"
            if manual_safe_bounds_override_mm is not None
            else "default_clearance"
        )
        return PlotterDeviceSettings(
            driver=self._config.plotter_driver,
            plotter_model=(
                PlotterModelDescriptor(code=model_info.code, label=model_info.label)
                if model_info is not None
                else None
            ),
            nominal_plotter_bounds_mm=nominal_bounds,
            nominal_plotter_bounds_source=nominal_bounds_source,
            plotter_bounds_mm=operational_bounds,
            plotter_bounds_source=operational_bounds_source,
            updated_at=updated_at,
            source=source,
        )

    def _default_safe_bounds(self, nominal_bounds: SizeMm) -> SizeMm:
        width_mm = nominal_bounds.width_mm - DEFAULT_SAFE_CLEARANCE_RIGHT_MM
        height_mm = nominal_bounds.height_mm - DEFAULT_SAFE_CLEARANCE_BOTTOM_MM
        if width_mm <= 0 or height_mm <= 0:
            raise HardwareUnavailableError(
                "Configured nominal machine bounds are smaller than the default safe clearances."
            )
        return SizeMm(width_mm=round(width_mm, 3), height_mm=round(height_mm, 3))

    def _validate_safe_bounds_override(
        self,
        *,
        width_mm: float,
        height_mm: float,
        nominal_bounds: SizeMm,
    ) -> SizeMm:
        if width_mm > nominal_bounds.width_mm or height_mm > nominal_bounds.height_mm:
            raise InvalidArtifactError(
                "Operational safe bounds cannot exceed the nominal machine bounds."
            )
        return SizeMm(width_mm=round(width_mm, 3), height_mm=round(height_mm, 3))

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

    def _resolve_bounds_source(self, *, driver: str, has_override: bool) -> PlotterBoundsSource:
        if driver.strip().lower() == "axidraw" and has_override:
            return "manual_override"
        return "config_default"
