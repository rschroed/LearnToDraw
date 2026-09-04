# LearnToDraw

LearnToDraw is a local-first creative studio for a pen plotter that can draw, photograph its work, interpret the result, and add another pass. The backend owns hardware access, plot execution, and artifact persistence; the frontend stays a lightweight localhost interface.

## What It Does

- Runs a FastAPI backend that stays responsible for plotter and camera access
- Provides a prompt-first React/Vite studio with an artwork canvas and compact agent conversation
- Keeps session history in Gallery and machine setup, diagnostics, capture tools, and manual SVG plotting in Controls
- Supports tracked plot runs from uploaded SVGs or built-in patterns
- Persists captures, plot assets, plot runs, versioned drawing sessions, calibration, and workspace/device settings locally
- Supports both mock adapters for development and a real AxiDraw-backed plotter path
- Supports both mock camera capture and a CameraBridge-backed real camera path

## Architecture At A Glance

- `apps/api` is the system of record for hardware status, commands, plot workflow orchestration, and artifact persistence
- `apps/web` is a localhost creative interface that polls backend HTTP endpoints and never talks to hardware directly
- `artifacts/` stores local captures, prepared plot assets, plot-run records, calibration data, and workspace/device state
- AxiDraw-specific behavior stays isolated in backend adapters and wrappers

## Repo Layout

- `apps/api`: FastAPI backend, services, adapters, and models
- `apps/web`: React/Vite dashboard
- `artifacts/`: local captures, plot assets, plot runs, drawing sessions, calibration, and workspace/device state
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

## Optional Drawing Advisor

Agentic drawing sessions begin with a plan and safe first-pass preview before motion. One explicit approval authorizes an attended sequence of additive plot, capture, and assessment cycles; stop, heartbeat, registration, and recovery boundaries remain backend-enforced. The visual drawing advisor is disabled by default. To enable the OpenAI Responses API adapter, set:

```bash
export LEARN_TO_DRAW_DRAWING_ADVISOR=openai
export OPENAI_API_KEY=YOUR_API_KEY
export LEARN_TO_DRAW_OPENAI_MODEL=YOUR_IMAGE_CAPABLE_MODEL
```

The configured model must accept image input and structured JSON output. The adapter sends the registered grayscale observation and drawing intent, then accepts only interpretation text and a bounded SVG layer. API credentials are read from the environment and are never persisted in artifacts. For local contract testing without an external request, use `LEARN_TO_DRAW_DRAWING_ADVISOR=mock`.

The implementation uses the official [Responses API](https://platform.openai.com/docs/api-reference/responses/create) contract. Model availability and billing depend on the OpenAI API project associated with the supplied key.

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
