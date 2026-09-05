import { useEffect, useRef, useState } from "react";

import {
  approveDrawingSession,
  confirmPlotRunCaptureReview,
  fetchDrawingSession,
  fetchHardwareStatus,
  fetchPlotterWorkspace,
  fetchPlotRun,
  fetchPlotRunCaptureReview,
  heartbeatDrawingSession,
  resumeDrawingSession,
  retryPlotRunCapture,
  sendDrawingSessionMessage,
  stopDrawingSession,
} from "../../lib/api";
import type { DrawingSession } from "../../types/drawing";
import type {
  HardwareStatus,
  NormalizationCorners,
  PlotterWorkspace,
} from "../../types/hardware";
import type { PlotRun, PlotRunCaptureReviewPayload } from "../../types/plotting";

const ACTIVE_SESSION_STATUSES = new Set([
  "planning",
  "running",
  "awaiting_capture_review",
  "stopping",
]);
const HEARTBEAT_SESSION_STATUSES = new Set([
  "running",
  "awaiting_capture_review",
  "stopping",
]);

export const STUDIO_ACTIVE_POLL_MS = 1000;
export const STUDIO_IDLE_POLL_MS = 3500;
export const STUDIO_HEARTBEAT_MS = 10000;

export type StudioAction =
  | "message"
  | "approve"
  | "stop-after-pass"
  | "emergency-stop"
  | "resume"
  | "retry-capture"
  | "register"
  | null;

