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

For the current architecture and system boundaries, see [architecture.md](architecture.md).
