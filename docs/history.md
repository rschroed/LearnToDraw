# LearnToDraw Project History

This document keeps the internal slice-by-slice evolution notes that used to live in the README. It is meant for contributors and maintainers who want the delivery history, while the README stays focused on explaining the project to new GitHub visitors.

## First Slice

- Established the local-first shape: FastAPI backend plus React/Vite dashboard
- Introduced plotter and camera adapter contracts with mock implementations
- Added simple backend-owned `home` and `capture` actions
- Started local capture persistence under `artifacts/captures`

## Second Slice

- Added tracked plot-run workflow and local plot-run metadata
- Added SVG upload and a built-in `test-grid` source
- Introduced local plot asset persistence under `artifacts/plot_assets`
- Added the first real AxiDraw-backed adapter path behind the existing backend interface

## Pen-Reliability Slice

- Replaced misleading `home` language with explicit `return to origin` semantics
- Added backend-configured AxiDraw pen-lift tuning
- Added fixed diagnostic pen actions and tiny built-in diagnostic patterns
- Split diagnostic plot runs from normal runs by intentionally skipping camera capture for diagnostics

## Plot-Sizing Slice

- Gave built-in plot patterns explicit physical `mm` dimensions
- Moved normal plot preparation into a backend-owned sizing path
- Surfaced prepared plot-size metadata in plot-run records and the local UI
- Added a configurable backend draw area for future layout work

## Workspace Slice

- Separated stable plotter bounds from editable session paper setup
- Persisted workspace state under `artifacts/workspace`
- Added backend validation to keep prepared plotting inside drawable area and plotter bounds
- Added page-size and margin controls in the Plotter card backed by backend state

## Device-Settings Slice

- Added a separate persisted plotter device-settings record under `artifacts/device_settings`
- Surfaced read-only plotter model information in the Plotter card
- Added vendor-aligned model labels and model-derived nominal bounds for explicit AxiDraw configurations
- Separated nominal machine bounds from operational safe bounds, including backend-owned clearances and narrow override support

## macOS Helper Proof Slice

- Added a macOS-first helper proof in `apps/macos-helper` to own backend startup for OpenCV camera testing
- Kept the helper lifecycle-only with localhost `/status`, `/start`, and `/stop` endpoints
- Left backend and frontend hardware APIs unchanged while testing whether helper-owned startup improves camera permission reliability
- Added OpenCV camera status diagnostics for open/read results and backend selection during real-camera validation
- Added helper-aware dashboard startup so the web app can auto-start the backend on first load and show helper failure or retry states
- Fixed helper restart to wait for owned backend shutdown before relaunching, avoiding false "outside helper control" failures during post-permission retries
- Made packaged helper bundles movable by embedding the repo root in a generated app resource config instead of deriving it from the bundle path
- Added a dashboard `Open helper` action backed by the `learntodraw-helper://open` custom URL scheme for helper-missing recovery
- Added a dedicated helper install/update script for `/Applications/LearnToDrawCameraHelper.app` to reduce ad hoc packaging and launch confusion

## Run Observation Slice

- Added a run-scoped `observed_result` record on normal plot runs after successful backend-owned capture
- Kept `PlotRun` as the single persisted workflow record and left the global latest-capture flow as convenience-only
- Extended the plot workflow panel so recent runs can be selected for planned, prepared, and observed inspection without adding alignment or comparison logic

## Helper Hardware-Mode Slice

- Removed helper-owned plotter configuration so the macOS helper is camera-only and plotter-neutral
- Kept helper startup focused on OpenCV camera ownership while leaving plotter mode to the backend's normal environment and configuration
- Added helper regression coverage to prevent future silent plotter overrides from creeping back into the helper layer

## Bounded Agent Workflow Slice

- Added an internal `docs/agent-workflow.md` playbook for Codex-driven feature delivery
- Standardized a short pre-edit plan for every implementation slice, with expanded plans for riskier work
- Linked repo workflow guidance and the PR template back to the same planning, verification, and risk language
- Added a project-specific local Codex skill and a narrow PR-readiness automation plan to reduce execution drift before returning to feature work

## Prepared Output Preview Slice

