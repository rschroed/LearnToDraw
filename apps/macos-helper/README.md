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

To package a real `.app` bundle without installing it:

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
./scripts/install-app.sh --open
```

If `/Applications` requires elevated privileges on your machine:

```sh
sudo ./scripts/install-app.sh --open
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

The helper is intended to run as a single app instance. Reopening the app or custom URL scheme
should reuse the existing helper process rather than leaving multiple menu-bar helpers active.

Example:

```sh
curl -X POST http://127.0.0.1:8001/start
curl http://127.0.0.1:8001/status
```

When the helper starts the backend, it always uses:

- `PYTHONPATH=src`
- `LEARN_TO_DRAW_CAMERA_DRIVER=opencv`

It forwards these optional camera environment variables from the helper process when present:

- `LEARN_TO_DRAW_OPENCV_CAMERA_INDEX`
- `LEARN_TO_DRAW_CAMERA_WARMUP_MS`
- `LEARN_TO_DRAW_CAMERA_DISCARD_FRAMES`

The helper is plotter-neutral. It does not configure plotter mode, inject AxiDraw settings,
or package plotter configuration into the app bundle. Plotter behavior remains owned by the
backend's normal environment and configuration.

For a repeatable real-camera smoke pass with the helper-managed backend:

1. Launch the helper with the desired plotter environment and any optional `LEARN_TO_DRAW_OPENCV_CAMERA_INDEX` override already exported.
2. Confirm `GET /status` reports the helper as reachable and `POST /start` moves it to `running`.
3. Verify the backend on `127.0.0.1:8000` is healthy and inspect `/api/hardware/status` for the camera details.
4. Trigger one `POST /api/camera/capture` and confirm `/api/captures/latest` returns the new JPEG metadata.
5. Check the helper `instance_id` / `helper_instance_id` and `helper_launched_at` fields in `/status` while repeating opens to confirm you are still talking to the same helper process.

This helper flow keeps camera index selection env-driven. If the default index is wrong, relaunch
the helper with a different `LEARN_TO_DRAW_OPENCV_CAMERA_INDEX` value rather than adding runtime UI controls.
