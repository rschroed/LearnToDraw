from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import cv2
import numpy as np

from learn_to_draw_api.adapters.camera import CaptureArtifact
from learn_to_draw_api.adapters.camerabridge_client import (
    CameraBridgeCapturedPhoto,
    CameraBridgeClient,
    CameraBridgeClientError,
    CameraBridgeConnectionError,
    CameraBridgeDevice,
    CameraBridgePermissionResult,
)
from learn_to_draw_api.config import AppConfig
from learn_to_draw_api.models import (
    DeviceStatus,
    HardwareBusyError,
    HardwareOperationError,
    HardwareUnavailableError,
    InvalidArtifactError,
)
from learn_to_draw_api.services.camera_device_settings import CameraDeviceSettingsService


CAMERABRIDGE_SUPPORT_DIR = (
    Path.home() / "Library" / "Application Support" / "CameraBridge"
)
CAMERABRIDGE_RUNTIME_CONFIGURATION_PATH = (
    CAMERABRIDGE_SUPPORT_DIR / "runtime-configuration.json"
)
CAMERABRIDGE_DEFAULT_TOKEN_PATH = CAMERABRIDGE_SUPPORT_DIR / "auth-token"
CAMERABRIDGE_PERMISSION_GUIDANCE = (
    "Open CameraBridgeApp, click Start CameraBridge Service, then click "
    "Request Camera Access if permission is still undecided."
)


@dataclass(frozen=True)
class _RuntimeResolution:
    base_url: Optional[str]
    token_path: Path
    token: Optional[str]
    configuration_error: Optional[str]
    token_error: Optional[str]