- Added a backend-served prepared-artifact URL for plot runs instead of leaving prepared SVGs as disk-path-only metadata
- Extended plot-run records so the dashboard can render the prepared SVG as a first-class artifact
- Replaced the prepared-output path-only panel view with an actual preview in the existing planned/prepared/observed comparison flow
- Added regression coverage for both the new plot-run artifact URL and the updated dashboard preview behavior

## CameraBridge Integration Slice

- Replaced the supported real-camera path with a backend-owned CameraBridge adapter pinned to the published `v0.1.x` localhost API surface
- Kept capture persistence backend-owned by importing CameraBridge JPEG captures into LearnToDraw's normal `artifacts/captures` store
- Added explicit CameraBridge readiness modeling for service availability, permission guidance, device selection, and external-session conflicts
- Persisted the selected CameraBridge device under `artifacts/device_settings` and added a narrow backend endpoint for updating that preference
- Removed helper-driven startup and OpenCV-specific real-camera UX from the active dashboard path in favor of manual CameraBridge guidance
- Left `apps/macos-helper` in the repo as legacy/non-active code for now instead of treating it as a current architecture dependency

## Setup-First Machine Tab Slice

- Replaced the Machine tab's equal-weight hardware dashboard layout with a setup-first surface centered on paper configuration
- Moved plotter model, readiness, and bounds context into the paper-setup section instead of a standalone summary panel
- Made camera selection the primary camera action, demoted capture to a test action, and removed the Machine-tab latest-capture surface
- Collapsed machine details and diagnostics so advanced hardware data no longer competes with setup tasks in the default view

## Post-Capture Normalization Slice

- Added a backend-owned normalization pipeline that turns raw raster captures into rectified, framed, and comparison-ready derivatives without mutating the raw artifact
- Extended capture records so both standalone captures and plot-run observed results can expose normalized grayscale, debug overlay, and normalization metadata through the existing API responses
- Kept manual capture requests fast by saving the raw artifact first and running workspace page-frame normalization in the background, while normal plot runs normalize inline before completion into the prepared page frame
- Adjusted the line-based fallback to stabilize top-edge selection against bright plotter-rail captures and changed the canonical normalized artifact to a white-backed page-aligned frame instead of a drawing-frame artifact with UI crop compensation
- Replaced the primary edge-led paper detector with a region-first `paper_region_v2` detector that segments the bright sheet from the dark mat, refines the fitted rectangle with local edge evidence, and falls back to the older line detector only when the region candidate is not credible
- Relaxed region occupancy scoring so dense plotted strokes and titles inside the paper no longer cause otherwise-valid paper regions to be rejected back into the weaker line fallback
- Tightened the region-first fit by replacing the loose `minAreaRect` candidate with a contour-clipped rotated box, which keeps left and bottom edges closer to the visible paper border on off-axis real captures
- Added structured normalization diagnostics plus a temporary `region_only` backend mode so rejected `paper_region_v2` candidates can be inspected directly without the noisy line-based fallback masking the failure reason
- Replaced the loose region-box refinement with contour-anchored border snapping, added per-side border-support diagnostics, and started explicitly rejecting region candidates whose left/right/top/bottom borders do not align with the visible paper edge
- Added an experimental contour-first `paper_contour_v3` detector plus a backend experiment switch and replay helper so saved real captures can be compared against `paper_region_v2` without relying on live-camera trial and error
- Increased the canonical normalization long side to `2048px` so downstream comparison artifacts preserve more stroke detail
- Added tight source-content bounds plus a comparison-frame version to preparation metadata and simplified the Workflow comparison view so Prepared and Normalized Result render directly from matching backend-owned page-frame artifacts
- Added deterministic OpenCV regression coverage for confident paper detection, low-confidence best-effort output, and full-frame fallback plus a small result-variant selector in the workflow UI

## Manual Capture Registration V2 Slice

