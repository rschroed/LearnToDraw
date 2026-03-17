# LearnToDraw

Local-first control panel for a closed-loop pen-plotter workflow.

This first slice includes:

- a FastAPI backend that owns hardware access
- a React/Vite dashboard for local control
- plotter and camera adapter interfaces
- mock plotter and mock camera implementations
- simple actions for `home` and `capture`
- local capture persistence under `artifacts/captures`

This second slice adds:

- a tracked plot-run workflow
- local SVG upload and a built-in `test-grid` source
- planned SVG preview and captured result comparison
- local asset persistence under `artifacts/plot_assets`
- local plot-run metadata under `artifacts/plot_runs`
- a real AxiDraw-backed plotter adapter path behind the existing backend interface

This pen-reliability slice adds:

- explicit `return to origin` semantics instead of misleading `home`
- documented AxiDraw pen-lift tuning via backend config
- fixed diagnostic pen actions for the real AxiDraw adapter
- tiny built-in diagnostic patterns: `tiny-square`, `dash-row`, and `double-box`
- diagnostic plot runs that skip camera capture on purpose

This plot-sizing slice adds:

- explicit physical `mm` dimensions for built-in plot patterns
- backend-owned plot sizing with `native` and `fit_to_draw_area`
- a configurable backend draw area for future page-layout and iterative drawing work
- prepared plot-size metadata surfaced in plot-run records and the local UI

This workspace slice adds:

- stable plotter bounds separate from editable session paper setup
- persisted backend workspace state under `artifacts/workspace`
- backend validation that plotting stays inside the current drawable area and plotter bounds
- page-size and margin controls in the Plotter card, stored as session/backend state

This device-settings slice adds:

- a separate persisted plotter device-settings record under `artifacts/device_settings`
- read-only plotter model visibility in the Plotter card
- vendor-aligned model labels and default bounds for AxiDraw when a model is explicitly configured
- explicit bounds-source reporting so model-derived defaults and config overrides are visible

## Repo layout

- `apps/api`: Python backend API and hardware layer
- `apps/web`: local dashboard UI
- `artifacts/captures`: locally saved mock camera captures
- `artifacts/plot_assets`: stored planned SVG assets
- `artifacts/plot_runs`: stored plot-run metadata
- `artifacts/device_settings`: persisted plotter device settings
- `artifacts/workspace`: persisted plotter workspace/session setup
- `docs/architecture.md`: slice-1 architecture notes

## Backend setup

Preferred long-term workflow is `uv`, but this repo also works with standard Python tooling.

```bash
make api-install
make api-dev
```

`make api-dev` uses `PYTHONPATH=src`, so a non-editable install is enough for local development on older system Python setups.

Run tests:

```bash
make api-test
```

## Frontend setup

```bash
make web-install
make web-dev
```

Run tests:

```bash
make web-test
```

The Vite dev server proxies `/api` and `/captures` to the backend on `http://127.0.0.1:8000`.
It also proxies `/plot-assets` for planned SVG previews.

## Real AxiDraw adapter

The backend still defaults to the mock plotter. To switch to the real AxiDraw adapter, set:

```bash
export LEARN_TO_DRAW_PLOTTER_DRIVER=axidraw
```

Optional motion settings:

```bash
export LEARN_TO_DRAW_AXIDRAW_PORT=YOUR_PORT
export LEARN_TO_DRAW_AXIDRAW_SPEED_PENDOWN=35
export LEARN_TO_DRAW_AXIDRAW_SPEED_PENUP=75
export LEARN_TO_DRAW_AXIDRAW_MODEL=3
```

Optional documented pen-lift tuning settings:

```bash
export LEARN_TO_DRAW_AXIDRAW_PEN_POS_UP=60
export LEARN_TO_DRAW_AXIDRAW_PEN_POS_DOWN=30
export LEARN_TO_DRAW_AXIDRAW_PEN_RATE_RAISE=75
export LEARN_TO_DRAW_AXIDRAW_PEN_RATE_LOWER=50
export LEARN_TO_DRAW_AXIDRAW_PEN_DELAY_UP=0
export LEARN_TO_DRAW_AXIDRAW_PEN_DELAY_DOWN=0
export LEARN_TO_DRAW_AXIDRAW_PENLIFT=1
```

