import { useEffect, useRef, useState } from "react";

import {
  captureImage,
  createPatternAsset,
  createPlotRun,
  fetchHardwareStatus,
  fetchLatestCapture,
  fetchPlotterCalibration,
  fetchPlotterDevice,
  setPlotterSafeBounds,
  fetchPlotterWorkspace,
  walkPlotterHome,
  runPlotterTestAction,
  setPlotterCalibration,
  setPlotterPenHeights,
  setPlotterWorkspace,
} from "../../lib/api";
import type {
  CaptureMetadata,
  HardwareStatus,
  PlotterCalibration,
  PlotterDeviceSettings,
  PlotterWorkspace,
} from "../../types/hardware";

const POLL_INTERVAL_MS = 2500;

type PlotterDiagnosticAction = "raise_pen" | "lower_pen" | "cycle_pen" | "align";
type DiagnosticPatternId = "tiny-square" | "dash-row" | "double-box";
type ActionName =
  | "plotter-walk-home"
  | "plotter-calibration"
  | "plotter-safe-bounds"
  | "plotter-workspace"
  | "plotter-pen-heights"
  | "camera-capture"
  | `plotter-test:${PlotterDiagnosticAction}`
  | `plotter-pattern:${DiagnosticPatternId}`
  | null;
type ActionTone = "info" | "success" | "error";

export function useHardwareDashboard() {
  const [hardwareStatus, setHardwareStatus] = useState<HardwareStatus | null>(null);
  const [plotterCalibration, setPlotterCalibrationState] =
    useState<PlotterCalibration | null>(null);
  const [plotterDevice, setPlotterDeviceState] =
    useState<PlotterDeviceSettings | null>(null);
  const [plotterWorkspace, setPlotterWorkspaceState] =
    useState<PlotterWorkspace | null>(null);
  const [latestCapture, setLatestCapture] = useState<CaptureMetadata | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [actionName, setActionName] = useState<ActionName>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionFeedback, setActionFeedback] = useState<{
    action: Exclude<ActionName, null>;
    message: string;
    tone: ActionTone;
  } | null>(null);
  const mountedRef = useRef(true);

  async function refresh({ silent = false }: { silent?: boolean } = {}) {
    if (!silent) {
      setRefreshing(true);
    }

    try {
      const [status, calibration, device, workspace, latest] = await Promise.all([
        fetchHardwareStatus(),
        fetchPlotterCalibration(),
        fetchPlotterDevice(),
        fetchPlotterWorkspace(),
        fetchLatestCapture(),
      ]);
      if (!mountedRef.current) {
        return;
      }
      setHardwareStatus(status);
      setPlotterCalibrationState(calibration);
      setPlotterDeviceState(device);
      setPlotterWorkspaceState(workspace);
      setLatestCapture(latest.capture);
      setError(null);
    } catch (refreshError) {
      if (!mountedRef.current) {
        return;
      }
      setError(
        refreshError instanceof Error
          ? refreshError.message
          : "Failed to refresh hardware state.",
      );
    } finally {
      if (!mountedRef.current) {
        return;
      }
      setLoading(false);
      setRefreshing(false);
    }
  }

  async function runAction(
    name: Exclude<ActionName, null>,
    action: () => Promise<unknown>,
    messages: {
      pending: string;
      success: string;
    },
  ) {
    try {
      setActionName(name);
      setError(null);
      setActionFeedback({
        action: name,
        message: messages.pending,
        tone: "info",
      });
      await action();
      await refresh({ silent: true });
      setActionFeedback({
        action: name,
        message: messages.success,
        tone: "success",
      });
    } catch (actionError) {
      const message =
        actionError instanceof Error ? actionError.message : "Action failed.";
      setError(message);
      setActionFeedback({
        action: name,
        message,
        tone: "error",
      });
    } finally {
      setActionName(null);
    }
  }

  useEffect(() => {
    mountedRef.current = true;
    void refresh();

    const poller = window.setInterval(() => {
      void refresh({ silent: true });
    }, POLL_INTERVAL_MS);

    return () => {
      mountedRef.current = false;
      window.clearInterval(poller);
    };
  }, []);

  return {
    hardwareStatus,
    plotterCalibration,
    plotterDevice,
    plotterWorkspace,
    latestCapture,
    loading,
    refreshing,
    actionName,
    actionFeedback,
    error,
    refresh,
    walkHome: () =>
      runAction("plotter-walk-home", walkPlotterHome, {
        pending: "Walking plotter home...",
        success: "Plotter walked home.",
      }),
    runPlotterTestAction: (action: PlotterDiagnosticAction) =>
      runAction(`plotter-test:${action}`, () => runPlotterTestAction(action), {
        pending: `Running ${action.replace("_", " ")}...`,
        success: `${action.replace("_", " ")} completed.`,
      }),
    runDiagnosticPattern: async (patternId: DiagnosticPatternId) =>
      runAction(
        `plotter-pattern:${patternId}`,
        async () => {
          const asset = await createPatternAsset(patternId);
          await createPlotRun(asset.id, {
            purpose: "diagnostic",
            capture_mode: "skip",
          });
        },
        {
          pending: `Starting ${patternId} diagnostic run...`,
          success: `${patternId} diagnostic run started.`,
        },
      ),
    setPlotterPenHeights: (penPosUp: number, penPosDown: number) =>
      runAction(
        "plotter-pen-heights",
        () => setPlotterPenHeights(penPosUp, penPosDown),
        {
          pending: "Updating pen heights...",
          success: "Pen heights updated.",
        },
      ),
    setPlotterCalibration: (nativeResFactor: number) =>
      runAction(
        "plotter-calibration",
        async () => {
          const response = await setPlotterCalibration(nativeResFactor);
          if (mountedRef.current) {
            setPlotterCalibrationState(response.calibration);
          }
        },
        {
          pending: "Saving plotter calibration...",
          success: "Plotter calibration saved.",
        },
      ),
    setPlotterSafeBounds: (safeBounds: {
      width_mm: number | null;
      height_mm: number | null;
    }) =>
      runAction(
        "plotter-safe-bounds",
        async () => {
          const response = await setPlotterSafeBounds(safeBounds);
          if (mountedRef.current) {
            setPlotterDeviceState(response.device);
          }
        },
        {
          pending:
            safeBounds.width_mm === null
              ? "Resetting operational safe bounds..."
              : "Saving operational safe bounds...",
          success:
            safeBounds.width_mm === null
              ? "Operational safe bounds reset."
              : "Operational safe bounds updated.",
        },
      ),
    setPlotterWorkspace: (workspace: {
      page_width_mm: number;
      page_height_mm: number;
      margin_left_mm: number;
      margin_top_mm: number;
      margin_right_mm: number;
      margin_bottom_mm: number;
    }) =>
      runAction(
        "plotter-workspace",
        async () => {
          const response = await setPlotterWorkspace(workspace);
          if (mountedRef.current) {
            setPlotterWorkspaceState(response.workspace);
          }
        },
        {
          pending: "Saving plotter workspace...",
          success: "Plotter workspace saved.",
        },
      ),
    capture: () =>
      runAction("camera-capture", captureImage, {
        pending: "Capturing image...",
        success: "Image captured.",
      }),
  };
}
