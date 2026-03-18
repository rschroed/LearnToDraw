# LearnToDraw Architecture

## System Goals And Guardrails

- Keep the system local-first
- Keep hardware control in the backend
- Preserve a thin localhost dashboard rather than a browser-side hardware client
- Isolate AxiDraw-specific behavior inside backend adapters and wrappers
- Prefer explicit persisted state and explicit run transitions over implicit side effects

## Backend Responsibilities

The backend is the system of record for hardware access and workflow state.

- exposes the HTTP API used by the local dashboard
- reads hardware status and executes plotter/camera actions
- persists captures, plot assets, plot runs, calibration, device settings, and workspace state
- prepares normal plot runs into validated page coordinates before adapter execution
- keeps diagnostic hardware actions narrow, fixed, and backend-owned

The current backend structure centers on:

- `routes.py` and `api.py` for the thin FastAPI surface
- `services/hardware.py` for hardware status and control orchestration
- `services/captures.py` for persisted capture storage and latest-capture lookup
- `services/plot_workflow.py` for asset storage, run creation, preparation, plotting, and capture flow
- `services/plotter_calibration.py`, `services/plotter_device_settings.py`, and `services/plotter_workspace.py` for persisted plotter state

## Frontend Responsibilities

The frontend is a lightweight local dashboard.

- polls backend endpoints for hardware status, captures, plot runs, and plotter state
- triggers safe backend-owned actions such as capture, return-to-origin, test actions, and plot workflow operations
- presents read-only hardware detail plus a small number of bounded controls
- previews planned-vs-captured output and current workspace information without becoming a second hardware API

## Local Helper Proof Slice

The repository now includes a macOS-first helper proof under `apps/macos-helper`.

- the helper is lifecycle-only and does not become a second backend
- it starts and stops the existing FastAPI backend for camera-mode testing
- it exposes helper-local startup status on `127.0.0.1:8001`
- all hardware access still stays in the backend on `127.0.0.1:8000`
- the web app remains unchanged in this slice

## Adapters And Hardware Boundary

Hardware integration stays behind backend interfaces.

- `adapters/plotter.py` and `adapters/camera.py` define the app-facing contracts
- mock adapters remain available for development and tests
- the AxiDraw adapter path lives behind the same backend-owned interface
- undocumented or version-sensitive AxiDraw behavior should stay isolated in the wrapper/client layer rather than leaking into services or routes

## Persistence Under `artifacts/`

Local persisted state is organized by purpose:

- `artifacts/captures`: saved capture metadata and SVG output
- `artifacts/plot_assets`: uploaded or built-in plot sources
- `artifacts/plot_runs`: run records and prepared output where applicable
- `artifacts/calibration`: persisted plotter calibration values
- `artifacts/device_settings`: persisted plotter device settings such as safe-bounds overrides
- `artifacts/workspace`: persisted page size and margin setup

Filesystem paths and public URLs are kept separate in the backend so local storage layout does not leak into the HTTP surface.

## Current Workflow Shape

The app currently supports a single backend-owned plotting workflow with a few narrow supporting flows.

- `status`: the frontend polls backend hardware status and availability
- `captures`: the backend can trigger and persist camera captures, then serve the latest result
- `plot runs`: uploaded SVGs and built-in patterns become stored assets, then tracked runs with explicit preparation, plotting, and optional capture stages
- `diagnostics`: fixed built-in pen and pattern tests stay separate from normal plotting semantics
- `workspace`: page size and margins are persisted and validated against the current drawable area
- `device settings`: stable machine information and operational safe bounds are backend-owned and surfaced read-only except for narrow safe overrides
- `calibration`: persisted plotter calibration remains backend-owned and separate from transient runtime overrides

## Extension Points

- replace or extend adapters without changing the frontend’s hardware model
- evolve the in-process plot-run executor if queued or longer-running work becomes necessary
- expand capture and analysis workflows without moving hardware control into the browser
- add more plotter backends by implementing the existing adapter contracts and keeping device-specific behavior isolated
