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
    prepared_width_mm: float
    prepared_height_mm: float


class PlotArea(BaseModel):
    page_width_mm: float
    page_height_mm: float
    margin_left_mm: float
    margin_top_mm: float
    margin_right_mm: float
    margin_bottom_mm: float
    origin: Literal["top-left"] = "top-left"

    @property
    def draw_width_mm(self) -> float:
        return self.page_width_mm - self.margin_left_mm - self.margin_right_mm

    @property
    def draw_height_mm(self) -> float:
        return self.page_height_mm - self.margin_top_mm - self.margin_bottom_mm


class SizeMm(BaseModel):
    width_mm: float
    height_mm: float


class MarginsMm(BaseModel):
    left_mm: float
    top_mm: float
    right_mm: float
    bottom_mm: float


class PlotPreparationMetadata(BaseModel):
    class WorkspaceAudit(BaseModel):
        page_within_plotter_bounds: bool
        drawable_area_positive: bool
        drawable_origin_x_mm: float
        drawable_origin_y_mm: float
        remaining_bounds_right_mm: float
        remaining_bounds_bottom_mm: float

    class PreparationAudit(BaseModel):
        strategy: str
        fit_scale: Optional[float] = None
        prepared_within_drawable_area: bool
        overflow_x_mm: float
        overflow_y_mm: float
        placement_origin_x_mm: Optional[float] = None
        placement_origin_y_mm: Optional[float] = None
        content_min_x_mm: Optional[float] = None
        content_min_y_mm: Optional[float] = None
        content_max_x_mm: Optional[float] = None
        content_max_y_mm: Optional[float] = None
        content_width_mm: Optional[float] = None
        content_height_mm: Optional[float] = None
        prepared_viewbox_min_x: Optional[float] = None
        prepared_viewbox_min_y: Optional[float] = None
        prepared_viewbox_width: Optional[float] = None
        prepared_viewbox_height: Optional[float] = None

    source_width: float
    source_height: float
    source_units: Literal["mm", "cm", "in", "px", "unitless", "mixed", "unknown"]
    prepared_width_mm: float
    prepared_height_mm: float
    page_width_mm: float
    page_height_mm: float
    drawable_width_mm: float
    drawable_height_mm: float
    plotter_bounds_width_mm: float
    plotter_bounds_height_mm: float
    plotter_bounds_source: Literal["model_default", "config_override", "config_default"]
    plotter_model_code: Optional[int] = None
    plotter_model_label: Optional[str] = None
    units_inferred: bool = False
    workspace_audit: WorkspaceAudit
    preparation_audit: PreparationAudit


class PlotResult(BaseModel):
    started_at: datetime
    completed_at: datetime
    document_id: str
    details: dict[str, Any] = Field(default_factory=dict)


PlotRunPurpose = Literal["normal", "diagnostic"]
PlotRunCaptureMode = Literal["auto", "skip"]
PlotterTestAction = Literal["raise_pen", "lower_pen", "cycle_pen", "align"]
PlotterBoundsSource = Literal["model_default", "config_override", "config_default"]
PlotterCalibrationSource = Literal[
    "vendor_default",
    "persisted",
    "env_override",
    "explicit_path",
]
PlotterDeviceSettingsSource = Literal["config_default", "persisted"]
PlotterWorkspaceSource = Literal["config_default", "persisted"]


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


class PlotterCalibration(BaseModel):
    driver: str
    motion_scale: float = Field(gt=0)
    driver_calibration: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime
    source: PlotterCalibrationSource


class PlotterCalibrationRequest(BaseModel):
    native_res_factor: float = Field(gt=0)


class PlotterCalibrationResponse(CommandResponse):
    calibration: PlotterCalibration


class PlotterModelDescriptor(BaseModel):
    code: int
    label: str


class PlotterDeviceSettings(BaseModel):
    driver: str
    plotter_model: Optional[PlotterModelDescriptor] = None
    plotter_bounds_mm: SizeMm
    plotter_bounds_source: PlotterBoundsSource
    updated_at: datetime
    source: PlotterDeviceSettingsSource


class PlotterWorkspace(BaseModel):
    plotter_bounds_mm: SizeMm
    page_size_mm: SizeMm
    margins_mm: MarginsMm
    drawable_area_mm: SizeMm
    updated_at: datetime
    source: PlotterWorkspaceSource
    is_valid: bool = True
    validation_error: Optional[str] = None

    def to_plot_area(self) -> PlotArea:
        return PlotArea(
            page_width_mm=self.page_size_mm.width_mm,
            page_height_mm=self.page_size_mm.height_mm,
            margin_left_mm=self.margins_mm.left_mm,
            margin_top_mm=self.margins_mm.top_mm,
            margin_right_mm=self.margins_mm.right_mm,
            margin_bottom_mm=self.margins_mm.bottom_mm,
        )


class PlotterWorkspaceRequest(BaseModel):
    page_width_mm: float = Field(gt=0)
    page_height_mm: float = Field(gt=0)
    margin_left_mm: float = Field(ge=0)
    margin_top_mm: float = Field(ge=0)
    margin_right_mm: float = Field(ge=0)
    margin_bottom_mm: float = Field(ge=0)


class PlotterWorkspaceResponse(CommandResponse):
    workspace: PlotterWorkspace
