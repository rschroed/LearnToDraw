from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class CameraBridgePermissionResult:
    status: str
    prompted: bool
    message: Optional[str]
    next_step_kind: Optional[str]


@dataclass(frozen=True)
class CameraBridgeDevice:
    id: str
    name: str
    position: str


@dataclass(frozen=True)
class CameraBridgeSessionSnapshot:
    state: str
    active_device_id: Optional[str]
    owner_id: Optional[str]
    last_error: Optional[str]


@dataclass(frozen=True)
class CameraBridgeCapturedPhoto:
    local_path: str
    captured_at: str
    device_id: str


class CameraBridgeConnectionError(Exception):
    """Raised when the local CameraBridge service cannot be reached."""


class CameraBridgeClientError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: Optional[str],
        message: str,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class CameraBridgeClient:
    def __init__(
        self,
        *,
        base_url: str,
        token: Optional[str] = None,
        timeout_s: float = 2.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout_s = timeout_s

    def health(self) -> str:
        payload = self._request("GET", "/health", requires_token=False)
        return str(payload.get("status", ""))

    def permission_status(self) -> str:
        payload = self._request("GET", "/v1/permissions", requires_token=False)
        return str(payload.get("status", ""))

    def request_permission(self) -> CameraBridgePermissionResult:
        payload = self._request(
            "POST",
            "/v1/permissions/request",
            requires_token=True,
            body={},
        )
        next_step = payload.get("next_step")
        next_step_kind = None
        if isinstance(next_step, dict):
            next_step_kind = next_step.get("kind")
        return CameraBridgePermissionResult(
            status=str(payload.get("status", "")),
            prompted=bool(payload.get("prompted", False)),
            message=_optional_string(payload.get("message")),
            next_step_kind=_optional_string(next_step_kind),
        )

    def devices(self) -> list[CameraBridgeDevice]:
        payload = self._request("GET", "/v1/devices", requires_token=False)
        devices = payload.get("devices")
        if not isinstance(devices, list):
            raise CameraBridgeClientError(
                status_code=500,
                code="invalid_response",
                message="CameraBridge returned an invalid devices response.",
            )
        return [
            CameraBridgeDevice(
                id=str(device.get("id", "")),
                name=str(device.get("name", "")),
                position=str(device.get("position", "")),
            )
            for device in devices
            if isinstance(device, dict)
        ]

    def session(self) -> CameraBridgeSessionSnapshot:
        payload = self._request("GET", "/v1/session", requires_token=False)
        return CameraBridgeSessionSnapshot(
            state=str(payload.get("state", "")),
            active_device_id=_optional_string(payload.get("active_device_id")),
            owner_id=_optional_string(payload.get("owner_id")),
            last_error=_optional_string(payload.get("last_error")),
        )

    def select_device(
        self,
        *,
        device_id: str,
        owner_id: Optional[str],
    ) -> CameraBridgeSessionSnapshot:
        payload = self._request(
            "POST",
            "/v1/session/select-device",
            requires_token=True,
            body={
                "device_id": device_id,
                "owner_id": owner_id,
            },
        )
        return CameraBridgeSessionSnapshot(
            state=str(payload.get("state", "")),
            active_device_id=_optional_string(payload.get("active_device_id")),
            owner_id=_optional_string(payload.get("owner_id")),
            last_error=_optional_string(payload.get("last_error")),
        )

    def start_session(self, *, owner_id: str) -> CameraBridgeSessionSnapshot:
        payload = self._request(
            "POST",
            "/v1/session/start",
            requires_token=True,
            body={"owner_id": owner_id},
        )
        return CameraBridgeSessionSnapshot(
            state=str(payload.get("state", "")),
            active_device_id=_optional_string(payload.get("active_device_id")),
            owner_id=_optional_string(payload.get("owner_id")),
            last_error=_optional_string(payload.get("last_error")),
        )

    def stop_session(self, *, owner_id: str) -> CameraBridgeSessionSnapshot:
        payload = self._request(
            "POST",
            "/v1/session/stop",
            requires_token=True,
            body={"owner_id": owner_id},
        )
        return CameraBridgeSessionSnapshot(
            state=str(payload.get("state", "")),
            active_device_id=_optional_string(payload.get("active_device_id")),
            owner_id=_optional_string(payload.get("owner_id")),
            last_error=_optional_string(payload.get("last_error")),
        )

    def capture_photo(self, *, owner_id: str) -> CameraBridgeCapturedPhoto:
        payload = self._request(
            "POST",
            "/v1/capture/photo",
            requires_token=True,
            body={"owner_id": owner_id},
        )
        return CameraBridgeCapturedPhoto(
            local_path=str(payload.get("local_path", "")),
            captured_at=str(payload.get("captured_at", "")),
            device_id=str(payload.get("device_id", "")),
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        requires_token: bool,
        body: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        headers = {"Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if requires_token:
            if not self._token:
                raise CameraBridgeClientError(
                    status_code=401,
                    code="unauthorized",
                    message="CameraBridge auth token is missing.",
                )
            headers["Authorization"] = f"Bearer {self._token}"

        request = Request(
            f"{self._base_url}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=self._timeout_s) as response:
                payload = response.read().decode("utf-8")
        except HTTPError as exc:
            payload = exc.read().decode("utf-8")
            parsed = _parse_json(payload)
            error_payload = parsed.get("error")
            if isinstance(error_payload, dict):
                raise CameraBridgeClientError(
                    status_code=exc.code,
                    code=_optional_string(error_payload.get("code")),
                    message=_optional_string(error_payload.get("message"))
                    or f"CameraBridge request failed with {exc.code}.",
                ) from exc
            raise CameraBridgeClientError(
                status_code=exc.code,
                code=None,
                message=f"CameraBridge request failed with {exc.code}.",
            ) from exc
        except (URLError, TimeoutError, ValueError) as exc:
            raise CameraBridgeConnectionError(
                f"Unable to reach CameraBridge at {self._base_url}."
            ) from exc

        parsed = _parse_json(payload)
        if not isinstance(parsed, dict):
            raise CameraBridgeClientError(
                status_code=500,
                code="invalid_response",
                message="CameraBridge returned an invalid JSON response.",
            )
        return parsed


def _parse_json(payload: str) -> Any:
    if not payload:
        return {}
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return {}


def _optional_string(value: object) -> Optional[str]:
    if value is None:
        return None
    return str(value)
