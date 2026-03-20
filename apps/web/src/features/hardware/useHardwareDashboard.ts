import { useEffect, useRef, useState } from "react";

import {
  captureImage,
  createPatternAsset,
  createPlotRun,
  isNetworkRequestError,
  restartHelperBackend,
  runPlotterTestAction,
  setPlotterCalibration,
  setPlotterPenHeights,
  setPlotterSafeBounds,
  setPlotterWorkspace,
  startHelperBackend,
  walkPlotterHome,
} from "../../lib/api";
import { useHardwareActionRunner } from "./useHardwareActionRunner";
import type {
  DiagnosticPatternId,
  PlotterDiagnosticAction,
} from "./hardwareDashboardTypes";
import { useHardwareSnapshotState } from "./useHardwareSnapshotState";
import { useHelperBackendControl } from "./useHelperBackendControl";


const POLL_INTERVAL_MS = 2500;


export function useHardwareDashboard() {
  const mountedRef = useRef(true);
  const [error, setError] = useState<string | null>(null);
  const snapshotState = useHardwareSnapshotState();
  const helperControl = useHelperBackendControl({
    mountedRef,
    clearHardwareState: snapshotState.clearHardwareState,
    applyHardwareSnapshot: snapshotState.applyHardwareSnapshot,
    fetchHardwareSnapshot: snapshotState.fetchHardwareSnapshot,
    setError,
  });

  async function refresh({
    silent = false,
    allowInitialAutoStart = false,
  }: {
    silent?: boolean;
    allowInitialAutoStart?: boolean;
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
      void helperControl.syncHelperConnection();
    } catch (refreshError) {
      if (!mountedRef.current) {
        return;
      }
      if (isNetworkRequestError(refreshError)) {
        await helperControl.reconcileBackendUnavailable({ allowInitialAutoStart });
      } else {
        snapshotState.clearHardwareState();
        setError(
          refreshError instanceof Error
            ? refreshError.message
            : "Failed to refresh hardware state.",
        );
      }
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
    void refresh({ allowInitialAutoStart: true });

    const poller = window.setInterval(() => {
      void refresh({ silent: true });
    }, POLL_INTERVAL_MS);

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
    helperStatus: helperControl.helperStatus,
    helperConnectionState: helperControl.helperConnectionState,
    helperActionName: helperControl.helperActionName,
    refresh,
    openHelper: () => helperControl.openHelper(() => refresh({ silent: true })),
    startBackend: () =>
      helperControl.runHelperAction(
        "start",
        startHelperBackend,
        () => refresh({ silent: true }),
      ),
    restartBackend: () =>
      helperControl.runHelperAction(
        "restart",
        restartHelperBackend,
        () => refresh({ silent: true }),
      ),
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
      }),
  };
}
