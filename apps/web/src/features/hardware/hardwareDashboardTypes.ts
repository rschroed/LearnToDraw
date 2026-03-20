import type { CaptureMetadata, HardwareStatus, PlotterCalibration, PlotterDeviceSettings, PlotterWorkspace } from "../../types/hardware";
import type { HelperStatus } from "../../types/helper";

export type PlotterDiagnosticAction = "raise_pen" | "lower_pen" | "cycle_pen" | "align";
export type DiagnosticPatternId = "tiny-square" | "dash-row" | "double-box";
export type ActionName =
  | "plotter-walk-home"
  | "plotter-calibration"
  | "plotter-safe-bounds"
  | "plotter-workspace"
  | "plotter-pen-heights"
  | "camera-capture"
  | `plotter-test:${PlotterDiagnosticAction}`
  | `plotter-pattern:${DiagnosticPatternId}`
  | null;
export type ActionTone = "info" | "success" | "error";
export type HelperActionName = "start" | "restart" | null;
export type HelperConnectionState = "unknown" | "reachable" | "missing";

export interface ActionFeedback {
  action: Exclude<ActionName, null>;
  message: string;
  tone: ActionTone;
}

export interface HardwareSnapshot {
  status: HardwareStatus;
  calibration: PlotterCalibration;
  device: PlotterDeviceSettings;
  workspace: PlotterWorkspace;
  latest: { capture: CaptureMetadata | null };
}

export interface HardwareDashboardState {
  hardwareStatus: HardwareStatus | null;
  plotterCalibration: PlotterCalibration | null;
  plotterDevice: PlotterDeviceSettings | null;
  plotterWorkspace: PlotterWorkspace | null;
  latestCapture: CaptureMetadata | null;
  loading: boolean;
  refreshing: boolean;
  actionName: ActionName;
  actionFeedback: ActionFeedback | null;
  error: string | null;
  helperStatus: HelperStatus | null;
  helperConnectionState: HelperConnectionState;
  helperActionName: HelperActionName;
}
