import { useEffect, useRef, useState } from "react";

import {
  acceptPlotRunCaptureReview,
  adjustPlotRunCaptureReview,
  createPatternAsset,
  createPlotRun,
  fetchPlotRun,
  fetchPlotRunCaptureReview,
  fetchLatestPlotRun,
  fetchPlotRuns,
  reuseLastPlotRunCaptureReview,
  uploadPlotAsset,
} from "../../lib/api";
import type {
  PlotAsset,
  PlotRun,
  PlotRunCaptureReviewPayload,
  PlotRunSummary,
} from "../../types/plotting";

type PlotAction = "upload" | "pattern" | "start" | "review" | null;
type NoticeTone = "info" | "success" | "error";
type SelectionSource = "manual" | "run-derived" | null;

const ACTIVE_RUN_STATUSES = new Set(["pending", "plotting", "capturing", "awaiting_capture_review"]);
export const PLOT_WORKFLOW_ACTIVE_POLL_INTERVAL_MS = 1200;
export const PLOT_WORKFLOW_IDLE_POLL_INTERVAL_MS = 3500;

export interface PlotWorkflowController {
  selectedAsset: PlotAsset | null;
  selectionSource: SelectionSource;
  latestRun: PlotRun | null;
  inspectedRun: PlotRun | null;
  inspectedRunId: string | null;
  recentRuns: PlotRunSummary[];
  pendingCaptureReview: PlotRunCaptureReviewPayload | null;
  loading: boolean;
  refreshing: boolean;
  busyAction: PlotAction;
  activeRun: boolean;
  error: string | null;
  notice: {
    tone: NoticeTone;
    message: string;
  } | null;
  refresh: (options?: { silent?: boolean }) => Promise<void>;
  createBuiltInPattern: () => Promise<void>;
  uploadSvg: (file: File) => Promise<void>;
  startRun: () => Promise<void>;
  inspectRun: (runId: string) => Promise<void>;
  acceptCaptureReview: (runId: string) => Promise<void>;
  adjustCaptureReview: (
    runId: string,
    corners: NonNullable<PlotRunCaptureReviewPayload["review"]>["proposed_corners"],
  ) => Promise<void>;
  reuseLastCaptureReview: (runId: string) => Promise<void>;
}

export function usePlotWorkflow(): PlotWorkflowController {
  const [selectedAsset, setSelectedAsset] = useState<PlotAsset | null>(null);
  const [selectionSource, setSelectionSource] = useState<SelectionSource>(null);
  const [latestRun, setLatestRun] = useState<PlotRun | null>(null);
  const [inspectedRun, setInspectedRun] = useState<PlotRun | null>(null);
  const [inspectedRunId, setInspectedRunId] = useState<string | null>(null);
  const [recentRuns, setRecentRuns] = useState<PlotRunSummary[]>([]);
  const [pendingCaptureReview, setPendingCaptureReview] = useState<PlotRunCaptureReviewPayload | null>(null);
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
      const effectiveInspectedRunId = inspectedRunId ?? latest.run?.id ?? null;
      if (effectiveInspectedRunId !== null && latest.run?.id !== effectiveInspectedRunId) {
        const selectedRun = await fetchPlotRun(effectiveInspectedRunId);
        if (!mountedRef.current) {
          return;
        }
        setInspectedRun(selectedRun);
      } else {
        setInspectedRun(latest.run);
      }
      const reviewTargetId = effectiveInspectedRunId;
      if (
        reviewTargetId !== null &&
        ((reviewTargetId === latest.run?.id && latest.run?.status === "awaiting_capture_review") ||
          (reviewTargetId !== latest.run?.id &&
            (await fetchPlotRun(reviewTargetId)).status === "awaiting_capture_review"))
      ) {
        const reviewPayload = await fetchPlotRunCaptureReview(reviewTargetId);
        if (!mountedRef.current) {
          return;
        }
        setPendingCaptureReview(reviewPayload);
      } else {
        setPendingCaptureReview(null);
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
      setPendingCaptureReview(null);
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
    pendingCaptureReview,
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
        setPendingCaptureReview(
          run.status === "awaiting_capture_review"
            ? await fetchPlotRunCaptureReview(runId)
            : null,
        );
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
    acceptCaptureReview: async (runId: string) => {
      try {
        setBusyAction("review");
        setError(null);
        const response = await acceptPlotRunCaptureReview(runId);
        if (!mountedRef.current) {
          return;
        }
        setLatestRun(response.run);
        setInspectedRun(response.run);
        setInspectedRunId(response.run.id);
        setPendingCaptureReview(null);
        setNotice({ tone: "info", message: response.message });
        await refresh({ silent: true });
      } catch (actionError) {
        if (!mountedRef.current) {
          return;
        }
        const message =
          actionError instanceof Error ? actionError.message : "Failed to accept capture review.";
        setError(message);
        setNotice({ tone: "error", message });
      } finally {
        if (mountedRef.current) {
          setBusyAction(null);
        }
      }
    },
    adjustCaptureReview: async (runId, corners) => {
      try {
        setBusyAction("review");
        setError(null);
        const response = await adjustPlotRunCaptureReview(runId, corners);
        if (!mountedRef.current) {
          return;
        }
        setLatestRun(response.run);
        setInspectedRun(response.run);
        setInspectedRunId(response.run.id);
        setPendingCaptureReview(null);
        setNotice({ tone: "info", message: response.message });
        await refresh({ silent: true });
      } catch (actionError) {
        if (!mountedRef.current) {
          return;
        }
        const message =
          actionError instanceof Error ? actionError.message : "Failed to save adjusted corners.";
        setError(message);
        setNotice({ tone: "error", message });
      } finally {
        if (mountedRef.current) {
          setBusyAction(null);
        }
      }
    },
    reuseLastCaptureReview: async (runId: string) => {
      try {
        setBusyAction("review");
        setError(null);
        const response = await reuseLastPlotRunCaptureReview(runId);
        if (!mountedRef.current) {
          return;
        }
        setLatestRun(response.run);
        setInspectedRun(response.run);
        setInspectedRunId(response.run.id);
        setPendingCaptureReview(null);
        setNotice({ tone: "info", message: response.message });
        await refresh({ silent: true });
      } catch (actionError) {
        if (!mountedRef.current) {
          return;
        }
        const message =
          actionError instanceof Error ? actionError.message : "Failed to reuse the last confirmed quad.";
        setError(message);
        setNotice({ tone: "error", message });
      } finally {
        if (mountedRef.current) {
          setBusyAction(null);
        }
      }
    },
  };
}
