import type { DrawingSession } from "../../types/drawing";
import type { PlotRun } from "../../types/plotting";

export type StudioProgressStepId =
  | "plan"
  | "draw"
  | "photograph"
  | "register"
  | "reflect";

export type StudioProgressStepState = "pending" | "active" | "complete" | "attention";

export interface StudioProgressStep {
  id: StudioProgressStepId;
  label: string;
  state: StudioProgressStepState;
}

export interface StudioProgressModel {
  title: string;
  detail: string;
  passLabel: string;
  tone: "active" | "attention" | "complete" | "failed";
  steps: StudioProgressStep[];
}

const STEP_LABELS: Array<{ id: StudioProgressStepId; label: string }> = [
  { id: "plan", label: "Plan" },
  { id: "draw", label: "Draw" },
  { id: "photograph", label: "Photograph" },
  { id: "register", label: "Register" },
  { id: "reflect", label: "Reflect" },
];

function passNumber(session: DrawingSession): number {
  const currentIteration = session.current_run_id
    ? session.iterations.find((iteration) => iteration.run_id === session.current_run_id)
    : null;
  return currentIteration?.number ?? Math.max(1, session.pass_count);
}

function inferRunStep(run: PlotRun | null): StudioProgressStepId {
  if (!run) return "draw";
  if (run.status === "awaiting_capture_review") return "register";
  if (run.status === "capturing" || run.stage_states.capture.status === "in_progress") {
    return "photograph";
  }
  if (
    run.status === "pending" ||
    run.status === "plotting" ||
    run.status === "stopping" ||
    run.stage_states.prepare.status === "in_progress" ||
    run.stage_states.plot.status === "in_progress"
  ) {
    return "draw";
  }
  return "reflect";
}

function stepsFor(
  activeStep: StudioProgressStepId,
  state: "active" | "attention" = "active",
  allComplete = false,
): StudioProgressStep[] {
  const activeIndex = STEP_LABELS.findIndex((step) => step.id === activeStep);
  return STEP_LABELS.map((step, index) => ({
    ...step,
    state: allComplete
      ? "complete"
      : index < activeIndex
        ? "complete"
        : index === activeIndex
          ? state
          : "pending",
  }));
}

function activeRunModel(session: DrawingSession, run: PlotRun | null): StudioProgressModel {
  const number = passNumber(session);
  if (session.assessing_run_id) {
    return {
      title: `Looking at pass ${number}`,
      detail:
        "The advisor is studying the registered photograph and deciding whether another layer would improve the drawing.",
      passLabel: `Pass ${number}`,
      tone: "active",
      steps: stepsFor("reflect"),
    };
  }
  if (!run) {
    return {
      title: `Preparing pass ${number}`,
      detail: "The studio is creating the next safe physical action. The plotter has not started this pass yet.",
      passLabel: `Pass ${number}`,
      tone: "active",
      steps: stepsFor("draw"),
    };
  }
  if (run.status === "capturing" || run.stage_states.capture.status === "in_progress") {
    return {
      title: `Photographing pass ${number}`,
      detail: "The marks are down. The camera is recording the sheet so the advisor can see what actually happened.",
      passLabel: `Pass ${number}`,
      tone: "active",
      steps: stepsFor("photograph"),
    };
  }
  if (run.status === "pending" || run.stage_states.prepare.status === "in_progress") {
    return {
      title: `Preparing pass ${number}`,
      detail: "The drawing layer is being checked and prepared before the plotter begins moving.",
      passLabel: `Pass ${number}`,
      tone: "active",
      steps: stepsFor("draw"),
    };
  }
  if (run.status === "plotting" || run.stage_states.plot.status === "in_progress") {
    return {
      title: `Drawing pass ${number}`,
      detail: "The plotter is adding this layer to the sheet. Guidance sent now will shape the next decision.",
      passLabel: `Pass ${number}`,
      tone: "active",
      steps: stepsFor("draw"),
    };
  }
  return {
    title: `Preparing to review pass ${number}`,
    detail: "The observation is ready. The studio is handing it to the advisor for the next creative decision.",
    passLabel: `Pass ${number}`,
    tone: "active",
    steps: stepsFor("reflect"),
  };
}

