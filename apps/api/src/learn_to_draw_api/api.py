from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from learn_to_draw_api.adapters.camera import CameraAdapter
from learn_to_draw_api.adapters.factory import build_camera_adapter, build_plotter_adapter
from learn_to_draw_api.adapters.plotter import PlotterAdapter
from learn_to_draw_api.config import AppConfig
from learn_to_draw_api.errors import register_exception_handlers
from learn_to_draw_api.routes import build_api_router
from learn_to_draw_api.services.captures import CaptureStore
from learn_to_draw_api.services.hardware import HardwareService
from learn_to_draw_api.services.plot_workflow import (
    PlotAssetStore,
    PlotRunStore,
    PlotWorkflowService,
)
from learn_to_draw_api.services.plotter_calibration import (
    PlotterCalibrationService,
    PlotterCalibrationStore,
)
from learn_to_draw_api.services.plotter_device_settings import (
    PlotterDeviceSettingsService,
    PlotterDeviceSettingsStore,
)
from learn_to_draw_api.services.plotter_workspace import (
    PlotterWorkspaceService,
    PlotterWorkspaceStore,
)


def create_app(
    config: Optional[AppConfig] = None,
    *,
    plotter: Optional[PlotterAdapter] = None,
    camera: Optional[CameraAdapter] = None,
) -> FastAPI:
    app_config = config or AppConfig.from_env()
    app_config.ensure_directories()
    calibration_store = PlotterCalibrationStore(app_config.calibration_dir)
    calibration_service = PlotterCalibrationService(
        store=calibration_store,
        config=app_config,
    )
    device_settings_store = PlotterDeviceSettingsStore(app_config.device_settings_dir)
    device_settings_service = PlotterDeviceSettingsService(
        store=device_settings_store,
        config=app_config,
    )
    workspace_store = PlotterWorkspaceStore(app_config.workspace_dir)
    workspace_service = PlotterWorkspaceService(
        store=workspace_store,
        config=app_config,
        device_settings_service=device_settings_service,
    )
    plotter_adapter = plotter or build_plotter_adapter(
        app_config,
        calibration=calibration_service.current(),
    )
    camera_adapter = camera or build_camera_adapter()

    capture_store = CaptureStore(
        captures_dir=app_config.captures_dir,
        capture_url_prefix=app_config.normalized_capture_url_prefix,
    )
    plot_asset_store = PlotAssetStore(
        assets_dir=app_config.plot_assets_dir,
        assets_url_prefix=app_config.normalized_plot_assets_url_prefix,
    )
    plot_run_store = PlotRunStore(runs_dir=app_config.plot_runs_dir)
    hardware_service = HardwareService(
        plotter=plotter_adapter,
        camera=camera_adapter,
        capture_store=capture_store,
        calibration_service=calibration_service,
        device_settings_service=device_settings_service,
        workspace_service=workspace_service,
    )
    plot_workflow_service = PlotWorkflowService(
        plotter=plotter_adapter,
        camera=camera_adapter,
        capture_store=capture_store,
        asset_store=plot_asset_store,
        run_store=plot_run_store,
        calibration_service=calibration_service,
        device_settings_service=device_settings_service,
        workspace_service=workspace_service,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        hardware_service.startup()
        yield
        hardware_service.shutdown()

    app = FastAPI(title="LearnToDraw API", lifespan=lifespan)
    app.state.config = app_config
    app.state.hardware_service = hardware_service
    app.state.plot_workflow_service = plot_workflow_service
    app.state.plotter_calibration_service = calibration_service
    app.state.plotter_device_settings_service = device_settings_service
    app.state.plotter_workspace_service = workspace_service
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(app_config.cors_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(build_api_router(hardware_service, plot_workflow_service))
    app.mount(
        app_config.normalized_capture_url_prefix,
        StaticFiles(directory=app_config.captures_dir),
        name="captures",
    )
    app.mount(
        app_config.normalized_plot_assets_url_prefix,
        StaticFiles(directory=app_config.plot_assets_dir),
        name="plot-assets",
    )

    return app


app = create_app()
