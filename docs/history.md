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

For the current architecture and system boundaries, see [architecture.md](architecture.md).