The real adapter expects the official `pyaxidraw` package to be installed separately.
In practice, the vendor-documented unpack-and-install flow (`pip install .` from the
unpacked AxiDraw API archive) is what produced the importable `pyaxidraw` module here.

Optional AxiDraw config override settings:

```bash
export LEARN_TO_DRAW_AXIDRAW_CONFIG_PATH=/absolute/path/to/axidraw_conf.py
export LEARN_TO_DRAW_AXIDRAW_NATIVE_RES_FACTOR=1905.0
```

`LEARN_TO_DRAW_AXIDRAW_CONFIG_PATH` points to an explicit vendor-style config file.
`LEARN_TO_DRAW_AXIDRAW_NATIVE_RES_FACTOR` generates a temporary override config from the
vendor default without editing the installed package in place. If both are set, the explicit
config path wins.

Persisted plotter calibration is stored separately under:

```text
artifacts/calibration/plotter.json
```

For this slice, the authoritative persisted value is AxiDraw-specific
`driver_calibration.native_res_factor`; the app also stores a derived generic
`motion_scale` alongside it for future plotter support. Effective precedence is:

1. `LEARN_TO_DRAW_AXIDRAW_NATIVE_RES_FACTOR`
2. persisted `artifacts/calibration/plotter.json`
3. vendor default config

The Plotter card can save the persisted value through the backend. If an env override
is active, the saved calibration is kept on disk but does not become effective until
the override is removed and the backend restarts.

## Plot sizing, bounds, and workspace

Built-in patterns now use explicit physical `mm` dimensions so AxiDraw plotting stays deterministic.
Uploaded SVG sizing is prepared in the backend before the plotter adapter runs.

Stable backend plotter-bounds settings:

```bash
export LEARN_TO_DRAW_PLOTTER_BOUNDS_WIDTH_MM=210
export LEARN_TO_DRAW_PLOTTER_BOUNDS_HEIGHT_MM=297
```

Default session page-setup settings:

```bash
export LEARN_TO_DRAW_PLOT_PAGE_WIDTH_MM=210
export LEARN_TO_DRAW_PLOT_PAGE_HEIGHT_MM=297
export LEARN_TO_DRAW_PLOT_MARGIN_LEFT_MM=20
export LEARN_TO_DRAW_PLOT_MARGIN_TOP_MM=20
export LEARN_TO_DRAW_PLOT_MARGIN_RIGHT_MM=20
export LEARN_TO_DRAW_PLOT_MARGIN_BOTTOM_MM=20
```

Optional workspace storage override:

```bash
export LEARN_TO_DRAW_WORKSPACE_DIR=/absolute/path/to/workspace
```

The app now treats sizing constraints as two separate layers:

- `plotter bounds`: the maximum safe physical area for the machine
- `session paper setup`: the current page size and margins mounted in the app

For the AxiDraw driver, the app also keeps a separate device-settings record under:

```text
artifacts/device_settings/plotter.json
```

If `LEARN_TO_DRAW_AXIDRAW_MODEL` is explicitly set, the backend derives default plotter
bounds from the same vendor travel constants used by the AxiDraw stack and surfaces a
descriptive model label in the Plotter card. Effective bounds precedence is:

1. `LEARN_TO_DRAW_PLOTTER_BOUNDS_WIDTH_MM` / `LEARN_TO_DRAW_PLOTTER_BOUNDS_HEIGHT_MM`
2. model-derived AxiDraw bounds when `LEARN_TO_DRAW_AXIDRAW_MODEL` is explicitly configured
3. backend config defaults

The normal UI does not edit plotter bounds directly. It shows the current model, effective
bounds, and bounds source read-only, while page size and margins remain editable session
state through the backend.

The persisted session workspace lives under:

```text
artifacts/workspace/plotter.json
```

The Plotter card can update page width, page height, and margins through the backend.
The backend computes a drawable area from that session setup and validates that it stays
inside the stable plotter bounds.

Current sizing modes:

- `native`: requires explicit physical SVG dimensions such as `mm`, `cm`, or `in`, preserves the authored size, and fails if the authored result exceeds the current drawable area
- `fit_to_draw_area`: scales uniformly into the current drawable area while preserving aspect ratio

Unitless uploaded SVGs are rejected in `native` mode and allowed in `fit_to_draw_area` mode with inferred sizing metadata. In both modes, the backend refuses prepared output that would exceed the current drawable area or the configured plotter bounds.
