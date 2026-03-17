from __future__ import annotations

from fastapi import APIRouter, File, UploadFile

from learn_to_draw_api.models import (
    CameraCaptureResponse,
    HealthResponse,
    HardwareStatus,
    LatestPlotRunResponse,
    LatestCaptureResponse,
    PlotterCalibration,
    PlotterCalibrationRequest,
    PlotterCalibrationResponse,
    PlotterDeviceSettings,
    PatternAssetCreateRequest,
    PlotAsset,
    PlotterPenHeightsRequest,
    PlotRun,
    PlotRunCreateRequest,
    PlotRunListResponse,
    PlotterCommandResponse,
    PlotterTestActionRequest,
    PlotterWorkspace,
    PlotterWorkspaceRequest,
    PlotterWorkspaceResponse,
)
from learn_to_draw_api.services.hardware import HardwareService
from learn_to_draw_api.services.plot_workflow import PlotWorkflowService


def build_api_router(
    hardware_service: HardwareService,
    plot_workflow_service: PlotWorkflowService,
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/health", response_model=HealthResponse)
    def get_health() -> HealthResponse:
        return HealthResponse()

    @router.get("/api/hardware/status", response_model=HardwareStatus)
    def get_hardware_status() -> HardwareStatus:
        return hardware_service.get_hardware_status()

    @router.post("/api/plotter/walk-home", response_model=PlotterCommandResponse)
    def post_plotter_walk_home() -> PlotterCommandResponse:
        return hardware_service.walk_plotter_home()

    @router.post("/api/plotter/test-actions", response_model=PlotterCommandResponse)
    def post_plotter_test_action(
        request: PlotterTestActionRequest,
    ) -> PlotterCommandResponse:
        return hardware_service.run_plotter_test_action(request.action)

    @router.post("/api/plotter/pen-heights", response_model=PlotterCommandResponse)
    def post_plotter_pen_heights(
        request: PlotterPenHeightsRequest,
    ) -> PlotterCommandResponse:
        return hardware_service.set_plotter_pen_heights(request)

    @router.get("/api/plotter/calibration", response_model=PlotterCalibration)
    def get_plotter_calibration() -> PlotterCalibration:
        return hardware_service.get_plotter_calibration()

    @router.get("/api/plotter/device", response_model=PlotterDeviceSettings)
    def get_plotter_device() -> PlotterDeviceSettings:
        return hardware_service.get_plotter_device_settings()

    @router.post("/api/plotter/calibration", response_model=PlotterCalibrationResponse)
    def post_plotter_calibration(
        request: PlotterCalibrationRequest,
    ) -> PlotterCalibrationResponse:
        return hardware_service.set_plotter_calibration(request)

    @router.get("/api/plotter/workspace", response_model=PlotterWorkspace)
    def get_plotter_workspace() -> PlotterWorkspace:
        return hardware_service.get_plotter_workspace()

    @router.post("/api/plotter/workspace", response_model=PlotterWorkspaceResponse)
    def post_plotter_workspace(
        request: PlotterWorkspaceRequest,
    ) -> PlotterWorkspaceResponse:
        return hardware_service.set_plotter_workspace(request)

    @router.post("/api/camera/capture", response_model=CameraCaptureResponse)
    def post_camera_capture() -> CameraCaptureResponse:
        return hardware_service.capture_image()

    @router.get("/api/captures/latest", response_model=LatestCaptureResponse)
    def get_latest_capture() -> LatestCaptureResponse:
        return hardware_service.latest_capture()

    @router.post("/api/plot-assets/upload", response_model=PlotAsset)
    async def post_plot_asset_upload(file: UploadFile = File(...)) -> PlotAsset:
        return plot_workflow_service.create_uploaded_asset(
            filename=file.filename or "",
            content=await file.read(),
            content_type=file.content_type,
        )

    @router.post("/api/plot-assets/patterns", response_model=PlotAsset)
    def post_plot_asset_pattern(
        request: PatternAssetCreateRequest,
    ) -> PlotAsset:
        return plot_workflow_service.create_pattern_asset(request)

    @router.get("/api/plot-assets/{asset_id}", response_model=PlotAsset)
    def get_plot_asset(asset_id: str) -> PlotAsset:
        return plot_workflow_service.get_asset(asset_id)

    @router.post("/api/plot-runs", response_model=PlotRun)
    def post_plot_run(request: PlotRunCreateRequest) -> PlotRun:
        return plot_workflow_service.create_run(
            request.asset_id,
            purpose=request.purpose,
            capture_mode=request.capture_mode,
            sizing_mode=request.sizing_mode,
        )

    @router.get("/api/plot-runs/latest", response_model=LatestPlotRunResponse)
    def get_latest_plot_run() -> LatestPlotRunResponse:
        return LatestPlotRunResponse(run=plot_workflow_service.latest_run())

    @router.get("/api/plot-runs", response_model=PlotRunListResponse)
    def get_plot_runs() -> PlotRunListResponse:
        return plot_workflow_service.list_runs()

    @router.get("/api/plot-runs/{run_id}", response_model=PlotRun)
    def get_plot_run(run_id: str) -> PlotRun:
        return plot_workflow_service.get_run(run_id)

    return router
