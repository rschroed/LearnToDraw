# LearnToDraw macOS Camera Helper

This helper is a macOS-first proof of concept for backend-owned real camera startup.

It does three things:

- runs as a native macOS helper process
- starts the existing FastAPI backend in OpenCV camera mode
- exposes localhost helper endpoints on `127.0.0.1:8001`

The helper does not proxy hardware requests. The backend on `127.0.0.1:8000` remains the only hardware authority.

## Build and run

From `apps/macos-helper`:

```sh
swift run LearnToDrawCameraHelper
```

To package a real `.app` bundle for macOS permission testing:

```sh
swift build
./scripts/package-app.sh ~/Desktop/LearnToDrawCameraHelper.app
open ~/Desktop/LearnToDrawCameraHelper.app
```

The packaged app embeds the current repo root so it can be moved to `~/Desktop`,
`/Applications`, or another stable location and still launch the backend from the
same checkout.

Recommended stable install location:

```sh
./scripts/package-app.sh /Applications/LearnToDrawCameraHelper.app
open /Applications/LearnToDrawCameraHelper.app
```

The custom URL scheme `learntodraw-helper://open` only works when macOS LaunchServices
has registered a stable installed bundle that claims that scheme. `/Applications` is
the recommended location. Temporary copies such as `/tmp` may launch manually but are
not a reliable URL-scheme target.

The helper also registers the custom URL scheme `learntodraw-helper://open`, which
the dashboard can use to prompt macOS to open the app when it is missing.

The helper exposes:

- `GET /status`
- `POST /start`
- `POST /stop`
- `POST /restart`

Example:

```sh
curl -X POST http://127.0.0.1:8001/start
curl http://127.0.0.1:8001/status
```

When the helper starts the backend, it uses:

- `PYTHONPATH=src`
- `LEARN_TO_DRAW_PLOTTER_DRIVER=mock`
- `LEARN_TO_DRAW_CAMERA_DRIVER=opencv`

It forwards these optional environment variables from the helper process when present:

- `LEARN_TO_DRAW_OPENCV_CAMERA_INDEX`
- `LEARN_TO_DRAW_CAMERA_WARMUP_MS`
- `LEARN_TO_DRAW_CAMERA_DISCARD_FRAMES`
