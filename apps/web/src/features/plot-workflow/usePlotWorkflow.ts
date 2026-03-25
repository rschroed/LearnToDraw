import { useEffect, useRef, useState } from "react";

import {
  createPatternAsset,
  createPlotRun,
  fetchPlotRun,
  fetchLatestPlotRun,
  fetchPlotRuns,
  uploadPlotAsset,
} from "../../lib/api";
import type {
  PlotAsset,
  PlotRun,
  PlotRunSummary,
} from "../../types/plotting";

type PlotAction = "upload" | "pattern" | "start" | null;
type NoticeTone = "info" | "success" | "error";
type SelectionSource = "manual" | "run-derived" | null;

const ACTIVE_RUN_STATUSES = new Set(["pending", "plotting", "capturing"]);
export const PLOT_WORKFLOW_ACTIVE_POLL_INTERVAL_MS = 1200;
export const PLOT_WORKFLOW_IDLE_POLL_INTERVAL_MS = 3500;

export function usePlotWorkflow() {
  const [selectedAsset, setSelectedAsset] = useState<PlotAsset | null>(null);
  const [selectionSource, setSelectionSource] = useState<SelectionSource>(null);
  const [latestRun, setLatestRun] = useState<PlotRun | null>(null);
  const [inspectedRun, setInspectedRun] = useState<PlotRun | null>(null);
  const [inspectedRunId, setInspectedRunId] = useState<string | null>(null);
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
  const selectionSourceRef = useRef<SelectionSource>(null);

  const activeRun = latestRun ? ACTIVE_RUN_STATUSES.has(latestRun.status) : false;

  function updateSelection(asset: PlotAsset | null, source: SelectionSource) {
    selectionSourceRef.current = source;
    setSelectionSource(source);
    setSelectedAsset(asset);
  }

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
      if (inspectedRunId !== null && latest.run?.id !== inspectedRunId) {
        const selectedRun = await fetchPlotRun(inspectedRunId);
        if (!mountedRef.current) {
          return;
        }
        setInspectedRun(selectedRun);
      } else {
        setInspectedRun(latest.run);
      }
      setRecentRuns(runs.runs);
      if (selectionSourceRef.current !== "manual") {
        updateSelection(latest.run?.asset ?? null, latest.run?.asset ? "run-derived" : null);
      }
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
      updateSelection(asset, "manual");
      setNotice({
        tone: "success",
        message: "Built-in test-grid pattern is ready to plot with automatic drawable-area preparation.",
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
      updateSelection(asset, "manual");
      setNotice({
        tone: "success",
        message: `Loaded ${asset.name} for plotting. Uploaded SVGs are prepared automatically into the current drawable area.`,
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
      setInspectedRun(run);
      setInspectedRunId(run.id);
      updateSelection(run.asset, "run-derived");
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
      activeRun
        ? PLOT_WORKFLOW_ACTIVE_POLL_INTERVAL_MS
        : PLOT_WORKFLOW_IDLE_POLL_INTERVAL_MS,
    );

    return () => {
      window.clearInterval(interval);
    };
  }, [activeRun]);

  return {
    selectedAsset,
    selectionSource,
    latestRun,
    inspectedRun,
    inspectedRunId,
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
    inspectRun: async (runId: string) => {
      setRefreshing(true);
      try {
        const run = await fetchPlotRun(runId);
        if (!mountedRef.current) {
          return;
        }
        setInspectedRun(run);
        setInspectedRunId(runId);
        setError(null);
      } catch (refreshError) {
        if (!mountedRef.current) {
          return;
        }
        setError(
          refreshError instanceof Error
            ? refreshError.message
            : "Failed to load plot run detail.",
        );
      } finally {
        if (mountedRef.current) {
          setRefreshing(false);
        }
      }
    },
  };
}
