import type { PlotRun, PlotStageState } from "../../types/plotting";

interface SummaryRunLike {
  status: PlotRun["status"];
  purpose: PlotRun["purpose"];
  created_at: string;
}

interface ResultCaptureLike {
  width: number;
  height: number;
  timestamp: string;
}

export interface RunStepSummaryItem {
  key: "prepare" | "plot" | "capture";
  label: string;
  tone: "ok" | "warn" | "error" | "neutral";
  note?: string | null;
}

export function getStageLabel(run: PlotRun | null) {
  if (!run) {
    return "No active run";
  }
  if (run.status === "plotting") {
    return "Plotting";
  }
  if (run.status === "capturing") {
    return "Capturing";
  }
  if (run.status === "completed") {
    return "Completed";
  }
  if (run.status === "failed") {
    return "Failed";
  }
  return "Preparing";
}


export function getRunStatusTone(status: PlotRun["status"] | "idle") {
  if (status === "completed") {
    return "ok";
  }
  if (status === "pending" || status === "plotting" || status === "capturing") {
    return "warn";
  }
  if (status === "failed") {
    return "warn";
  }
  return "ok";
}


export function formatStageState(stageState: PlotStageState) {
  if (stageState.status === "in_progress") {
    return "in progress";
  }
  return stageState.status;
}

export function formatShortTimestamp(timestamp: string) {
  const date = new Date(timestamp);
  return `${date.toLocaleDateString([], {
    month: "numeric",
    day: "numeric",
  })} · ${date.toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  })}`;
}

export function formatRunMetaStrip({
  kindLabel,
  run,
}: {
  kindLabel: string;
  run: SummaryRunLike;
}) {
  const tokens = [kindLabel];
  if (run.purpose !== "normal") {
    tokens.push(run.purpose);
  }
  tokens.push(formatShortTimestamp(run.created_at));
  return tokens.join(" · ");
}

export function getStepSummaryItems(run: PlotRun | null): RunStepSummaryItem[] {
  if (!run) {
    return [];
  }

  const items: RunStepSummaryItem[] = [];
  const prepareState = run.stage_states.prepare;
  const plotState = run.stage_states.plot;
  const captureState = run.stage_states.capture;

  items.push({
    key: "prepare",
    label:
      prepareState.status === "completed"
        ? "Prepared ✓"
        : prepareState.status === "failed"
          ? "Prepare !"
          : prepareState.status === "in_progress"
            ? "Preparing…"
            : "Prepare",
    tone:
      prepareState.status === "completed"
        ? "ok"
        : prepareState.status === "failed"
          ? "error"
          : prepareState.status === "in_progress"
            ? "warn"
            : "neutral",
    note:
      prepareState.status === "completed"
        ? null
        : prepareState.message,
  });

  items.push({
    key: "plot",
    label:
      plotState.status === "completed"
        ? "Plotted ✓"
        : plotState.status === "failed"
          ? "Plot !"
          : plotState.status === "in_progress"
            ? "Plotting…"
            : "Plot",
    tone:
      plotState.status === "completed"
        ? "ok"
        : plotState.status === "failed"
          ? "error"
          : plotState.status === "in_progress"
            ? "warn"
            : "neutral",
    note:
      plotState.status === "completed"
        ? null
        : plotState.message,
  });

  items.push({
    key: "capture",
    label:
      run.capture_mode === "skip" && captureState.status === "completed"
        ? "Skipped"
        : captureState.status === "completed"
          ? "Captured ✓"
          : captureState.status === "failed"
            ? "Capture !"
            : captureState.status === "in_progress"
              ? "Capturing…"
              : "Capture",
    tone:
      captureState.status === "completed"
        ? "ok"
        : captureState.status === "failed"
          ? "error"
          : captureState.status === "in_progress"
            ? "warn"
            : run.capture_mode === "skip"
              ? "neutral"
              : "neutral",
    note:
      captureState.status === "completed"
        ? run.capture_mode === "skip"
          ? "Capture skipped for this run."
          : null
        : captureState.message,
  });

  return items;
}

export function getStepSummaryNote(run: PlotRun | null) {
  if (!run) {
    return null;
  }
  if (run.status === "completed" && run.capture_mode !== "skip") {
    return null;
  }
  if (run.status === "completed" && run.capture_mode === "skip") {
    return "Capture skipped for this run.";
  }
  const failedStage = Object.values(run.stage_states).find((stage) => stage.status === "failed");
  if (failedStage?.message) {
    return failedStage.message;
  }
  const activeStage = Object.values(run.stage_states).find((stage) => stage.status === "in_progress");
  if (activeStage?.message) {
    return activeStage.message;
  }
  if (run.error) {
    return run.error;
  }
  return null;
}

export function formatResultMeta({
  capture,
  includeTimestamp,
}: {
  capture: ResultCaptureLike | null;
  includeTimestamp?: boolean;
}) {
  if (!capture) {
    return null;
  }
  const tokens = ["Captured", `${capture.width} × ${capture.height}`];
  if (includeTimestamp) {
    tokens.push(`Saved ${formatShortTimestamp(capture.timestamp)}`);
  }
  return tokens.join(" · ");
}


export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}


export function formatPhysicalSize(width: unknown, height: unknown) {
  if (typeof width !== "number" || typeof height !== "number") {
    return null;
  }
  return `${width.toFixed(1).replace(/\.0$/, "")} × ${height
    .toFixed(1)
    .replace(/\.0$/, "")} mm`;
}


export function getNestedRecord(
  record: Record<string, unknown> | null,
  key: string,
): Record<string, unknown> | null {
  const value = record?.[key];
  return isRecord(value) ? value : null;
}
