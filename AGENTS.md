# AGENTS.md

## Project Overview
LearnToDraw is a local-first pen-plotter control app.

Current architecture:
- `apps/api`: FastAPI backend, owns all hardware access
- `apps/web`: React/Vite frontend, localhost control panel only
- `artifacts/`: local captures, plot assets, plot run metadata, calibration, device settings, and workspace state

Backend is the system of record for:
- plotter control
- camera control
- hardware status
- plot run execution
- local artifact persistence

Frontend must never access hardware directly.

Docs intent:
- `README.md` is the GitHub-facing project entry point and should stay concise.
- `docs/architecture.md` is the current internal architecture reference.
- `docs/history.md` is the internal slice-by-slice evolution log.

## Working Principles
- Preserve the local-first architecture.
- Keep hardware control in the backend.
- Keep driver-specific behavior isolated in adapters and wrappers.
- Prefer maintainability and explicitness over clever abstractions.
- Do not introduce the iterative drawing engine unless explicitly asked.
- Avoid broad UI or config surfaces for hardware tuning unless clearly necessary.

## Architecture Guardrails
- App-facing plotter behavior should stay generic and backend-owned.
- Do not couple services or routes directly to AxiDraw-specific APIs.
- Keep AxiDraw differences isolated inside the wrapper and adapter.
- Mock adapters must remain intact and usable for development and tests.
- Prefer extending the existing plot-run model over inventing parallel workflows, unless the distinction is architecturally important.
- If a behavior is not documented in the official AxiDraw API docs, do not assume it. Call out installed-package differences explicitly.

## Backend Conventions
- Keep route handlers thin.
- Put orchestration in services.
- Put hardware behavior in adapters.
- Keep filesystem paths and public URLs separate for stored artifacts.
- Prefer explicit run state transitions over implied state from side effects.
- Treat `return_to_origin` as positioning semantics, not true hardware homing.
- Keep diagnostic actions fixed and narrow; do not grow them into a second plotting API.

## Frontend Conventions
- Frontend is a lightweight local dashboard, not a hardware driver.
- Prefer small, explicit controls over large control surfaces.
- Poll HTTP endpoints; do not add browser-side hardware integration.
- Keep AxiDraw-specific UI minimal and only where justified.
- Prefer read-only hardware detail displays plus a few safe actions.

## AxiDraw Rules
- Official source of truth: https://axidraw.com/doc/py_api/
- Distinguish clearly between Plot context and Interactive context.
- Prefer documented Plot-context methods and options for production behavior.
- If the installed package differs from the docs, isolate that mismatch in the wrapper.
- Do not leak compat-path behavior outside the wrapper or adapter.
- Pen tuning should stay backend or config driven by default.
- Safe built-in hardware test patterns are preferred over arbitrary freeform motion tools.

## Runtime Tuning Rules
- Browser controls may update safe runtime hardware settings only when the backend remains the sole authority.
- Runtime tuning changes must be clearly labeled as session-only unless they are also persisted to config.
- If a UI control changes AxiDraw tuning, surface the effective value back through hardware status.

## Done Means
A task is not complete unless:
- relevant automated tests pass, or the reason they could not be run is stated clearly
- docs or config notes are updated if behavior changed
- mock adapters still work unless the task explicitly changes them
- new env vars or hardware assumptions are documented
- remaining uncertainty or risk is called out clearly

## Planning Guidance
Write a narrow implementation plan before editing when work:
- touches both frontend and backend
- changes hardware contracts
- changes plot-run or artifact models
- depends on undocumented or version-sensitive hardware behavior

## Testing Expectations
Before finishing substantial work:
- backend: `make api-test`
- frontend: `make web-test`
- frontend build: `npm run build` in `apps/web`

When changing hardware behavior:
- add or update backend adapter tests
- preserve mock-adapter coverage
- verify plot-run behavior for both normal and diagnostic cases

## Safe Changes
Safe by default:
- backend API changes that preserve the backend-owned hardware model
- mock adapter improvements
- small UI additions for status and safe diagnostics
- artifact, model, and test updates aligned with the current architecture

Needs explicit discussion first:
- browser-side hardware access
- replacing polling with a more complex execution model
- broad hardware tuning UI
- changes that blur diagnostic runs and normal runs
- undocumented AxiDraw behavior assumptions
- iterative drawing engine work

## Hardware UI Limits
- Hardware-panel controls should stay narrow, diagnostic, and reversible.
- Do not add arbitrary motion controls or freeform command entry without explicit discussion.
- Prefer fixed safe actions and fixed small test patterns over generic manual control.

## AxiDraw Persistence Note
- Distinguish between config-backed defaults and runtime-only tuning.
- If a tuning control is session-only, document that in the UI or user-facing notes.

## Practical Notes
- Use `rg` for search.
- Prefer `apply_patch` for edits.
- Do not revert unrelated user changes.
- Ignore generated folders like `node_modules`, `dist`, and caches unless the task is specifically about them.

## Git Hygiene
- Keep generated runtime artifacts out of git; retain only placeholder files like `.gitkeep` where needed.
- Do not commit generated frontend build output or TypeScript build-info files.
- Prefer small commits at slice boundaries, especially before hardware-facing changes.
- If a task starts from `main`, create a short-lived `codex/` branch before making edits unless the user explicitly asks to work directly on `main`.

## Remote Workflow
- Primary remote is GitHub.
- Keep `main` stable and push working slice boundaries, not half-finished hardware experiments.
- Before pushing hardware-related changes, make sure relevant tests pass or state clearly what was not verified.
- Prefer short-lived branches for risky adapter or hardware-control changes.
- Use `codex/` as the branch prefix for agent-created branches.