export function deriveStudioProgress(
  session: DrawingSession,
  run: PlotRun | null,
): StudioProgressModel {
  const number = passNumber(session);
  const passLabel = `Pass ${number}`;

  if (session.status === "planning") {
    return {
      title: "Planning the first pass",
      detail: "The advisor is turning your idea into a safe drawing plan and preview. Nothing will move yet.",
      passLabel,
      tone: "active",
      steps: stepsFor("plan"),
    };
  }
  if (session.status === "awaiting_approval") {
    return {
      title: "Preview ready for approval",
      detail: "Review the plan and first-pass artwork. The plotter remains still until you approve.",
      passLabel,
      tone: "attention",
      steps: stepsFor("plan", "attention"),
    };
  }
  if (session.status === "awaiting_capture_review") {
    return {
      title: session.authorization.finish_requested
        ? `Register the final photo for pass ${number}`
        : `Page registration needed for pass ${number}`,
      detail: session.authorization.finish_requested
        ? "Place the four corner markers, or retake the photo. The drawing will finish after this observation is saved."
        : "Place the four corner markers on the physical sheet, or retake the photo, before the advisor continues.",
      passLabel,
      tone: "attention",
      steps: stepsFor("register", "attention"),
    };
  }
  if (session.status === "stopping") {
    const emergencyStopInProgress = run?.status === "stopping";
    return {
      title: session.authorization.finish_requested
        ? `Finishing pass ${number}`
        : emergencyStopInProgress
        ? "Stopping safely"
        : `Finishing pass ${number}, then stopping`,
      detail: session.authorization.finish_requested
        ? "The current plot and its photograph will finish safely. No additional drawing layer will begin."
        : emergencyStopInProgress
        ? "The plotter will pause after its current path segment. No photograph or later pass will begin."
        : "The current pass and its observation will finish, but the studio will not begin another layer.",
      passLabel,
      tone: "attention",
      steps: stepsFor(inferRunStep(run), "attention"),
    };
  }
  if (session.status === "paused") {
    return {
      title: "Session paused",
      detail:
        session.requested_human_action ??
        session.error ??
        "The studio is waiting for attention and will not make another physical move.",
      passLabel,
      tone: "attention",
      steps: stepsFor(inferRunStep(run), "attention"),
    };
  }
  if (session.status === "completed") {
    return {
      title: "Drawing complete",
      detail: "The studio has finished this drawing and will not add another layer.",
      passLabel: session.pass_count === 1 ? "1 pass complete" : `${session.pass_count} passes complete`,
      tone: "complete",
      steps: stepsFor("reflect", "active", true),
    };
  }
  if (session.status === "failed") {
    return {
      title: "Session stopped",
      detail: session.error ?? "The drawing could not continue safely.",
      passLabel,
      tone: "failed",
      steps: stepsFor(inferRunStep(run), "attention"),
    };
  }
  if (session.status === "abandoned") {
    return {
      title: "Session left unfinished",
      detail: "The studio will not return to this drawing or make another physical move for it.",
      passLabel: session.pass_count === 0 ? "No passes plotted" : passLabel,
      tone: "attention",
      steps: stepsFor(inferRunStep(run), "attention"),
    };
  }
  if (session.status === "observed") {
    return {
      title: `Pass ${number} is ready to review`,
      detail: "The registered observation is ready for a human-directed next step in this legacy session.",
      passLabel,
      tone: "attention",
      steps: stepsFor("reflect", "attention"),
    };
  }
  if (session.status === "proposal_ready") {
    return {
      title: "Next pass ready for approval",
      detail: "Review the proposed layer before continuing this legacy session.",
      passLabel: `Pass ${number + 1}`,
      tone: "attention",
      steps: stepsFor("plan", "attention"),
    };
  }
  return activeRunModel(session, run);
}