- Replaced unreliable automatic page detection with mandatory per-capture TL/TR/BR/BL registration for every non-skipped plot run
- Added strict backend quad validation and a versioned `manual_corners_v2` contract whose complete forward and inverse homographies map raw capture pixels directly to top-left canonical page pixels
- Preserved V1 JSON loading and legacy side-by-side display without rewriting existing artifacts or inactive review-memory files
- Added a click, drag, keyboard-nudge, and reset registration editor that transforms pointer input through the SVG screen matrix before submitting raw-image coordinates; a live raw-pixel magnifier keeps fine corner placement visible without obscuring the active point
- Added a V2-only prepared-versus-grayscale overlay with adjustable intended-art opacity, while visibly labeling V1 results as legacy registration
- Removed the active detector modules, experiment configuration, replay helper, reuse-memory wiring, and accept-detected/reuse-last API and UI paths
- Corrected paper validation so registration can use the true physical sheet dimensions while right and bottom margins keep prepared drawing coordinates inside operational plotter bounds
- Removed the synthetic full-page white SVG rectangle that AxiDraw could trace as page-edge motion, retaining the white Prepared preview as frontend-only styling
- Separated physical page pose from registration accuracy: the page-true overlay still exposes absolute placement, while hardware validation may remove translation and rotation—but not scale or deformation—before evaluating checkpoint residuals
- Allowed completed V2 runs to refine confirmed corners and regenerate normalized derivatives from the same immutable raw capture without plotting or capturing again

## Automatic Corner Proposal Slice

- Added a backend-owned `light_page_edges_v1` proposal pass that combines light-page segmentation, coarse quadrilateral extraction, robust edge fitting, and threshold-stability checks
- Seeded pending manual reviews from stable proposals while retaining the five-percent inset fallback for missing, clipped, or ambiguous pages
- Added explicit proposal provenance without reusing legacy detector fields or changing the requirement for manual confirmation
- Labeled suggestions and fallback reasons in the existing corner editor, including guidance to verify the intersection of straight page edges through curled tips
- Covered synthetic success/failure cases, workflow fallback and confirmation behavior, legacy parsing, and the selected real C930e/AxiDraw fixture

## Confidence-Gated Automatic Registration Slice

- Automatically finalized stable `light_page_edges_v1` proposals through the existing V2 homography and normalization path
- Kept missing, clipped, unstable, or invalid proposals in the existing manual corner-review flow
- Persisted automatic confirmation provenance and kept completed-run corner refinement available as the recovery path
- Preserved mock, diagnostic, capture-skip, legacy artifact, AxiDraw, and CameraBridge behavior without adding another hardware workflow

## Bounded Iterative Drawing Session Slice

- Added a persisted additive `DrawingSession` that groups existing normal PlotRuns around a text intent and a 2-to-10-pass limit
- Added a read-only drawing-advisor boundary with disabled, deterministic mock, and optional OpenAI Responses API implementations
- Sent registered grayscale observations to the advisor and treated interpretation plus proposed SVG as untrusted output
- Required generated layers to match the drawable area in physical millimeters, rejected active or out-of-bounds SVG content, and reused normal preparation and workspace validation
- Added dashboard controls for session creation, pass history, interpretation, proposal preview, and explicit approval before each additional physical plot
- Kept provider failures retryable and left unattended plotting, erasure, separate-attempt layouts, and cross-session learning out of scope

## Prompt-First Agentic Session Contract Slice

- Added a versioned V2 drawing-session contract that starts from creative intent and produces an agent-authored plan plus safe first-pass SVG before any plotter motion
- Added asynchronous planning, pre-approval conversational revisions with stale-response protection, a compact session-list contract, and one-time first-pass approval
- Split the advisor boundary into prompt-first planning and structured observation assessment while retaining the legacy V1 advice method
- Added typed append-only session events, proposal and authorization metadata, and open-ended V2 persistence while keeping V1 bounded session JSON readable without migration
- Kept all provider output behind the existing SVG safety validator and reused normal PlotRuns only after explicit approval

## Autonomous Session Orchestration And Capture Recovery Slice

- Added a single backend coordinator that turns registered V2 observations into strict continue, complete, or pause decisions and creates at most one validated next PlotRun
- Made one approval open-ended but attended through a 30-second creative-screen heartbeat, stop-after-pass, restart-to-pause recovery, and explicit resume
- Queued guidance during physical work and consumed it exactly once at the next observation assessment, with restoration on provider or validation failure
- Added capture-only retry after a completed plot and preserved ordered immutable capture attempts while keeping the existing current-capture contract
- Kept manual registration, active-run exclusion, normal PlotRuns, mock adapters, and backend-only hardware ownership as the safety boundaries

## Interruptible AxiDraw Plot Worker Slice

