# AGENTS.md

## Project Overview
LearnToDraw is a local-first pen-plotter control app.

Current architecture:
- `apps/api`: FastAPI backend, owns all hardware access
- `apps/web`: React/Vite frontend, localhost control panel only
- `artifacts/`: local captures, plot assets, and plot run metadata

Backend is the system of record for:
- plotter control
- camera control
- hardware status
- plot run execution
- local artifact persistence

Frontend must never access hardware directly.

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

## Practical Notes
- Use `rg` for search.
- Prefer `apply_patch` for edits.
- Do not revert unrelated user changes.
- Ignore generated folders like `node_modules`, `dist`, and caches unless the task is specifically about them.
