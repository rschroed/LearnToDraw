from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional

from learn_to_draw_api.config import AppConfig
from learn_to_draw_api.models import PlotterCalibration, PlotterCalibrationRequest
from learn_to_draw_api.adapters.axidraw_client import read_vendor_default_native_res_factor


class PlotterCalibrationStore:
    def __init__(self, calibration_dir: Path) -> None:
        self._calibration_dir = calibration_dir
        self._calibration_dir.mkdir(parents=True, exist_ok=True)
        self._file_path = self._calibration_dir / "plotter.json"
        self._lock = Lock()

    def load(self) -> Optional[PlotterCalibration]:
        if not self._file_path.exists():
            return None
        return PlotterCalibration.model_validate_json(
            self._file_path.read_text(encoding="utf-8")
        )

    def save(self, calibration: PlotterCalibration) -> PlotterCalibration:
        with self._lock:
            temp_path = self._file_path.with_suffix(".tmp")
            temp_path.write_text(
                calibration.model_dump_json(indent=2),
                encoding="utf-8",
            )
            temp_path.replace(self._file_path)
        return calibration


class PlotterCalibrationService:
    def __init__(
        self,
        *,
        store: PlotterCalibrationStore,
        config: AppConfig,
    ) -> None:
        self._store = store
        self._config = config
        self._vendor_default_native_res_factor = read_vendor_default_native_res_factor() or 1016.0

    @property
    def vendor_default_native_res_factor(self) -> float:
        return self._vendor_default_native_res_factor

    def current(self) -> PlotterCalibration:
        if self._config.axidraw_config_path is not None:
            native_res_factor = self._read_explicit_config_native_res_factor()
            return self._build_calibration(
                native_res_factor=native_res_factor,
                source="explicit_path",
                updated_at=datetime.now(timezone.utc),
            )
        if self._config.axidraw_native_res_factor is not None:
            return self._build_calibration(
                native_res_factor=self._config.axidraw_native_res_factor,
                source="env_override",
                updated_at=datetime.now(timezone.utc),
            )

        persisted = self._store.load()
        if persisted is not None:
            return persisted.model_copy(update={"source": "persisted"})

        return self._build_calibration(
            native_res_factor=self._vendor_default_native_res_factor,
            source="vendor_default",
            updated_at=datetime.now(timezone.utc),
        )

    def persisted(self) -> Optional[PlotterCalibration]:
        return self._store.load()

    def save_axidraw_native_res_factor(
        self,
        request: PlotterCalibrationRequest,
    ) -> PlotterCalibration:
        calibration = self._build_calibration(
            native_res_factor=request.native_res_factor,
            source="persisted",
            updated_at=datetime.now(timezone.utc),
        )
        self._store.save(calibration)
        return calibration

    def _build_calibration(
        self,
        *,
        native_res_factor: float,
        source: str,
        updated_at: datetime,
    ) -> PlotterCalibration:
        return PlotterCalibration(
            driver="axidraw",
            motion_scale=round(
                native_res_factor / self._vendor_default_native_res_factor,
                6,
            ),
            driver_calibration={
                "native_res_factor": round(native_res_factor, 6),
            },
            updated_at=updated_at,
            source=source,
        )

    def _read_explicit_config_native_res_factor(self) -> float:
        assert self._config.axidraw_config_path is not None
        calibration = self._config.axidraw_config_path.read_text(encoding="utf-8")
        for line in calibration.splitlines():
            if line.strip().startswith("native_res_factor"):
                _, value = line.split("=", 1)
                return float(value.split("#", 1)[0].strip())
        return self._vendor_default_native_res_factor
