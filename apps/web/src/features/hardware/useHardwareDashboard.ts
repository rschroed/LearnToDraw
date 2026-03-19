import { useEffect, useRef, useState } from "react";

import {
  captureImage,
  createPatternAsset,
  createPlotRun,
  fetchHardwareStatus,
  fetchHelperStatus,
  fetchLatestCapture,
  fetchPlotterCalibration,
  fetchPlotterDevice,
  setPlotterSafeBounds,
  fetchPlotterWorkspace,
  isNetworkRequestError,
  openHelperApp,
  restartHelperBackend,
  startHelperBackend,
  walkPlotterHome,
  runPlotterTestAction,
  setPlotterCalibration,
  setPlotterPenHeights,
  setPlotterWorkspace,
} from "../../lib/api";
import type { HelperStatus } from "../../types/helper";
import type {
  CaptureMetadata,
  HardwareStatus,
  PlotterCalibration,
  PlotterDeviceSettings,
  PlotterWorkspace,
} from "../../types/hardware";

const POLL_INTERVAL_MS = 2500;
const HELPER_RECONNECT_WINDOW_MS = 15000;

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
type HelperActionName = "start" | "restart" | null;
type HelperConnectionState = "unknown" | "reachable" | "missing";

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
  const [helperStatus, setHelperStatus] = useState<HelperStatus | null>(null);
  const [helperConnectionState, setHelperConnectionState] =
    useState<HelperConnectionState>("unknown");
  const [helperActionName, setHelperActionName] =
    useState<HelperActionName>(null);
  const mountedRef = useRef(true);
  const initialAutoStartAttemptedRef = useRef(false);
  const helperReconnectUntilRef = useRef(0);
  const helperReconnectTimerRef = useRef<number | null>(null);

  function clearHardwareState() {
    setHardwareStatus(null);
    setPlotterCalibrationState(null);
    setPlotterDeviceState(null);
    setPlotterWorkspaceState(null);
    setLatestCapture(null);
  }

  function applyHardwareSnapshot(snapshot: {
    status: HardwareStatus;
    calibration: PlotterCalibration;
    device: PlotterDeviceSettings;
    workspace: PlotterWorkspace;
    latest: { capture: CaptureMetadata | null };
  }) {
    setHardwareStatus(snapshot.status);
    setPlotterCalibrationState(snapshot.calibration);
    setPlotterDeviceState(snapshot.device);
    setPlotterWorkspaceState(snapshot.workspace);
    setLatestCapture(snapshot.latest.capture);
    setError(null);
    setHelperStatus(null);
  }

  async function syncHelperConnection() {
    try {
      const nextHelperStatus = await fetchHelperStatus();
      if (!mountedRef.current) {
        return;
      }
      setHelperConnectionState("reachable");
      setHelperStatus(nextHelperStatus);
    } catch (helperError) {
      if (!mountedRef.current) {
        return;
      }
      if (isNetworkRequestError(helperError)) {
        setHelperConnectionState("missing");
        setHelperStatus(null);
        return;
      }
      setHelperConnectionState("unknown");
    }
  }

  async function fetchHardwareSnapshot() {
    const [status, calibration, device, workspace, latest] = await Promise.all([
      fetchHardwareStatus(),
      fetchPlotterCalibration(),
      fetchPlotterDevice(),
      fetchPlotterWorkspace(),
      fetchLatestCapture(),
    ]);
    return { status, calibration, device, workspace, latest };
  }

  async function reconcileBackendUnavailable({
    allowInitialAutoStart,
  }: {
    allowInitialAutoStart: boolean;
  }) {
    clearHardwareState();
    const allowReconnectAutoStart = Date.now() < helperReconnectUntilRef.current;
    try {
      const nextHelperStatus = await fetchHelperStatus();
      if (!mountedRef.current) {
        return;
      }
      setHelperConnectionState("reachable");
      setHelperStatus(nextHelperStatus);
      setError(null);

      if (
        (
          (allowInitialAutoStart && !initialAutoStartAttemptedRef.current) ||
          allowReconnectAutoStart
        ) &&
        nextHelperStatus.state === "stopped"
      ) {
        if (allowInitialAutoStart) {
          initialAutoStartAttemptedRef.current = true;
        }
        helperReconnectUntilRef.current = 0;
        const startedHelperStatus = await startHelperBackend();
        if (!mountedRef.current) {
          return;
        }
        setHelperStatus(startedHelperStatus);
        setHelperConnectionState("reachable");
        return;
      }

      if (
        nextHelperStatus.state === "running" &&
        nextHelperStatus.backend_health === "healthy"
      ) {
        helperReconnectUntilRef.current = 0;
        try {
          const snapshot = await fetchHardwareSnapshot();
          if (!mountedRef.current) {
            return;
          }
          applyHardwareSnapshot(snapshot);
          return;
        } catch (retryError) {
          if (!mountedRef.current) {
            return;
          }
          if (!isNetworkRequestError(retryError)) {
            setError(
              retryError instanceof Error
                ? retryError.message
                : "Failed to refresh hardware state.",
            );
          }
        }
      }
    } catch (helperError) {
      if (!mountedRef.current) {
        return;
      }
      if (isNetworkRequestError(helperError)) {
        setHelperConnectionState("missing");
        setHelperStatus(null);
        setError(null);
        return;
      }
      setError(
        helperError instanceof Error
          ? helperError.message
          : "Failed to refresh helper state.",
      );
    }
  }

  async function refresh({
    silent = false,
    allowInitialAutoStart = false,
  }: {
    silent?: boolean;
    allowInitialAutoStart?: boolean;
  } = {}) {
    if (!silent) {
      setRefreshing(true);
    }

    try {
      const snapshot = await fetchHardwareSnapshot();
      if (!mountedRef.current) {
        return;
      }
      applyHardwareSnapshot(snapshot);
      void syncHelperConnection();
    } catch (refreshError) {
      if (!mountedRef.current) {
        return;
      }
      if (isNetworkRequestError(refreshError)) {
        await reconcileBackendUnavailable({ allowInitialAutoStart });
      } else {
        clearHardwareState();
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

  async function runHelperAction(
    name: Exclude<HelperActionName, null>,
    action: () => Promise<HelperStatus>,
  ) {
    try {
      setHelperActionName(name);
      setError(null);
      clearHardwareState();
      const nextHelperStatus = await action();
      if (!mountedRef.current) {
        return;
      }
      setHelperConnectionState("reachable");
      setHelperStatus(nextHelperStatus);
      await refresh({ silent: true });
    } catch (helperError) {
      if (!mountedRef.current) {
        return;
      }
      clearHardwareState();
      if (isNetworkRequestError(helperError)) {
        setHelperConnectionState("missing");
        setHelperStatus(null);
        return;
      }
      setError(
        helperError instanceof Error
          ? helperError.message
          : "Failed to control the local helper.",
      );
    } finally {
      if (!mountedRef.current) {
        return;
      }
      setHelperActionName(null);
    }
  }

  function openHelper() {
    helperReconnectUntilRef.current = Date.now() + HELPER_RECONNECT_WINDOW_MS;
    setError(null);
    openHelperApp();

    if (helperReconnectTimerRef.current !== null) {
      window.clearTimeout(helperReconnectTimerRef.current);
    }

    helperReconnectTimerRef.current = window.setTimeout(() => {
      if (!mountedRef.current) {
        return;
      }
      void refresh({ silent: true });
    }, 750);
  }

  useEffect(() => {
    mountedRef.current = true;
    void refresh({ allowInitialAutoStart: true });

    const poller = window.setInterval(() => {
      void refresh({ silent: true });
    }, POLL_INTERVAL_MS);

    return () => {
      mountedRef.current = false;
      if (helperReconnectTimerRef.current !== null) {
        window.clearTimeout(helperReconnectTimerRef.current);
      }
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
    helperStatus,
    helperConnectionState,
    helperActionName,
    refresh,
    openHelper,
    startBackend: () => runHelperAction("start", startHelperBackend),
    restartBackend: () => runHelperAction("restart", restartHelperBackend),
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
