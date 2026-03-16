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

## Repo layout

- `apps/api`: Python backend API and hardware layer
- `apps/web`: local dashboard UI
- `artifacts/captures`: locally saved mock camera captures
- `artifacts/plot_assets`: stored planned SVG assets
- `artifacts/plot_runs`: stored plot-run metadata
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
