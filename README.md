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
- backend-owned drawable-area preparation for normal plots
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
For explicit driver startup, use:

```bash
make api-dev-mock
make api-dev-axidraw
```

These targets keep driver selection backend-owned and require a backend restart when you switch modes.
Any AxiDraw-specific env overrides already in your shell still apply to `make api-dev-axidraw`.

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

The backend still defaults to the mock plotter. For local switching, prefer:

```bash
make api-dev-mock
make api-dev-axidraw
```

If you need to launch the backend another way, set:

```bash
export LEARN_TO_DRAW_PLOTTER_DRIVER=axidraw
```

Real AxiDraw no longer falls back to a generic hard-coded machine size. You must also
configure either:

```bash
export LEARN_TO_DRAW_AXIDRAW_MODEL=1
```

or explicit machine bounds:

```bash
export LEARN_TO_DRAW_PLOTTER_BOUNDS_WIDTH_MM=300
export LEARN_TO_DRAW_PLOTTER_BOUNDS_HEIGHT_MM=218
```

For a V2/V3/SE A4 machine, `300 × 218 mm` is the observed safe bound to configure,
but it is now an explicit example config rather than an implicit backend fallback.

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
export LEARN_TO_DRAW_PLOTTER_BOUNDS_WIDTH_MM=300
export LEARN_TO_DRAW_PLOTTER_BOUNDS_HEIGHT_MM=218
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

For the real AxiDraw driver, one of those two sources is now required. If neither is
configured, the backend stays up but marks the plotter unavailable until explicit machine
bounds or an explicit AxiDraw model are provided.

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

If corrected machine bounds make the saved paper setup invalid, `GET /api/plotter/workspace`
now returns the persisted workspace plus `is_valid=false` and a `validation_error` message
so the UI can stay usable while plotting remains blocked until the paper setup is fixed.

Normal plotting now uses a single backend-owned preparation path:

- normal runs are prepared into page-mm coordinates and anchored at the drawable area's top-left origin
- uploaded SVGs with explicit physical units keep their authored size when already within the drawable area and are only downscaled when oversized
- unitless or px-only uploads are max-fit into the drawable area
- the normal built-in `test-grid` uses this same preparation path
- dedicated hardware diagnostics stay fixed-size and use a separate diagnostic passthrough path

The backend refuses prepared output that would exceed the current drawable area or the configured plotter bounds.

Each plot run now also records a preparation audit in the run metadata, including:

- the effective plotter bounds, page size, and drawable area used for the run
- derived workspace math such as drawable origin and remaining bounds headroom
- preparation details such as strategy, placement origin, prepared content box, root `viewBox`, scale, and any computed overflow

The Plot Workflow panel shows this audit as a compact read-only summary so bounds,
workspace math, and prepared placement can be inspected alongside each run.
