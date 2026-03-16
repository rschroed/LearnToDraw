import { useEffect, useRef, useState } from "react";

import {
  captureImage,
  createPatternAsset,
  createPlotRun,
  fetchHardwareStatus,
  fetchLatestCapture,
  returnPlotterToOrigin,
  setPlotterPenHeights,
  runPlotterTestAction,
} from "../../lib/api";
import type { CaptureMetadata, HardwareStatus } from "../../types/hardware";

const POLL_INTERVAL_MS = 2500;

type PlotterDiagnosticAction = "raise_pen" | "lower_pen" | "cycle_pen" | "align";
type DiagnosticPatternId = "tiny-square" | "dash-row" | "double-box";
type ActionName =
  | "plotter-return"
  | "plotter-pen-heights"
  | "camera-capture"
  | `plotter-test:${PlotterDiagnosticAction}`
  | `plotter-pattern:${DiagnosticPatternId}`
  | null;
type ActionTone = "info" | "success" | "error";

export function useHardwareDashboard() {
  const [hardwareStatus, setHardwareStatus] = useState<HardwareStatus | null>(null);
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
      const [status, latest] = await Promise.all([
        fetchHardwareStatus(),
        fetchLatestCapture(),
      ]);
      if (!mountedRef.current) {
        return;
      }
      setHardwareStatus(status);
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
    latestCapture,
    loading,
    refreshing,
    actionName,
    actionFeedback,
    error,
    refresh,
    returnToOrigin: () =>
      runAction("plotter-return", returnPlotterToOrigin, {
        pending: "Returning plotter to origin...",
        success: "Plotter returned to origin.",
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
    capture: () =>
      runAction("camera-capture", captureImage, {
        pending: "Capturing image...",
        success: "Image captured.",
      }),
  };
}
