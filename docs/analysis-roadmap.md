# Interpretation-Oriented Analysis Roadmap

## Summary

LearnToDraw should move from planned/prepared/observed inspection to aligned observed-result analysis for interpretation and future iteration.

The prepared drawing is context, not a strict target for replication.

This roadmap keeps the existing slice sequencing and backend-owned transform model, but changes the outputs from comparison, diff, and correction language to rectified observation, derived views, and next-step guidance.

## Principle: Interpretation Over Fidelity

The system does not aim to reproduce the planned drawing exactly.

Aligned observation exists to support interpretation of what was physically produced, and to inform future drawing decisions.

The prepared drawing is one input to that interpretation, not the ground truth.

## Slice 1: Manual Registration And Rectified Observation

- Keep manual page-corner registration as the first alignment step.
- Keep all transform and artifact generation in the backend.
- Keep analysis data attached to `PlotRun` as run-scoped state.
- Replace `comparison_result` with `analysis_result`.
- Use the rectified observed image as the canonical Slice 1 artifact.
- Keep planned and prepared outputs visible in the UI as context for interpretation.
- Do not make overlay or diff the primary outcome for this slice.

Expected backend shape:

- `PlotRun.analysis_result`
- backend-owned manual registration route for completed normal runs with an `observed_result`
- rectified observed artifact persisted with the run's other plot-run artifacts

Expected frontend shape:

- the operator selects the page corners in the observed image
- the backend produces the rectified observed result
- the dashboard shows the rectified observed result alongside planned and prepared context

## Slice 2: Derived Views And Interpretation Signals

- Keep the slice boundary after registration and rectification.
- Replace `difference_artifact` with `derived_views` or `analysis_artifacts`.
- Frame all derived outputs as aids for understanding the physical result, not as fidelity scoring.
- Prefer coarse physical-result signals such as drawn-area bounds, occupancy, density regions, structure hints, and image-quality or confidence indicators.
- Keep any image-processing view secondary to the rectified observed artifact.

## Slice 3: Read-Only Next-Step Guidance

- Replace `suggested_adjustment` with `suggested_next_step`.
- Keep this guidance optional and read-only.
- Allow the next step to cover more than geometric correction, including reinforcement, added structure, density changes, composition extension, or alignment correction where warranted.
- Keep the suggestion tied to a specific run and `analysis_result`, not promoted to machine-wide truth.

## Acceptance Criteria

- Roadmap language does not frame strict replication as the primary goal.
- Slice 1 success is that a rectified observed result exists and is usable for interpretation.
- Planned backend and frontend naming uses `analysis_result`, `derived_views` or `analysis_artifacts`, and `suggested_next_step`.
- Manual registration, backend ownership, run-scoped persistence, and slice sequencing remain unchanged.

## Assumptions

- Manual page-corner registration remains the first analysis path.
- The prepared drawing remains contextual input rather than ground truth.
- The `PlotRun` record remains the atomic workflow and analysis record.