export function useStudioSession(sessionId: string) {
  const [session, setSession] = useState<DrawingSession | null>(null);
  const [runs, setRuns] = useState<Record<string, PlotRun>>({});
  const [captureReview, setCaptureReview] = useState<PlotRunCaptureReviewPayload | null>(null);
  const [hardwareStatus, setHardwareStatus] = useState<HardwareStatus | null>(null);
  const [plotterWorkspace, setPlotterWorkspace] = useState<PlotterWorkspace | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyAction, setBusyAction] = useState<StudioAction>(null);
  const [error, setError] = useState<string | null>(null);
  const [hardwareError, setHardwareError] = useState<string | null>(null);
  const mountedRef = useRef(true);
  const refreshRunningRef = useRef(false);

  async function refresh({ silent = false }: { silent?: boolean } = {}) {
    if (refreshRunningRef.current) {
      return;
    }
    refreshRunningRef.current = true;
    try {
      const nextSession = await fetchDrawingSession(sessionId);
      const runIds = Array.from(
        new Set([
          ...nextSession.iterations.map((iteration) => iteration.run_id),
          ...(nextSession.current_run_id ? [nextSession.current_run_id] : []),
        ]),
      );
      const runEntries = await Promise.all(
        runIds.map(async (runId) => [runId, await fetchPlotRun(runId)] as const),
      );
      const nextRuns = Object.fromEntries(runEntries);
      const currentRun = nextSession.current_run_id
        ? nextRuns[nextSession.current_run_id] ?? null
        : null;
      const nextReview =
        currentRun?.status === "awaiting_capture_review"
          ? await fetchPlotRunCaptureReview(currentRun.id)
          : null;

      if (mountedRef.current) {
        setSession(nextSession);
        setRuns(nextRuns);
        setCaptureReview(nextReview);
        setError(null);
      }
    } catch (refreshError) {
      if (mountedRef.current && !silent) {
        setError(
          refreshError instanceof Error ? refreshError.message : "Unable to load this drawing.",
        );
      }
    } finally {
      refreshRunningRef.current = false;
      if (mountedRef.current) {
        setLoading(false);
      }
    }

    try {
      const status = await fetchHardwareStatus();
      if (mountedRef.current) {
        setHardwareStatus(status);
        setHardwareError(null);
      }
    } catch (statusError) {
      if (mountedRef.current) {
        setHardwareStatus(null);
        setHardwareError(
          statusError instanceof Error ? statusError.message : "Hardware status is unavailable.",
        );
      }
    }

    try {
      const workspace = await fetchPlotterWorkspace();
      if (mountedRef.current) setPlotterWorkspace(workspace);
    } catch {
      if (mountedRef.current) setPlotterWorkspace(null);
    }
  }

  async function runAction(
    action: Exclude<StudioAction, null>,
    callback: () => Promise<DrawingSession | PlotRun | { run: PlotRun }>,
  ) {
    try {
      setBusyAction(action);
      setError(null);
      const result = await callback();
      if (!mountedRef.current) return;
      if ("session_version" in result) {
        setSession(result);
      } else if ("run" in result) {
        setRuns((current) => ({ ...current, [result.run.id]: result.run }));
      } else {
        setRuns((current) => ({ ...current, [result.id]: result }));
      }
      await refresh({ silent: true });
    } catch (actionError) {
      if (mountedRef.current) {
        setError(
          actionError instanceof Error ? actionError.message : "The studio action failed.",
        );
      }
    } finally {
      if (mountedRef.current) {
        setBusyAction(null);
      }
    }
  }

  useEffect(() => {
    mountedRef.current = true;
    setLoading(true);
    void refresh();
    return () => {
      mountedRef.current = false;
    };
  }, [sessionId]);

  useEffect(() => {
    const pollMs =
      session && ACTIVE_SESSION_STATUSES.has(session.status)
        ? STUDIO_ACTIVE_POLL_MS
        : STUDIO_IDLE_POLL_MS;
    const poller = window.setInterval(() => void refresh({ silent: true }), pollMs);
    return () => window.clearInterval(poller);
  }, [session?.id, session?.status]);

  useEffect(() => {
    const shouldHeartbeat = Boolean(
      session?.session_version === 2 &&
        session.authorization.approved_at &&
        HEARTBEAT_SESSION_STATUSES.has(session.status),
    );
    if (!shouldHeartbeat || !session) {
      return undefined;
    }

    const sendHeartbeat = async () => {
      if (document.visibilityState === "hidden") return;
      try {
        const updated = await heartbeatDrawingSession(session.id);
        if (mountedRef.current) {
          setSession(updated);
          setHardwareError(null);
        }
      } catch (heartbeatError) {
        if (mountedRef.current) {
          setHardwareError(
            heartbeatError instanceof Error
              ? `Attendance signal lost: ${heartbeatError.message}`
              : "Attendance signal lost.",
          );
        }
      }
    };

    void sendHeartbeat();
    const heartbeat = window.setInterval(() => void sendHeartbeat(), STUDIO_HEARTBEAT_MS);
    const handleVisibility = () => {
      if (document.visibilityState === "visible") void sendHeartbeat();
    };
    document.addEventListener("visibilitychange", handleVisibility);
    window.addEventListener("focus", handleVisibility);
    return () => {
      window.clearInterval(heartbeat);
      document.removeEventListener("visibilitychange", handleVisibility);
      window.removeEventListener("focus", handleVisibility);
    };
  }, [session?.id, session?.status, session?.authorization.approved_at]);

  return {
    session,
    runs,
    captureReview,
    hardwareStatus,
    plotterWorkspace,
    hardwareError,
    loading,
    busyAction,
    error,
    refresh,
    sendMessage: (text: string) =>
      runAction("message", () => sendDrawingSessionMessage(sessionId, text)),
    approve: () => runAction("approve", () => approveDrawingSession(sessionId)),
    stopAfterPass: () =>
      runAction("stop-after-pass", () => stopDrawingSession(sessionId, "after_pass")),
    emergencyStop: () =>
      runAction("emergency-stop", () => stopDrawingSession(sessionId, "emergency")),
    resume: () => runAction("resume", () => resumeDrawingSession(sessionId)),
    retryCapture: (runId: string) =>
      runAction("retry-capture", () => retryPlotRunCapture(runId)),
    confirmRegistration: (runId: string, corners: NormalizationCorners) =>
      runAction("register", () => confirmPlotRunCaptureReview(runId, corners)),
  };
}
