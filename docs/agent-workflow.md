# Agent Workflow

This document is the internal execution playbook for Codex-driven work in this repo. It complements [workflow.md](workflow.md), which stays focused on branch and PR hygiene.

## Default Delivery Loop

Use this loop for every implementation slice:

1. Explore the relevant code, docs, and tests first.
2. Write a short pre-edit plan.
3. Implement one narrow slice on a short-lived `codex/<topic>` branch.
4. Run the relevant verification.
5. Summarize what changed, what was verified, and any remaining risk.

Keep repo vocabulary aligned with `AGENTS.md`, the PR template, and `docs/workflow.md`. Do not create a second policy layer.

## Mandatory Pre-Edit Plan

Write this before editing any code or docs:

```md
Goal:

In scope:
- ...

Out of scope:
- ...

Expected files or subsystems:
- ...

Verification:
- ...

Risks or assumptions:
- ...
```

Every slice needs this short form. Expand it only when the work is higher risk.

## When To Expand The Plan

Use the short plan for simple backend-only or frontend-only slices. Write an expanded plan when work is:

- cross-stack
- hardware-facing
- changing a data or artifact model
- version-sensitive
- relying on undocumented behavior

An expanded plan should still stay brief, but it must also name:

- interface or contract changes
- data flow and state transitions affected
- failure modes or edge cases worth verifying
- tests or checks that prove the risky path still works

## Primary Playbooks

### Backend-Only Slice

- Explore the affected route, service, adapter, and tests before editing.
- Keep route handlers thin and put orchestration in services.
- Keep hardware behavior in adapters and wrappers.
- Extend existing backend-owned models instead of creating parallel flows unless the distinction matters architecturally.
- Run `make api-test`.
- Run `make api-lint` when touching backend validation, typing, lint-sensitive code, or shared backend plumbing.
- Update docs or config notes when behavior, env vars, or hardware assumptions change.

### Frontend-Only Slice

- Explore the backend contract first so the UI stays dashboard-only and backend-owned.
- Keep controls narrow, explicit, and reversible.
- Poll existing HTTP endpoints; do not add browser-side hardware integration.
- Prefer read-only hardware detail plus a few safe actions.
- Run `make web-test`.
- Run `make web-build` when changing app code, routing, state flow, or production build behavior.
- Run `make web-lint` when touching frontend lint-sensitive code, project tooling, or shared UI plumbing.

### Cross-Stack Slice

- Write the expanded plan before editing.
- Define the backend contract first, then update the frontend to consume it.
- Keep the backend as the sole owner of hardware access, plot execution, and artifact persistence.
- Call out any model, artifact, or state-transition changes explicitly in the plan and PR.
- Run `make api-test`, `make web-test`, and `make web-build`.
- Run the relevant lint checks when touching shared contracts, tooling, or quality-sensitive paths.

## Secondary Checklists

### Hardware-Sensitive Change Checklist

- Confirm the behavior is documented by the official AxiDraw API before assuming it.
- Keep AxiDraw-specific behavior inside adapters and wrappers.
- Preserve mock adapter behavior and coverage unless the task intentionally changes it.
- Treat `return_to_origin` as positioning semantics, not true homing.
- Keep diagnostic actions fixed and narrow; do not expand them into a second plotting API.
- Document new env vars, runtime-only tuning, hardware assumptions, or package-version differences.
- Verify both the normal and diagnostic plot-run paths when hardware behavior changes.

### PR Readiness / Review Cleanup Checklist

- Branch is still a narrow `codex/<topic>` slice.
- PR summary explains the behavioral or architectural change, not just the mechanics.
- The short plan or expanded plan is reflected in the PR summary.
- Relevant checks ran, and skipped checks are called out with reasons.
- Hardware assumptions, undocumented behavior, and residual risk are called out when relevant.
- Docs and config notes were updated if behavior changed.
- Merged or stale local branches are cleaned up when the branch is no longer needed.

## Done Means

A slice is not done unless:

- relevant automated tests passed, or the reason they were not run is stated clearly
- docs or config notes were updated if behavior changed
- mock adapters still work unless the task explicitly changed them
- new env vars or hardware assumptions are documented
- remaining uncertainty or risk is called out clearly

## Dry-Run Examples

### Backend-Only Example

```md
Goal:
Add a backend-owned plot run status detail to the API response.

In scope:
- plot workflow service
- response model
- backend tests

Out of scope:
- dashboard UI changes
- hardware behavior changes

Expected files or subsystems:
- apps/api route or model layer
- plot workflow service
- backend tests

Verification:
- make api-test

Risks or assumptions:
- Existing run-state transitions stay unchanged.
```

### Cross-Stack Example

```md
Goal:
Expose a new workspace warning in the backend and render it in the dashboard.

In scope:
- backend response contract
- frontend polling consumer
- backend and frontend tests

Out of scope:
- plotter tuning changes
- new hardware actions

Expected files or subsystems:
- backend workspace service or response models
- frontend dashboard consumer and tests

Verification:
- make api-test
- make web-test
- make web-build

Risks or assumptions:
- Backend remains the sole owner of workspace validation.
- Existing polling cadence remains unchanged.
```
