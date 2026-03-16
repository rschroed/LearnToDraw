from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class HardwareError(Exception):
    """Base hardware exception."""


class HardwareBusyError(HardwareError):
    """Raised when a device is already performing an action."""


class HardwareUnavailableError(HardwareError):
    """Raised when a device is not available."""


class HardwareOperationError(HardwareError):
    """Raised when a device action fails."""


class AppConflictError(Exception):
    """Raised when a requested action conflicts with current state."""


class AppNotFoundError(Exception):
    """Raised when an expected resource does not exist."""


class InvalidArtifactError(Exception):
    """Raised when provided artifact content is invalid."""


class DeviceStatus(BaseModel):
    available: bool
    connected: bool
    busy: bool
    error: Optional[str] = None
    driver: str
    last_updated: datetime
    details: dict[str, Any] = Field(default_factory=dict)


class HardwareStatus(BaseModel):
    plotter: DeviceStatus
    camera: DeviceStatus


class CaptureMetadata(BaseModel):
    id: str
    timestamp: datetime
    file_path: str
    public_url: str
    width: int
    height: int
    mime_type: str


class PlotDocument(BaseModel):
    asset_id: str
    name: str
    svg_text: str
    width: int
    height: int


class PlotResult(BaseModel):
    started_at: datetime
    completed_at: datetime
    document_id: str
    details: dict[str, Any] = Field(default_factory=dict)


PlotRunPurpose = Literal["normal", "diagnostic"]
PlotRunCaptureMode = Literal["auto", "skip"]
PlotterTestAction = Literal["raise_pen", "lower_pen", "cycle_pen", "align"]


class PlotAsset(BaseModel):
    id: str
    kind: Literal["uploaded_svg", "built_in_pattern"]
    pattern_id: Optional[str] = None
    name: str
    timestamp: datetime
    file_path: str
    public_url: str
    mime_type: str


class PlotStageState(BaseModel):
    status: Literal["pending", "in_progress", "completed", "failed"]
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    message: Optional[str] = None


class PlotRun(BaseModel):
    id: str
    status: Literal["pending", "plotting", "capturing", "completed", "failed"]
    purpose: PlotRunPurpose = "normal"
    capture_mode: PlotRunCaptureMode = "auto"
    created_at: datetime
    updated_at: datetime
    asset: PlotAsset
    capture: Optional[CaptureMetadata] = None
    error: Optional[str] = None
    stage_states: dict[str, PlotStageState] = Field(default_factory=dict)
    plotter_run_details: dict[str, Any] = Field(default_factory=dict)
    camera_run_details: dict[str, Any] = Field(default_factory=dict)


class PlotRunSummary(BaseModel):
    id: str
    status: Literal["pending", "plotting", "capturing", "completed", "failed"]
    purpose: PlotRunPurpose = "normal"
    created_at: datetime
    updated_at: datetime
    asset_id: str
    asset_name: str
    asset_kind: Literal["uploaded_svg", "built_in_pattern"]
    error: Optional[str] = None

    @classmethod
    def from_run(cls, run: "PlotRun") -> "PlotRunSummary":
        return cls(
            id=run.id,
            status=run.status,
            purpose=run.purpose,
            created_at=run.created_at,
            updated_at=run.updated_at,
            asset_id=run.asset.id,
            asset_name=run.asset.name,
            asset_kind=run.asset.kind,
            error=run.error,
        )


class HealthResponse(BaseModel):
    ok: bool = True


class LatestCaptureResponse(BaseModel):
    capture: Optional[CaptureMetadata] = None


class CommandResponse(BaseModel):
    ok: bool = True
    message: str


class PlotterCommandResponse(CommandResponse):
    status: DeviceStatus


class CameraCaptureResponse(CommandResponse):
    status: DeviceStatus
    capture: CaptureMetadata


class LatestPlotRunResponse(BaseModel):
    run: Optional[PlotRun] = None


class PlotRunListResponse(BaseModel):
    runs: list[PlotRunSummary] = Field(default_factory=list)


class PlotRunCreateRequest(BaseModel):
    asset_id: str
    purpose: PlotRunPurpose = "normal"
    capture_mode: PlotRunCaptureMode = "auto"


class PatternAssetCreateRequest(BaseModel):
    pattern_id: str


class PlotterTestActionRequest(BaseModel):
    action: PlotterTestAction


class PlotterPenHeightsRequest(BaseModel):
    pen_pos_up: int = Field(ge=0, le=100)
    pen_pos_down: int = Field(ge=0, le=100)
