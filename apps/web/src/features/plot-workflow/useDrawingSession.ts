import { useEffect, useRef, useState } from "react";

import {
  approveDrawingIteration,
  createDrawingSession,
  fetchDrawingSession,
  fetchLatestDrawingSession,
  requestDrawingAdvice,
} from "../../lib/api";
import type { DrawingSession } from "../../types/drawing";

const ACTIVE_SESSION_STATUSES = new Set(["running", "awaiting_capture_review"]);
const ACTIVE_POLL_MS = 1200;
const IDLE_POLL_MS = 3500;

type SessionAction = "create" | "advice" | "approve" | null;

export function useDrawingSession(onRunStarted: () => Promise<void>) {
  const [session, setSession] = useState<DrawingSession | null>(null);
  const [busyAction, setBusyAction] = useState<SessionAction>(null);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  async function refresh() {
    try {
      const response = session
        ? await fetchDrawingSession(session.id)
        : await fetchLatestDrawingSession();
      if (mountedRef.current) {
        setSession("session" in response ? response.session : response);
        setError(null);
      }
    } catch (refreshError) {
      if (mountedRef.current) {
        setError(
          refreshError instanceof Error
            ? refreshError.message
            : "Failed to load iterative drawing session.",
        );
      }
    }
  }

  async function runAction(
    action: Exclude<SessionAction, null>,
    callback: () => Promise<DrawingSession>,
    startsRun = false,
  ) {
    try {
      setBusyAction(action);
      setError(null);
      const updated = await callback();
      if (!mountedRef.current) return;
      setSession(updated);
      if (startsRun) {
        await onRunStarted();
      }
    } catch (actionError) {
      if (mountedRef.current) {
        setError(
          actionError instanceof Error ? actionError.message : "Drawing session action failed.",
        );
      }
    } finally {
      if (mountedRef.current) setBusyAction(null);
    }
  }

  useEffect(() => {
    mountedRef.current = true;
    void refresh();
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    const interval = window.setInterval(
      () => void refresh(),
      session && ACTIVE_SESSION_STATUSES.has(session.status) ? ACTIVE_POLL_MS : IDLE_POLL_MS,
    );
    return () => window.clearInterval(interval);
  }, [session?.id, session?.status]);

  return {
    session,
    busyAction,
    error,
    start: (intent: string, initialAssetId: string, iterationLimit: number) =>
      runAction(
        "create",
        () => createDrawingSession(intent, initialAssetId, iterationLimit),
        true,
      ),
    requestAdvice: () =>
      session
        ? runAction("advice", () => requestDrawingAdvice(session.id))
        : Promise.resolve(),
    approve: () =>
      session
        ? runAction("approve", () => approveDrawingIteration(session.id), true)
        : Promise.resolve(),
  };
}
