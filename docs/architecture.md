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
- `services/capture_service.py` and `services/capture_normalization.py` for backend-owned post-capture normalization
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
- `captures`: the backend can trigger and persist camera captures, then enrich them with backend-owned normalized derivatives without mutating the raw source artifact
  Manual captures normalize into a canonical page-sized workspace frame, while normal plot runs normalize inline into the prepared page frame so prepared and observed artifacts share the same backend-owned comparison coordinates. Paper detection is backend-owned and deterministic, with a region-first bright-paper detector on dark-mat captures plus explicit edge/full-frame fallbacks.
- `plot runs`: uploaded SVGs and built-in patterns become stored assets, then tracked runs with explicit preparation, plotting, and optional capture stages; normal runs persist a run-scoped observed result whose embedded capture record can include normalized comparison-ready artifacts
- `diagnostics`: fixed built-in pen and pattern tests stay separate from normal plotting semantics
- `workspace`: page size and margins are persisted and validated against the current drawable area
- `device settings`: stable machine information and operational safe bounds are backend-owned and surfaced read-only except for narrow safe overrides
- `calibration`: persisted plotter calibration remains backend-owned and separate from transient runtime overrides

## Experimental Capture Normalization Diagnostics

Capture normalization exposes backend-only diagnostic switches for saved-capture replay and detector comparison:

- `LEARN_TO_DRAW_NORMALIZATION_MODE`: `default` or `region_only`
- `LEARN_TO_DRAW_NORMALIZATION_EXPERIMENT`: `region_v2` or `contour_v3`

These switches are session/runtime configuration only. They are not persisted as operator settings and should not be surfaced as broad browser controls. Use them to compare detector behavior or inspect rejected candidates while keeping the backend as the sole owner of capture analysis.

## Extension Points

- replace or extend adapters without changing the frontend’s hardware model
- evolve the in-process plot-run executor if queued or longer-running work becomes necessary
- expand capture and analysis workflows without moving hardware control into the browser
- add more plotter backends by implementing the existing adapter contracts and keeping device-specific behavior isolated
