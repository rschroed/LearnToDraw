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
- persists captures, plot assets, plot runs, drawing sessions, calibration, device settings, and workspace state
- prepares normal plot runs into validated page coordinates before adapter execution
- keeps diagnostic hardware actions narrow, fixed, and backend-owned

The current backend structure centers on:

- `routes.py` and `api.py` for the thin FastAPI surface
- `services/hardware.py` for hardware status and control orchestration
- `services/captures.py` for persisted raw capture storage, normalized-derivative metadata, and latest-capture lookup
- `services/capture_service.py` and `services/capture_normalization/` for backend-owned manual page registration
- `services/plot_workflow.py` for asset storage, run creation, preparation, plotting, and capture flow
- `services/drawing_sessions.py` for versioned creative-session state, attended autonomous coordination, and reuse of existing plot runs
- `services/drawing_advisor.py` for prompt-first planning and read-only visual assessment; provider output cannot invoke hardware
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
- `artifacts/drawing_sessions`: versioned intent, plans, ordered PlotRun references, typed events, proposal provenance, and authorization state
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
- `workspace`: physical page size and margins are persisted; the page may extend beyond machine travel, but its margin-bounded drawable coordinates must remain inside the current operational safe bounds
- `device settings`: stable machine information and operational safe bounds are backend-owned and surfaced read-only except for narrow safe overrides
- `calibration`: persisted plotter calibration remains backend-owned and separate from transient runtime overrides
- `drawing sessions`: V2 begins from creative intent, requires explicit authorization for an attended open-ended session, then serially observes and decides whether to continue, complete, or pause; V1 bounded sessions remain readable

## Manual Capture Registration V2

For each non-skipped plot-run capture, the backend first attempts a `light_page_edges_v1` corner proposal: it segments a large light page, extracts a coarse quadrilateral, robustly fits the four straight page edges, and requires the result to remain stable across nearby image thresholds. A stable, geometry-valid result is automatically confirmed and continues through V2 normalization without operator input. An unavailable, clipped, unstable, or invalid result falls back to the five-percent inset quad and pauses in `awaiting_capture_review`; the operator then places named TL/TR/BR/BL points manually. Completed automatic and manual V2 registrations remain adjustable from the immutable raw capture.

`CaptureReview.proposal` records whether `proposed_corners` came from a stable suggestion or the inset fallback, together with the proposal method, raw-pixel stability when available, and a specific fallback reason. It is optional so existing V1 and V2 artifacts remain readable. Stable automatic confirmations persist `review_required: false`, matching proposed and confirmed corners, and `confirmation_source: auto`; operator confirmations and refinements persist `confirmation_source: manual`.

Confirmation uses `POST /api/plot-runs/{run_id}/capture-review/confirm`. The existing asynchronous executor then maps the confirmed raw-capture pixels directly to the full canonical page with one homography. The canonical raster keeps the prepared page aspect ratio, uses a 2048-pixel long side, has a top-left origin, and is not trimmed, rotated, or resized again.

The same confirmation operation may refine a completed, confirmed V2 run. It validates the replacement quad before changing state, then reuses the immutable raw capture to regenerate page-aligned derivatives through the existing `capturing` to `completed` finalization path. This does not plot again, take a new camera image, or make V1 captures editable.

V2 metadata labels this contract with `method: manual_corners_v2` and `frame.version: 2`. `transform.matrix` maps `raw_capture_px` to `page_px`; `inverse_matrix` maps back to the raw capture. Horizontal and vertical pixels-per-millimeter are explicit. Prepared SVG coordinates and registered capture coordinates therefore describe the same page frame, which enables a no-crop intended-versus-observed overlay.

The persisted workspace page size must match the physical sheet whose corners are registered. Machine travel constrains the drawable rectangle, not the sheet itself: right and bottom margins may reserve physical paper beyond the reachable safe bounds, while all prepared drawing coordinates remain inside those bounds.

The AxiDraw Plot context treats the carriage position at plot start as that plot's origin. Post-capture corner registration measures the physical page frame but does not move artwork relative to that frame, so exact sheet placement affects the absolute page position shown by the page-true overlay. It is not a registration prerequisite: hardware validation may remove one best-fit rigid transform (translation and rotation only) that represents page-to-plotter pose before evaluating checkpoint residuals. Scale, shear, projective warping, lens distortion, and local error remain part of that measurement.

Prepared plot SVGs contain only intentional artwork geometry. Full-page source background rectangles are stripped and no synthetic page rectangle is added; the dashboard supplies its white Prepared canvas through presentation styling so page-edge preview treatment can never become plotter motion.

V1 capture and run JSON remains readable without migration. Its detector fields and transforms are legacy evidence only: the dashboard labels V1 registration as legacy, keeps it side by side, and never enables the exact overlay for it. Existing persisted artifacts and former review-memory files are left untouched on disk, but no active runtime reads or rewrites them.

## Versioned Agentic Drawing Sessions

V2 `DrawingSession` records begin from intent alone. Creation persists `planning` state and dispatches provider work without moving hardware. The drawing advisor returns a concise plan, paper strategy, completion intent, and first-pass SVG. That SVG is untrusted: the backend validates its exact drawable-area canvas, supported passive elements, direct coordinates, safe stroke styling, and in-bounds geometry before storing it as a generated asset and exposing `awaiting_approval`.

Guidance submitted before approval is appended to the session event timeline, invalidates the current proposal, and starts a newer planning generation. A stale provider response cannot replace the latest generation. Approval is the first operation that creates a normal PlotRun; all existing preparation, active-run exclusion, hardware adapters, capture registration, and persistence remain authoritative.

V2 persistence adds an append-only typed event timeline, plan and proposal references, authorization timestamps, current-run identity, pass count, and queued guidance. SVGs and images remain separate stored artifacts. Session-list responses expose compact gallery summaries without embedding artifact data. Provider calls remain read-only and receive no hardware tools.

After a registered observation completes, a single backend coordinator sends the rectified grayscale page, current plan, bounded interpretation history, and atomically consumed guidance through `assess_iteration`. `continue` requires a validated incremental SVG and creates exactly one next normal PlotRun. `complete` ends the session. `pause` records its reason and any requested human action. Provider, hardware, registration, and artifact failures pause rather than permitting another physical pass.

Authorization remains attended. The creative client posts a heartbeat; if it is absent for 30 seconds, the current physical pass and its capture may finish, but another pass cannot begin. Stop-after-pass uses the same boundary. Backend startup converts persisted active V2 sessions to a paused recovery state, so process restart never restarts hardware automatically. Resume refreshes attendance, clears the soft-stop request, and re-enters coordination only after normal readiness checks.

A plot run may retake its capture after plotting completed. The run retains an ordered `capture_attempts` history, keeps `capture` as the selected current attempt for compatibility, and sends only that current attempt through registration and normalization. Retake never invokes the plotter. Earlier capture files and metadata remain immutable evidence.

Existing session JSON without `session_version` parses as V1. Its bounded two-to-ten-pass, request-advice, and approve-next-iteration behavior remains available through the legacy endpoints and is not migrated or proactively rewritten.

## Extension Points

- replace or extend adapters without changing the frontend’s hardware model
- evolve the in-process plot-run executor if queued or longer-running work becomes necessary
- expand capture and analysis workflows without moving hardware control into the browser
- add more plotter backends by implementing the existing adapter contracts and keeping device-specific behavior isolated