class CameraBridgeCamera:
    driver = "camerabridge"

    def __init__(
        self,
        *,
        config: AppConfig,
        camera_settings_service: CameraDeviceSettingsService,
    ) -> None:
        self._config = config
        self._camera_settings_service = camera_settings_service
        self._connected = False
        self._last_updated = datetime.now(timezone.utc)

    def connect(self) -> None:
        self._connected = True
        self._touch()

    def disconnect(self) -> None:
        self._connected = False
        self._touch()

    def set_selected_device(self, device_id: Optional[str]) -> DeviceStatus:
        if device_id is not None and not device_id.strip():
            raise InvalidArtifactError("device_id must be a non-empty string or null.")
        normalized_device_id = device_id.strip() if device_id is not None else None
        status = self._build_status()
        device_ids = {
            str(device.get("id"))
            for device in status.details.get("devices", [])
            if isinstance(device, dict) and device.get("id") is not None
        }
        if normalized_device_id is not None and normalized_device_id not in device_ids:
            raise InvalidArtifactError(
                f"CameraBridge device '{normalized_device_id}' is unavailable."
            )
        self._camera_settings_service.save_selected_device(normalized_device_id)
        return self._build_status()

    def get_status(self) -> DeviceStatus:
        return self._build_status()

    def capture(self) -> CaptureArtifact:
        runtime = self._resolve_runtime()
        if runtime.configuration_error is not None:
            raise HardwareUnavailableError(runtime.configuration_error)
        if runtime.base_url is None:
            raise HardwareUnavailableError("CameraBridge base URL is not configured.")

        client = CameraBridgeClient(base_url=runtime.base_url, token=runtime.token)
        try:
            if client.health() != "ok":
                raise HardwareUnavailableError(
                    "CameraBridge is not healthy. Start CameraBridge Service in CameraBridgeApp and retry."
                )
        except CameraBridgeConnectionError as exc:
            raise HardwareUnavailableError(
                "CameraBridge is unavailable. Start CameraBridge Service in CameraBridgeApp and retry."
            ) from exc

        if runtime.token_error is not None:
            raise HardwareUnavailableError(runtime.token_error)

        try:
            permission = client.request_permission()
            devices = client.devices()
            session = client.session()
        except CameraBridgeClientError as exc:
            raise self._map_client_error(exc) from exc
        except CameraBridgeConnectionError as exc:
            raise HardwareUnavailableError(
                "CameraBridge became unavailable while preparing the capture."
            ) from exc

        if permission.status == "not_determined":
            raise HardwareUnavailableError(
                permission.message or CAMERABRIDGE_PERMISSION_GUIDANCE
            )
        if permission.status == "denied":
            raise HardwareUnavailableError(
                "CameraBridge camera permission is denied. Open CameraBridgeApp and re-enable camera access in System Settings."
            )
        if permission.status == "restricted":
            raise HardwareUnavailableError(
                "CameraBridge camera permission is restricted and cannot be used for capture."
            )
        if not devices:
            raise HardwareUnavailableError("CameraBridge did not report any available camera devices.")

        effective_device_id = self._resolve_effective_device_id(devices)
        if effective_device_id is None:
            raise HardwareUnavailableError(
                "Select a CameraBridge device in LearnToDraw before capturing."
            )

        if session.state == "running" and session.owner_id not in {None, self._config.camerabridge_owner_id}:
            raise HardwareBusyError(
                "CameraBridge is busy because another local client owns the current session."
            )

        stop_required = False
        artifact: Optional[CaptureArtifact] = None
        cleanup_error: Optional[HardwareOperationError] = None
        try:
            if session.state == "running" and session.owner_id == self._config.camerabridge_owner_id:
                client.stop_session(owner_id=self._config.camerabridge_owner_id)

            client.select_device(
                device_id=effective_device_id,
                owner_id=self._config.camerabridge_owner_id,
            )
            client.start_session(owner_id=self._config.camerabridge_owner_id)
            stop_required = True
            captured = client.capture_photo(owner_id=self._config.camerabridge_owner_id)
            artifact = self._build_capture_artifact(captured)
        except CameraBridgeClientError as exc:
            raise self._map_client_error(exc) from exc
        except CameraBridgeConnectionError as exc:
            raise HardwareUnavailableError(
                "CameraBridge became unavailable during capture."
            ) from exc
        finally:
            if stop_required:
                try:
                    client.stop_session(owner_id=self._config.camerabridge_owner_id)
                except (CameraBridgeClientError, CameraBridgeConnectionError):
                    cleanup_error = HardwareOperationError(
                        "CameraBridge captured an image but the session could not be stopped cleanly."
                    )

        if cleanup_error is not None:
            raise cleanup_error
        assert artifact is not None
        self._touch()
        return artifact

    def _build_status(self) -> DeviceStatus:
        runtime = self._resolve_runtime()
        details: dict[str, object] = {
            "base_url": runtime.base_url,
            "token_path": str(runtime.token_path),
            "token_readable": runtime.token_error is None,
            "persisted_selected_device_id": self._camera_settings_service.selected_device_id(),
            "effective_selected_device_id": None,
            "selection_required": False,
            "service_available": False,
            "permission_status": None,
            "permission_message": None,
            "permission_next_step_kind": None,
            "session_state": None,
            "session_owner_id": None,
            "active_device_id": None,
            "device_count": 0,
            "devices": [],
            "readiness_state": "error",
        }

        if runtime.configuration_error is not None:
            details["configuration_error"] = runtime.configuration_error
            return self._status(
                available=False,
                connected=False,
                busy=False,
                error=runtime.configuration_error,
                details=details,
            )

        if runtime.base_url is None:
            details["configuration_error"] = "CameraBridge base URL is not configured."
            return self._status(
                available=False,
                connected=False,
                busy=False,
                error="CameraBridge base URL is not configured.",
                details=details,
            )

        client = CameraBridgeClient(base_url=runtime.base_url, token=runtime.token)
        try:
            service_available = client.health() == "ok"
        except CameraBridgeConnectionError:
            details["readiness_state"] = "needs_service"
            return self._status(
                available=False,
                connected=False,
                busy=False,
                error=None,
                details=details,
            )
        except CameraBridgeClientError as exc:
            details["readiness_state"] = "error"
            return self._status(
                available=False,
                connected=False,
                busy=False,
                error=exc.message,
                details=details,
            )

        details["service_available"] = service_available
        if not service_available:
            details["readiness_state"] = "needs_service"
            return self._status(
                available=False,
                connected=False,
                busy=False,
                error=None,
                details=details,
            )

        if runtime.token_error is not None:
            return self._status(
                available=False,
                connected=True,
                busy=False,
                error=runtime.token_error,
                details={**details, "readiness_state": "error"},
            )

        try:
            permission_status = client.permission_status()
            devices = client.devices()
            session = client.session()
        except CameraBridgeClientError as exc:
            details["readiness_state"] = "error"
            return self._status(
                available=False,
                connected=True,
                busy=False,
                error=exc.message,
                details=details,
            )
        except CameraBridgeConnectionError:
            details["readiness_state"] = "needs_service"
            return self._status(
                available=False,
                connected=False,
                busy=False,
                error=None,
                details=details,
            )

        details["permission_status"] = permission_status
        details["devices"] = [device.__dict__ for device in devices]
        details["device_count"] = len(devices)
        details["session_state"] = session.state
        details["session_owner_id"] = session.owner_id
        details["active_device_id"] = session.active_device_id

        permission_result: Optional[CameraBridgePermissionResult] = None
        token_error: Optional[str] = None
        if token_error is None:
            try:
                permission_result = client.request_permission()
            except CameraBridgeClientError as exc:
                if exc.status_code == 401:
                    token_error = (
                        f"CameraBridge auth token at {runtime.token_path} is missing or invalid."
                    )
                else:
                    return self._status(
                        available=False,
                        connected=True,
                        busy=False,
                        error=exc.message,
                        details={**details, "readiness_state": "error"},
                    )
            except CameraBridgeConnectionError:
                token_error = "CameraBridge became unavailable while validating camera readiness."

        if permission_result is not None:
            details["permission_status"] = permission_result.status
            details["permission_message"] = permission_result.message
            details["permission_next_step_kind"] = permission_result.next_step_kind

        effective_device_id = self._resolve_effective_device_id(devices)
        details["effective_selected_device_id"] = effective_device_id
        selection_required = len(devices) > 1 and effective_device_id is None
        details["selection_required"] = selection_required

        if token_error is not None:
            return self._status(
                available=False,
                connected=True,
                busy=False,
                error=token_error,
                details={**details, "readiness_state": "error"},
            )

        permission_state = str(details["permission_status"])
        if permission_state == "not_determined":
            details["permission_message"] = (
                details.get("permission_message") or CAMERABRIDGE_PERMISSION_GUIDANCE
            )
            details["permission_next_step_kind"] = (
                details.get("permission_next_step_kind") or "open_camera_bridge_app"
            )
            details["readiness_state"] = "needs_permission"
            return self._status(
                available=False,
                connected=True,
                busy=False,
                error=None,
                details=details,
            )
        if permission_state == "denied":
            return self._status(
                available=False,
                connected=True,
                busy=False,
                error=(
                    "CameraBridge camera permission is denied. Open CameraBridgeApp and re-enable camera access in System Settings."
                ),
                details={**details, "readiness_state": "error"},
            )
        if permission_state == "restricted":
            return self._status(
                available=False,
                connected=True,
                busy=False,
                error="CameraBridge camera permission is restricted.",
                details={**details, "readiness_state": "error"},
            )
        if not devices:
            return self._status(
                available=False,
                connected=True,
                busy=False,
                error="CameraBridge did not report any available camera devices.",
                details={**details, "readiness_state": "error"},
            )
        if session.state == "running" and session.owner_id not in {None, self._config.camerabridge_owner_id}:
            return self._status(
                available=False,
                connected=True,
                busy=True,
                error=None,
                details={**details, "readiness_state": "busy_external"},
            )
        if effective_device_id is None:
            return self._status(
                available=False,
                connected=True,
                busy=False,
                error=None,
                details={**details, "readiness_state": "needs_device_selection"},
            )
        return self._status(
            available=True,
            connected=True,
            busy=False,
            error=None,
            details={**details, "readiness_state": "ready"},
        )

    def _resolve_runtime(self) -> _RuntimeResolution:
        token_path = (
            self._config.camerabridge_token_path
            if self._config.camerabridge_token_path is not None
            else CAMERABRIDGE_DEFAULT_TOKEN_PATH
        )
        token: Optional[str] = None
        token_error: Optional[str] = None
        try:
            token = self._load_token(token_path)
        except HardwareUnavailableError as exc:
            token_error = str(exc)

        if self._config.camerabridge_base_url is not None:
            try:
                return _RuntimeResolution(
                    base_url=self._normalize_base_url(
                        self._config.camerabridge_base_url,
                        source="LEARN_TO_DRAW_CAMERABRIDGE_BASE_URL",
                    ),
                    token_path=token_path,
                    token=token,
                    configuration_error=None,
                    token_error=token_error,
                )
            except HardwareUnavailableError as exc:
                return _RuntimeResolution(
                    base_url=None,
                    token_path=token_path,
                    token=token,
                    configuration_error=str(exc),
                    token_error=token_error,
                )

        if CAMERABRIDGE_RUNTIME_CONFIGURATION_PATH.exists():
            try:
                config_payload = json.loads(
                    CAMERABRIDGE_RUNTIME_CONFIGURATION_PATH.read_text(encoding="utf-8")
                )
                host = str(config_payload.get("host", "")).strip()
                port = int(config_payload.get("port"))
                return _RuntimeResolution(
                    base_url=self._normalize_base_url(
                        f"http://{host}:{port}",
                        source=str(CAMERABRIDGE_RUNTIME_CONFIGURATION_PATH),
                    ),
                    token_path=token_path,
                    token=token,
                    configuration_error=None,
                    token_error=token_error,
                )
            except (ValueError, TypeError, json.JSONDecodeError):
                return _RuntimeResolution(
                    base_url=None,
                    token_path=token_path,
                    token=token,
                    configuration_error=(
                        "CameraBridge runtime configuration is invalid at "
                        f"{CAMERABRIDGE_RUNTIME_CONFIGURATION_PATH}."
                    ),
                    token_error=token_error,
                )

        return _RuntimeResolution(
            base_url="http://127.0.0.1:8731",
            token_path=token_path,
            token=token,
            configuration_error=None,
            token_error=token_error,
        )

    def _normalize_base_url(self, value: str, *, source: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme != "http" or not parsed.netloc:
            raise HardwareUnavailableError(
                f"CameraBridge base URL from {source} must be a valid http://host:port URL."
            )
        return value.rstrip("/")

    def _load_token(self, token_path: Path) -> str:
        if not token_path.exists():
            raise HardwareUnavailableError(
                f"CameraBridge auth token is missing at {token_path}."
            )
        token = token_path.read_text(encoding="utf-8").strip()
        if not token:
            raise HardwareUnavailableError(
                f"CameraBridge auth token is empty at {token_path}."
            )
        return token

    def _resolve_effective_device_id(
        self,
        devices: list[CameraBridgeDevice],
    ) -> Optional[str]:
        available_ids = {device.id for device in devices}
        persisted_selected_device_id = self._camera_settings_service.selected_device_id()
        if (
            persisted_selected_device_id is not None
            and persisted_selected_device_id in available_ids
        ):
            return persisted_selected_device_id
        if (
            self._config.camerabridge_default_device_id is not None
            and self._config.camerabridge_default_device_id in available_ids
        ):
            return self._config.camerabridge_default_device_id
        if len(devices) == 1:
            return devices[0].id
        return None

    def _build_capture_artifact(
        self,
        captured: CameraBridgeCapturedPhoto,
    ) -> CaptureArtifact:
        artifact_path = Path(captured.local_path)
        if not artifact_path.exists():
            raise HardwareOperationError(
                f"CameraBridge capture file does not exist: {artifact_path}"
            )
        content = artifact_path.read_bytes()
        width, height = self._image_dimensions(content)
        return CaptureArtifact(
            capture_id=artifact_path.stem,
            timestamp=_parse_utc_timestamp(captured.captured_at),
            filename=artifact_path.name,
            content=content,
            media_type="image/jpeg",
            width=width,
            height=height,
        )

    def _image_dimensions(self, content: bytes) -> tuple[int, int]:
        image = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None or len(image.shape) < 2:
            raise HardwareOperationError(
                "CameraBridge returned a capture that LearnToDraw could not inspect."
            )
        return int(image.shape[1]), int(image.shape[0])

    def _status(
        self,
        *,
        available: bool,
        connected: bool,
        busy: bool,
        error: Optional[str],
        details: dict[str, object],
    ) -> DeviceStatus:
        self._touch()
        return DeviceStatus(
            available=available,
            connected=connected and self._connected,
            busy=busy,
            error=error,
            driver=self.driver,
            last_updated=self._last_updated,
            details=details,
        )

    def _map_client_error(self, error: CameraBridgeClientError) -> Exception:
        if error.status_code == 401:
            return HardwareUnavailableError(
                "CameraBridge auth token is missing or invalid."
            )
        if error.status_code == 409 and error.code == "ownership_conflict":
            return HardwareBusyError(
                "CameraBridge is busy because another local client owns the current session."
            )
        if error.status_code == 409 and error.code == "invalid_state":
            return HardwareUnavailableError(error.message)
        if error.status_code >= 500:
            return HardwareOperationError(error.message)
        return HardwareUnavailableError(error.message)

    def _touch(self) -> None:
        self._last_updated = datetime.now(timezone.utc)


def _parse_utc_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).astimezone(timezone.utc)
