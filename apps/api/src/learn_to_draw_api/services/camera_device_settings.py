from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional

from learn_to_draw_api.models import CameraDeviceSettingsRecord


class CameraDeviceSettingsStore:
    def __init__(self, settings_dir: Path) -> None:
        self._settings_dir = settings_dir
        self._settings_dir.mkdir(parents=True, exist_ok=True)
        self._file_path = self._settings_dir / "camera.json"
        self._lock = Lock()

    def load(self) -> Optional[CameraDeviceSettingsRecord]:
        if not self._file_path.exists():
            return None
        return CameraDeviceSettingsRecord.model_validate_json(
            self._file_path.read_text(encoding="utf-8")
        )

    def save(self, settings: CameraDeviceSettingsRecord) -> CameraDeviceSettingsRecord:
        with self._lock:
            temp_path = self._file_path.with_suffix(".tmp")
            temp_path.write_text(settings.model_dump_json(indent=2), encoding="utf-8")
            temp_path.replace(self._file_path)
        return settings


class CameraDeviceSettingsService:
    def __init__(self, *, store: CameraDeviceSettingsStore) -> None:
        self._store = store

    def current(self) -> CameraDeviceSettingsRecord:
        persisted = self._store.load()
        if persisted is not None:
            return persisted
        record = CameraDeviceSettingsRecord(updated_at=datetime.now(timezone.utc))
        self._store.save(record)
        return record

    def selected_device_id(self) -> Optional[str]:
        return self.current().selected_device_id

    def save_selected_device(self, device_id: Optional[str]) -> CameraDeviceSettingsRecord:
        record = CameraDeviceSettingsRecord(
            selected_device_id=device_id,
            updated_at=datetime.now(timezone.utc),
        )
        self._store.save(record)
        return record
