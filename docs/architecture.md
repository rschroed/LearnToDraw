# Slice 1 Architecture

## Goals

- keep the system local-first
- keep hardware control in the backend
- stay modular enough for future real-device adapters
- avoid premature orchestration or iterative drawing logic
- add one end-to-end plotting workflow before building the closed loop

## Backend

The backend is the source of truth for hardware state and action execution.

- `models.py` holds shared API and domain models plus hardware exceptions
- `adapters/` defines plotter and camera contracts and mock implementations
- `services/hardware.py` coordinates status reads and command execution
- `services/captures.py` persists capture artifacts and reloads the latest metadata
- `services/plot_workflow.py` stores SVG assets, tracks plot runs, and advances runs through prepare, plot, and capture stages
- `api.py` exposes a thin REST surface and static serving for capture previews

## Frontend

The frontend is a small local control panel.

- polls hardware status and latest capture
- polls latest plot run and recent plot runs
- triggers `home` and `capture` through REST calls
- uploads SVGs or creates a built-in test pattern
- shows current state, action progress, errors, and planned-vs-captured comparison

## Future extension points

- keep the `pyaxidraw` wrapper isolated so a more durable runner can replace the current in-process execution model later
- expand the real AxiDraw adapter before replacing the mock camera
- replace the in-process plot-run executor once longer-running or queued work is needed
- add drawing generation and iterative analysis as separate services without moving hardware access into the browser
