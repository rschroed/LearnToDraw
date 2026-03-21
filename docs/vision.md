# LearnToDraw Vision

> If a change does not help compare **planned vs observed**, it is likely not core to the system.

## What This Is

LearnToDraw is a **closed-loop drawing system** that connects intent, execution, and physical observation.

It is not just a tool that generates drawings.
It is a system that **draws, observes the result, and improves over time**.

## Core Loop

Every part of the system exists to support this loop:

Intent -> Plan -> Plot -> Observe -> Compare -> Adjust

- **Intent**: what we want to draw
- **Plan**: how the system prepares that drawing
- **Plot**: the physical execution
- **Observe**: what actually happened (camera capture)
- **Compare**: understand what happened in the physical result, using the plan as context (not as a strict target for replication)
- **Adjust**: future corrections (alignment, strategy, etc.)

## Core Primitive: PlotRun

A `PlotRun` is the atomic unit of the system.

Each run represents a single attempt and contains:

- **planned**: source asset and preparation details
- **prepared**: transformed or ready-to-plot representation
- **observed_result**: what was physically captured after execution

The system does not reason about drawings directly.
It reasons about **runs over time**.

## Key Principle: Reality Over Assumptions

Most plotting systems assume:

- perfect motion
- perfect alignment
- perfect surfaces

LearnToDraw assumes:

- drift exists
- materials vary
- execution is imperfect

Instead of avoiding error, the system:

- captures it
- records it
- uses it

## Interpretation Over Fidelity

The goal of the system is not to perfectly reproduce the planned drawing.

The goal is to:

- understand what was produced on the page
- interpret that result
- decide what to do next

The prepared drawing is one source of intent, not the ground truth.

Future iterations may:

- reinforce parts of the drawing
- add new structure
- change composition
- intentionally diverge from the original plan

Comparison is used for understanding, not strict error correction.

## What This Is Not

To prevent drift, this project is not:

- just a plotter controller
- just a camera capture tool
- just an SVG processing pipeline
- just a desktop app or helper service

Those are **supporting components**, not the product.

The product is:

> the feedback loop between intention and physical result

## Current Focus

The system is being built incrementally.

Current milestone:

- establish **run-scoped observed results**
- reliably capture what happened during a run
- make planned vs observed visible for inspection

This enables the next step:

- comparison and alignment

## Direction (Not Yet Implemented)

Future capabilities build on the same loop:

- alignment between planned and observed output
- drift detection and correction
- multi-pass drawing (iterative refinement)
- system-specific learning (machine, pen, surface)

## Design Constraint

The system should evolve toward:

> a machine that gets better at drawing **on its specific physical setup over time**

Not:

- generic rendering perfection
- one-shot output

## Guiding Question

When making changes, ask:

> "Does this help the system understand what it meant to draw vs what actually happened?"

If not, it is likely infrastructure or supporting work, not core progress.
