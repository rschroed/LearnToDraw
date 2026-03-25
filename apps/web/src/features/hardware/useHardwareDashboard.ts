import { useEffect, useRef, useState } from "react";

import {
  captureImage,
  createPatternAsset,
  createPlotRun,
  runPlotterTestAction,
  setCameraDevice,
  setPlotterCalibration,
  setPlotterPenHeights,
  setPlotterSafeBounds,
  setPlotterWorkspace,
  walkPlotterHome,
} from "../../lib/api";
import type { CaptureMetadata } from "../../types/hardware";
import { useHardwareActionRunner } from "./useHardwareActionRunner";
import type {
  DiagnosticPatternId,
  HardwareDashboardController,
  PlotterDiagnosticAction,
} from "./hardwareDashboardTypes";
import { useHardwareSnapshotState } from "./useHardwareSnapshotState";


export const HARDWARE_DASHBOARD_POLL_INTERVAL_MS = 2500;


export function useHardwareDashboard(): HardwareDashboardController {
  const mountedRef = useRef(true);
  const [error, setError] = useState<string | null>(null);
  const snapshotState = useHardwareSnapshotState();

  async function refresh({
    silent = false,
  }: {
    silent?: boolean;
  } = {}) {
    if (!silent) {
      snapshotState.setRefreshing(true);
    }

    try {
      const snapshot = await snapshotState.fetchHardwareSnapshot();
      if (!mountedRef.current) {
        return;
      }
      snapshotState.applyHardwareSnapshot(snapshot);
      setError(null);
    } catch (refreshError) {
      if (!mountedRef.current) {
        return;
      }
      snapshotState.clearHardwareState();
      setError(
        refreshError instanceof Error
          ? refreshError.message
          : "Failed to refresh hardware state.",
      );
    } finally {
      if (!mountedRef.current) {
        return;
      }
      snapshotState.setLoading(false);
      snapshotState.setRefreshing(false);
    }
  }

  const actionRunner = useHardwareActionRunner({
    refresh,
    setError,
  });

  useEffect(() => {
    mountedRef.current = true;
    void refresh();

    const poller = window.setInterval(() => {
      void refresh({ silent: true });
    }, HARDWARE_DASHBOARD_POLL_INTERVAL_MS);

    return () => {
      mountedRef.current = false;
      window.clearInterval(poller);
    };
  }, []);

  return {
    hardwareStatus: snapshotState.hardwareStatus,
    plotterCalibration: snapshotState.plotterCalibration,
    plotterDevice: snapshotState.plotterDevice,
    plotterWorkspace: snapshotState.plotterWorkspace,
    latestCapture: snapshotState.latestCapture,
    loading: snapshotState.loading,
    refreshing: snapshotState.refreshing,
    actionName: actionRunner.actionName,
    actionFeedback: actionRunner.actionFeedback,
    error,
    refresh,
    walkHome: () =>
      actionRunner.runAction("plotter-walk-home", walkPlotterHome, {
        pending: "Walking plotter home...",
        success: "Plotter walked home.",
      }),
    runPlotterTestAction: (action: PlotterDiagnosticAction) =>
      actionRunner.runAction(
        `plotter-test:${action}`,
        () => runPlotterTestAction(action),
        {
          pending: `Running ${action.replace("_", " ")}...`,
          success: `${action.replace("_", " ")} completed.`,
        },
      ),
    runDiagnosticPattern: async (patternId: DiagnosticPatternId) =>
      actionRunner.runAction(
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
      actionRunner.runAction(
        "plotter-pen-heights",
        () => setPlotterPenHeights(penPosUp, penPosDown),
        {
          pending: "Updating pen heights...",
          success: "Pen heights updated.",
        },
      ),
    setPlotterCalibration: (nativeResFactor: number) =>
      actionRunner.runAction(
        "plotter-calibration",
        async () => {
          const response = await setPlotterCalibration(nativeResFactor);
          if (mountedRef.current) {
            snapshotState.setPlotterCalibrationState(response.calibration);
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
      actionRunner.runAction(
        "plotter-safe-bounds",
        async () => {
          const response = await setPlotterSafeBounds(safeBounds);
          if (mountedRef.current) {
            snapshotState.setPlotterDeviceState(response.device);
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
      actionRunner.runAction(
        "plotter-workspace",
        async () => {
          const response = await setPlotterWorkspace(workspace);
          if (mountedRef.current) {
            snapshotState.setPlotterWorkspaceState(response.workspace);
          }
        },
        {
          pending: "Saving plotter workspace...",
          success: "Plotter workspace saved.",
        },
      ),
    capture: () =>
      actionRunner.runAction("camera-capture", captureImage, {
        pending: "Capturing image...",
        success: "Image captured.",
      }, {
        onSuccess: (result) => {
          const response = result as { capture?: CaptureMetadata };
          if (mountedRef.current && response.capture) {
            snapshotState.setLatestCaptureState(response.capture);
          }
        },
        ignoreRefreshErrors: true,
      }),
    setCameraDevice: (deviceId: string | null) =>
      actionRunner.runAction("camera-device", () => setCameraDevice(deviceId), {
        pending:
          deviceId === null
            ? "Clearing camera selection..."
            : "Saving camera selection...",
        success:
          deviceId === null
            ? "Camera selection cleared."
            : "Camera selection saved.",
      }),
  };
}