- Moved real AxiDraw Plot-context execution into a dedicated spawned process so documented keyboard-pause signal handling is isolated from API server threads
- Added a generic active-plot stop capability, process-scoped SIGINT, AxiDraw output-SVG collection, and explicit error-code interpretation for keyboard and physical pauses
- Added stopping and terminal cancelled run states, persisted paused-progress SVG evidence, and guaranteed that an interrupted plot cannot continue to capture or agent assessment
- Added deterministic mock interruption plus fake-client and process-runner coverage without adding partial-plot resume or undocumented AxiDraw calls
- Kept the physical Pause button as the hardware fallback and documented that software pause occurs only after the current line segment

## Agentic Creative Studio Interface Slice

- Replaced the operator dashboard as the default route with a prompt-first creative home and session-centered studio
- Made cumulative intended artwork, the latest registered observation, exact V2 overlay, and in-context manual corner registration the primary visual surface
- Added a compact typed conversation for plan revisions, queued guidance, agent interpretations, decisions, human-action requests, and consequential machine events
- Added attended heartbeat behavior, stop-after-pass, confirmation-protected emergency stop, capture-only retake, paused recovery, and accessible live-state treatment to the creative interface
- Exposed capture-only retake directly beside manual registration so a blocked, blurred, or overexposed frame can be replaced before its corners are confirmed, without replotting
- Added a session gallery whose preview follows the latest or final camera observation, while retaining machine setup, capture, diagnostics, manual SVG plotting, and legacy session tools under Controls
- Kept provider secrets entirely backend-configured and preserved the existing polling, PlotRun, capture, registration, hardware-adapter, and V1 compatibility boundaries

## Runtime Drawing Advisor Setup Slice

- Added a Controls form that submits an OpenAI key and model to the localhost backend without using browser storage or persisted artifacts
- Added a thread-safe runtime advisor delegate so existing drawing-session orchestration uses the configured provider without restarting the API
- Kept runtime credentials only in backend process memory, returned redacted status only, and made clear/restart restore startup configuration
- Left environment-based advisor configuration available for operators who prefer startup-time setup

## Pre-Approval Preview Orientation Fix

- Made the session studio use the backend-owned workspace page dimensions before a PlotRun exists, so landscape first-pass proposals render in a landscape paper frame
- Kept run preparation and registered-capture dimensions authoritative after plotting, with the existing A4 fallback retained when workspace data is unavailable

## Creative Session Progress Slice

- Added a persistent, user-facing progress panel that translates session, plot-run, and stage states into planning, drawing, photographing, registration, reflection, stopping, paused, complete, and failed language
- Added current-pass context and a compact five-step drawing-cycle indicator without inventing time estimates, percentages, or new backend states
- Consolidated live status announcements into the progress panel and added responsive, reduced-motion, and non-color-only state treatment
- Left polling, orchestration, advisor behavior, registration, capture, and hardware control unchanged

## Creative Session Lifecycle And Paper Preflight Slice

- Added a deliberate New drawing path that can abandon an unused plan, preserve a safely paused session as unfinished, or finish the active physical pass before opening a blank prompt
- Distinguished stop-after-pass from user-requested completion and made completion win before another autonomous assessment or plot can begin
- Added terminal abandoned sessions while retaining their plans, event timelines, and completed run references in Gallery
- Required an explicit blank-sheet, displayed-orientation, and installed-pen confirmation before first motion, with the backend persisting the approved workspace dimensions and timestamp
- Kept active abandonment invalid, all hardware transitions backend-owned, and existing V1/V2 artifacts readable through defaulted lifecycle fields

## Runtime Advisor Model And Timeout Recovery Slice

- Added a model-only runtime configuration operation that reuses the OpenAI credential already held privately by the backend
- Made Controls save future model changes without asking the user to re-enter the intentionally cleared API key, while preserving explicit key replacement and clear-runtime actions
- Kept in-flight planning or assessment on its original advisor snapshot and applied model changes only to future calls
- Extended the bounded OpenAI request window from 60 to 180 seconds and made timeout recovery explicitly recommend retrying or selecting a faster model
- Preserved process-memory-only secret handling and left provider discovery, key persistence, and background Responses orchestration out of scope

For the current architecture and system boundaries, see [architecture.md](architecture.md).
