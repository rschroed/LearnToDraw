import type { PlotRun, PlotStageState } from "../../types/plotting";


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
