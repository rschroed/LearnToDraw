import { useEffect, useRef, useState } from "react";
import type { MutableRefObject } from "react";

import {
  fetchHelperStatus,
  isNetworkRequestError,
  openHelperApp,
  startHelperBackend,
} from "../../lib/api";
import type { HelperStatus } from "../../types/helper";
import type { HardwareSnapshot, HelperActionName, HelperConnectionState } from "./hardwareDashboardTypes";


const HELPER_RECONNECT_WINDOW_MS = 15000;


export function useHelperBackendControl({
  mountedRef,
  clearHardwareState,
  applyHardwareSnapshot,
  fetchHardwareSnapshot,
  setError,
}: {
  mountedRef: MutableRefObject<boolean>;
  clearHardwareState: () => void;
  applyHardwareSnapshot: (snapshot: HardwareSnapshot) => void;
  fetchHardwareSnapshot: () => Promise<HardwareSnapshot>;
  setError: (message: string | null) => void;
}) {
  const [helperStatus, setHelperStatus] = useState<HelperStatus | null>(null);
  const [helperConnectionState, setHelperConnectionState] =
    useState<HelperConnectionState>("unknown");
  const [helperActionName, setHelperActionName] =
    useState<HelperActionName>(null);
  const initialAutoStartAttemptedRef = useRef(false);
  const helperReconnectUntilRef = useRef(0);
  const helperReconnectTimerRef = useRef<number | null>(null);

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

  async function runHelperAction(
    name: Exclude<HelperActionName, null>,
    action: () => Promise<HelperStatus>,
    refresh: () => Promise<void>,
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
      await refresh();
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

  function openHelper(refresh: () => Promise<void>) {
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
      void refresh();
    }, 750);
  }

  useEffect(() => {
    return () => {
      if (helperReconnectTimerRef.current !== null) {
        window.clearTimeout(helperReconnectTimerRef.current);
      }
    };
  }, []);

  return {
    helperStatus,
    helperConnectionState,
    helperActionName,
    syncHelperConnection,
    reconcileBackendUnavailable,
    openHelper,
    runHelperAction,
  };
}
