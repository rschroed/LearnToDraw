import { useEffect, useRef, useState } from "react";

import {
  createPatternAsset,
  createPlotRun,
  fetchLatestPlotRun,
  fetchPlotRuns,
  uploadPlotAsset,
} from "../../lib/api";
import type { PlotAsset, PlotRun, PlotRunSummary } from "../../types/plotting";

type PlotAction = "upload" | "pattern" | "start" | null;
type NoticeTone = "info" | "success" | "error";

const ACTIVE_RUN_STATUSES = new Set(["pending", "plotting", "capturing"]);

export function usePlotWorkflow() {
  const [selectedAsset, setSelectedAsset] = useState<PlotAsset | null>(null);
  const [latestRun, setLatestRun] = useState<PlotRun | null>(null);
  const [recentRuns, setRecentRuns] = useState<PlotRunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [busyAction, setBusyAction] = useState<PlotAction>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<{
    tone: NoticeTone;
    message: string;
  } | null>(null);
  const mountedRef = useRef(true);

  const activeRun = latestRun ? ACTIVE_RUN_STATUSES.has(latestRun.status) : false;

  async function refresh({ silent = false }: { silent?: boolean } = {}) {
    if (!silent) {
      setRefreshing(true);
    }

    try {
      const [latest, runs] = await Promise.all([fetchLatestPlotRun(), fetchPlotRuns()]);
      if (!mountedRef.current) {
        return;
      }
      setLatestRun(latest.run);
      setRecentRuns(runs.runs);
      setSelectedAsset((currentAsset) => currentAsset ?? latest.run?.asset ?? null);
      setError(null);
    } catch (refreshError) {
      if (!mountedRef.current) {
        return;
      }
      setError(
        refreshError instanceof Error
          ? refreshError.message
          : "Failed to refresh plot workflow.",
      );
    } finally {
      if (!mountedRef.current) {
        return;
      }
      setLoading(false);
      setRefreshing(false);
    }
  }

  async function createBuiltInPattern() {
    try {
      setBusyAction("pattern");
      setError(null);
      const asset = await createPatternAsset("test-grid");
      if (!mountedRef.current) {
        return;
      }
      setSelectedAsset(asset);
      setNotice({
        tone: "success",
        message: "Built-in test-grid pattern is ready to plot.",
      });
    } catch (actionError) {
      if (!mountedRef.current) {
        return;
      }
      const message =
        actionError instanceof Error ? actionError.message : "Failed to create pattern.";
      setError(message);
      setNotice({ tone: "error", message });
    } finally {
      if (mountedRef.current) {
        setBusyAction(null);
      }
    }
  }

  async function uploadSvg(file: File) {
    try {
      setBusyAction("upload");
      setError(null);
      const asset = await uploadPlotAsset(file);
      if (!mountedRef.current) {
        return;
      }
      setSelectedAsset(asset);
      setNotice({
        tone: "success",
        message: `Loaded ${asset.name} for plotting.`,
      });
    } catch (actionError) {
      if (!mountedRef.current) {
        return;
      }
      const message =
        actionError instanceof Error ? actionError.message : "Failed to upload SVG.";
      setError(message);
      setNotice({ tone: "error", message });
    } finally {
      if (mountedRef.current) {
        setBusyAction(null);
      }
    }
  }

  async function startRun() {
    if (!selectedAsset) {
      return;
    }
    try {
      setBusyAction("start");
      setError(null);
      setNotice({ tone: "info", message: "Starting plot run..." });
      const run = await createPlotRun(selectedAsset.id);
      if (!mountedRef.current) {
        return;
      }
      setLatestRun(run);
      await refresh({ silent: true });
      setNotice({ tone: "success", message: "Plot run started." });
    } catch (actionError) {
      if (!mountedRef.current) {
        return;
      }
      const message =
        actionError instanceof Error ? actionError.message : "Failed to start plot run.";
      setError(message);
      setNotice({ tone: "error", message });
    } finally {
      if (mountedRef.current) {
        setBusyAction(null);
      }
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
      () => {
        void refresh({ silent: true });
      },
      activeRun ? 1200 : 3500,
    );

    return () => {
      window.clearInterval(interval);
    };
  }, [activeRun]);

  return {
    selectedAsset,
    latestRun,
    recentRuns,
    loading,
    refreshing,
    busyAction,
    activeRun,
    error,
    notice,
    refresh,
    createBuiltInPattern,
    uploadSvg,
    startRun,
  };
}
