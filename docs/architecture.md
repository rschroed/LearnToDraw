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
- `services/captures.py` for persisted raw capture storage, normalized-derivative metadata, and latest-capture lookup
- `services/capture_service.py` and `services/capture_normalization/` for backend-owned manual page registration
- `services/plot_workflow.py` for asset storage, run creation, preparation, plotting, and capture flow
- `services/plotter_calibration.py`, `services/plotter_device_settings.py`, and `services/plotter_workspace.py` for persisted plotter state

## Frontend Responsibilities

The frontend is a lightweight local dashboard.

- polls backend endpoints for hardware status, captures, plot runs, and plotter state
- triggers safe backend-owned actions such as capture, return-to-origin, test actions, and plot workflow operations
- organizes the local operator experience into workflow, machine-setup, and run-history surfaces
- presents read-only hardware detail plus a small number of bounded controls
- previews planned-vs-captured output and current workspace information without becoming a second hardware API

## CameraBridge Real-Camera Path

The supported real-camera architecture is now CameraBridge-backed and still backend-owned.

- LearnToDraw talks only to its own backend; the browser never calls CameraBridge directly
- the backend integrates with CameraBridge's published localhost `/v1` API and support-directory artifacts
- CameraBridge session ownership stays ephemeral per capture while LearnToDraw persists only the selected device preference under `artifacts/device_settings`
- readiness is modeled explicitly as service, permission, device-selection, busy, or error state rather than helper-owned startup flow
- the dashboard shows manual CameraBridge guidance only; it does not start, stop, or restart CameraBridge on the user's behalf
- the old `apps/macos-helper` proof remains in the repo only as legacy/non-active code and is no longer part of the supported dashboard flow

## Adapters And Hardware Boundary

Hardware integration stays behind backend interfaces.

- `adapters/plotter.py` and `adapters/camera.py` define the app-facing contracts
- mock adapters remain available for development and tests
- the AxiDraw adapter path lives behind the same backend-owned interface
- undocumented or version-sensitive AxiDraw behavior should stay isolated in the wrapper/client layer rather than leaking into services or routes

## Persistence Under `artifacts/`

Local persisted state is organized by purpose:

- `artifacts/captures`: saved raw capture metadata plus normalized derivative artifacts such as rectified grayscale and debug overlays
- `artifacts/plot_assets`: uploaded or built-in plot sources
- `artifacts/plot_runs`: run records and prepared output where applicable
- `artifacts/calibration`: persisted plotter calibration values
- `artifacts/device_settings`: persisted plotter device settings such as safe-bounds overrides plus the selected CameraBridge device preference
- `artifacts/workspace`: persisted page size and margin setup

Filesystem paths and public URLs are kept separate in the backend so local storage layout does not leak into the HTTP surface.

## Current Workflow Shape

The app currently supports a single backend-owned plotting workflow with a few narrow supporting flows.

- `status`: the frontend polls backend hardware status and availability
- `captures`: the backend persists the unmodified camera image first; standalone camera tests remain raw captures, while plot-run captures are registered and enriched with backend-owned color, grayscale, and corner-debug derivatives
- `plot runs`: uploaded SVGs and built-in patterns become stored assets, then tracked runs with explicit preparation, plotting, registration, and capture-finalization stages; every non-skipped plot-run capture pauses in `awaiting_capture_review` until the operator confirms all four physical page corners
- `diagnostics`: fixed built-in pen and pattern tests stay separate from normal plotting semantics
- `workspace`: page size and margins are persisted and validated against the current drawable area
- `device settings`: stable machine information and operational safe bounds are backend-owned and surfaced read-only except for narrow safe overrides
- `calibration`: persisted plotter calibration remains backend-owned and separate from transient runtime overrides

## Manual Capture Registration V2

Automatic paper detection is not part of the active capture path. Each non-skipped plot-run capture gets a versioned `manual_corners` review seeded five percent inside the raw image. The operator places named TL/TR/BR/BL points on the visible physical page corners, and the backend validates that the quad is finite, in bounds, convex, non-crossing, large enough, and has usable edge lengths before changing run state.

Confirmation uses `POST /api/plot-runs/{run_id}/capture-review/confirm`. The existing asynchronous executor then maps the confirmed raw-capture pixels directly to the full canonical page with one homography. The canonical raster keeps the prepared page aspect ratio, uses a 2048-pixel long side, has a top-left origin, and is not trimmed, rotated, or resized again.

V2 metadata labels this contract with `method: manual_corners_v2` and `frame.version: 2`. `transform.matrix` maps `raw_capture_px` to `page_px`; `inverse_matrix` maps back to the raw capture. Horizontal and vertical pixels-per-millimeter are explicit. Prepared SVG coordinates and registered capture coordinates therefore describe the same page frame, which enables a no-crop intended-versus-observed overlay.

V1 capture and run JSON remains readable without migration. Its detector fields and transforms are legacy evidence only: the dashboard labels V1 registration as legacy, keeps it side by side, and never enables the exact overlay for it. Existing persisted artifacts and former review-memory files are left untouched on disk, but no active runtime reads or rewrites them.

## Extension Points

- replace or extend adapters without changing the frontend’s hardware model
- evolve the in-process plot-run executor if queued or longer-running work becomes necessary
- expand capture and analysis workflows without moving hardware control into the browser
- add more plotter backends by implementing the existing adapter contracts and keeping device-specific behavior isolated
