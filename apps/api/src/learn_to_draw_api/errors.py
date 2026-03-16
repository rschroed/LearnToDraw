from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from learn_to_draw_api.models import (
    AppConflictError,
    AppNotFoundError,
    HardwareBusyError,
    HardwareError,
    HardwareOperationError,
    HardwareUnavailableError,
    InvalidArtifactError,
)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppConflictError)
    async def handle_conflict(_: Request, exc: AppConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(AppNotFoundError)
    async def handle_not_found(_: Request, exc: AppNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(InvalidArtifactError)
    async def handle_invalid_artifact(
        _: Request, exc: InvalidArtifactError
    ) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(HardwareBusyError)
    async def handle_busy(_: Request, exc: HardwareBusyError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(HardwareUnavailableError)
    async def handle_unavailable(
        _: Request, exc: HardwareUnavailableError
    ) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(HardwareOperationError)
    async def handle_operation(
        _: Request, exc: HardwareOperationError
    ) -> JSONResponse:
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    @app.exception_handler(HardwareError)
    async def handle_hardware(_: Request, exc: HardwareError) -> JSONResponse:
        return JSONResponse(status_code=500, content={"detail": str(exc)})
