# LearnToDraw

LearnToDraw is a local-first control panel for a pen-plotter workflow. The backend owns hardware access, plot execution, and artifact persistence; the frontend is a lightweight localhost dashboard for monitoring and safe control.

## What It Does

- Runs a FastAPI backend that stays responsible for plotter and camera access
- Provides a React/Vite operator UI with focused Workflow, Machine, and History views
- Supports tracked plot runs from uploaded SVGs or built-in patterns
- Persists captures, plot assets, plot runs, calibration, and workspace/device settings locally
- Supports both mock adapters for development and a real AxiDraw-backed plotter path
- Supports both mock camera capture and a CameraBridge-backed real camera path

## Architecture At A Glance

- `apps/api` is the system of record for hardware status, commands, plot workflow orchestration, and artifact persistence
- `apps/web` is a localhost dashboard that polls backend HTTP endpoints and never talks to hardware directly
- `artifacts/` stores local captures, prepared plot assets, plot-run records, calibration data, and workspace/device state
- AxiDraw-specific behavior stays isolated in backend adapters and wrappers

## Repo Layout

- `apps/api`: FastAPI backend, services, adapters, and models
- `apps/web`: React/Vite dashboard
- `artifacts/`: local captures, plot assets, plot runs, calibration, and workspace/device state
- `docs/`: architecture notes, project history, and manual test assets

## Quick Start

Install dependencies:

```bash
make api-install
make web-install
```

Start the backend and frontend:

```bash
make api-dev
make web-dev
```

Then open [http://127.0.0.1:5173](http://127.0.0.1:5173).

By default, the backend runs against the mock plotter path so the app can be explored locally without hardware.

Camera capture also defaults to the mock adapter. For frontend testing with a real local camera, use:

```bash
make api-dev-camera
```

That keeps the plotter on the mock backend and starts the API with the CameraBridge adapter enabled.

If you need to start the backend manually instead, install the backend dependencies with `make api-install` and set:

```bash
export LEARN_TO_DRAW_CAMERA_DRIVER=camerabridge
```

LearnToDraw supports CameraBridge against an explicit tested `v0.1.x` range, audited and smoke-validated against the published `v0.1.2` localhost runtime contract, and relies on CameraBridge's localhost service plus support-directory artifacts. Optional CameraBridge env vars:

```bash
export LEARN_TO_DRAW_CAMERABRIDGE_BASE_URL=http://127.0.0.1:8731
export LEARN_TO_DRAW_CAMERABRIDGE_TOKEN_PATH="$HOME/Library/Application Support/CameraBridge/auth-token"
export LEARN_TO_DRAW_CAMERABRIDGE_OWNER_ID=learntodraw-api
export LEARN_TO_DRAW_CAMERABRIDGE_DEFAULT_DEVICE_ID=camera-1
```

If `LEARN_TO_DRAW_CAMERABRIDGE_BASE_URL` is not set, LearnToDraw checks `~/Library/Application Support/CameraBridge/runtime-configuration.json` and otherwise falls back to `http://127.0.0.1:8731`. The auth token defaults to `~/Library/Application Support/CameraBridge/auth-token`.

CameraBridge is not assumed to be running just because it is installed. Start `CameraBridgeApp`, click `Start CameraBridge Service`, and if needed click `Request Camera Access`. LearnToDraw surfaces those readiness steps through backend camera status and the dashboard.

## Mock Vs Real Hardware

For mock-backed local development:

```bash
make api-dev-mock
```

For a real AxiDraw-backed backend:

```bash
make api-dev-axidraw
```

The real AxiDraw path also requires the vendor `pyaxidraw` package to be installed separately and an explicit machine definition via either:

```bash
export LEARN_TO_DRAW_AXIDRAW_MODEL=1
```

or explicit machine bounds:

```bash
export LEARN_TO_DRAW_PLOTTER_BOUNDS_WIDTH_MM=300
export LEARN_TO_DRAW_PLOTTER_BOUNDS_HEIGHT_MM=218
```

Additional AxiDraw tuning remains backend-owned and is configured through backend environment variables rather than browser controls.

## Testing

Run the backend and frontend test suites with:

```bash
make api-test
make web-test
```

To verify the frontend production build:

```bash
cd apps/web
npm run build
```

## Further Docs

- [Architecture](docs/architecture.md): current system structure and boundaries
- [Workflow](docs/workflow.md): branch, PR, and cleanup rules for keeping the repo tidy
- [Project history](docs/history.md): internal slice-by-slice evolution notes
- [Manual test assets](docs/manual-test-assets): SVGs used for plot sizing and bounds checks
