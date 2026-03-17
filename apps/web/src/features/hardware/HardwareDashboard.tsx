import { useEffect, useState } from "react";

import { HardwareCard } from "../../components/HardwareCard";
import { LatestCapturePanel } from "../../components/LatestCapturePanel";
import { PlotWorkflowPanel } from "../plot-workflow/PlotWorkflowPanel";

import { PlotterWorkspacePreview } from "./PlotterWorkspacePreview";
import { useHardwareDashboard } from "./useHardwareDashboard";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

interface PenHeightValues {
  penPosUp: string;
  penPosDown: string;
}

interface CalibrationValue {
  nativeResFactor: string;
}

interface WorkspaceValues {
  pageWidthMm: string;
  pageHeightMm: string;
  marginLeftMm: string;
  marginTopMm: string;
  marginRightMm: string;
  marginBottomMm: string;
}

interface WorkspaceMetrics {
  hasBlank: boolean;
  allFinite: boolean;
  pageWidthMm: number | null;
  pageHeightMm: number | null;
  marginLeftMm: number | null;
  marginTopMm: number | null;
  marginRightMm: number | null;
  marginBottomMm: number | null;
  drawableWidthMm: number | null;
  drawableHeightMm: number | null;
}

function formatLabel(value: string) {
  return value.replace(/_/g, " ");
}

function arePenHeightsEqual(
  left: PenHeightValues | null,
  right: PenHeightValues | null,
) {
  return (
    left?.penPosUp === right?.penPosUp && left?.penPosDown === right?.penPosDown
  );
}

function areCalibrationValuesEqual(
  left: CalibrationValue | null,
  right: CalibrationValue | null,
) {
  return left?.nativeResFactor === right?.nativeResFactor;
}

function areWorkspaceValuesEqual(
  left: WorkspaceValues | null,
  right: WorkspaceValues | null,
) {
  return (
    left?.pageWidthMm === right?.pageWidthMm &&
    left?.pageHeightMm === right?.pageHeightMm &&
    left?.marginLeftMm === right?.marginLeftMm &&
    left?.marginTopMm === right?.marginTopMm &&
    left?.marginRightMm === right?.marginRightMm &&
    left?.marginBottomMm === right?.marginBottomMm
  );
}

function getPenHeightValidation(
  penPosUp: string,
  penPosDown: string,
): string | null {
  if (penPosUp.trim() === "" || penPosDown.trim() === "") {
    return "Enter both pen heights before applying them.";
  }

  const parsedPenPosUp = Number(penPosUp);
  const parsedPenPosDown = Number(penPosDown);

  if (!Number.isFinite(parsedPenPosUp) || !Number.isFinite(parsedPenPosDown)) {
    return "Pen heights must be numeric values.";
  }

  if (
    parsedPenPosUp < 0 ||
    parsedPenPosUp > 100 ||
    parsedPenPosDown < 0 ||
    parsedPenPosDown > 100
  ) {
    return "Pen heights must stay between 0 and 100.";
  }

  if (parsedPenPosDown >= parsedPenPosUp) {
    return "Pen down must be lower than pen up.";
  }

  return null;
}

function getCalibrationValidation(nativeResFactor: string): string | null {
  if (nativeResFactor.trim() === "") {
    return "Enter a native resolution factor before saving.";
  }

  const parsedNativeResFactor = Number(nativeResFactor);
  if (!Number.isFinite(parsedNativeResFactor)) {
    return "Native resolution factor must be numeric.";
  }

  if (parsedNativeResFactor <= 0) {
    return "Native resolution factor must be greater than zero.";
  }

  return null;
}

function getWorkspaceValidation(
  workspace: WorkspaceMetrics,
  plotterBounds: { width_mm: number; height_mm: number } | null,
): string | null {
  if (workspace.hasBlank) {
    return "Enter page size and margins before saving workspace setup.";
  }

  if (!workspace.allFinite) {
    return "Page size and margins must be numeric values.";
  }

  if (
    workspace.pageWidthMm === null ||
    workspace.pageHeightMm === null ||
    workspace.marginLeftMm === null ||
    workspace.marginTopMm === null ||
    workspace.marginRightMm === null ||
    workspace.marginBottomMm === null ||
    workspace.drawableWidthMm === null ||
    workspace.drawableHeightMm === null
  ) {
    return "Enter page size and margins before saving workspace setup.";
  }

  if (workspace.pageWidthMm <= 0 || workspace.pageHeightMm <= 0) {
    return "Page width and height must be greater than zero.";
  }

  if (
    workspace.marginLeftMm < 0 ||
    workspace.marginTopMm < 0 ||
    workspace.marginRightMm < 0 ||
    workspace.marginBottomMm < 0
  ) {
    return "Margins cannot be negative.";
  }

  if (workspace.drawableWidthMm <= 0 || workspace.drawableHeightMm <= 0) {
    return "Safe margins leave no drawable area. Reduce the margins or increase the paper size.";
  }

  if (
    plotterBounds &&
    (workspace.pageWidthMm > plotterBounds.width_mm ||
      workspace.pageHeightMm > plotterBounds.height_mm)
  ) {
    return `Paper size exceeds the plotter's safe bounds of ${plotterBounds.width_mm} x ${plotterBounds.height_mm} mm.`;
  }

  return null;
}

function getWorkspaceMetrics(workspace: WorkspaceValues): WorkspaceMetrics {
  const hasBlank = Object.values(workspace).some((value) => value.trim() === "");
  const pageWidthMm = Number(workspace.pageWidthMm);
  const pageHeightMm = Number(workspace.pageHeightMm);
  const marginLeftMm = Number(workspace.marginLeftMm);
  const marginTopMm = Number(workspace.marginTopMm);
  const marginRightMm = Number(workspace.marginRightMm);
  const marginBottomMm = Number(workspace.marginBottomMm);
  const allFinite = [
    pageWidthMm,
    pageHeightMm,
    marginLeftMm,
    marginTopMm,
    marginRightMm,
    marginBottomMm,
  ].every((value) => Number.isFinite(value));

  return {
    hasBlank,
    allFinite,
    pageWidthMm: allFinite ? pageWidthMm : null,
    pageHeightMm: allFinite ? pageHeightMm : null,
    marginLeftMm: allFinite ? marginLeftMm : null,
    marginTopMm: allFinite ? marginTopMm : null,
    marginRightMm: allFinite ? marginRightMm : null,
    marginBottomMm: allFinite ? marginBottomMm : null,
    drawableWidthMm: allFinite ? pageWidthMm - marginLeftMm - marginRightMm : null,
    drawableHeightMm: allFinite ? pageHeightMm - marginTopMm - marginBottomMm : null,
  };
}

function formatMm(value: number | null) {
  if (value === null) {
    return "unknown";
  }
  return `${value.toFixed(1).replace(/\.0$/, "")} mm`;
}

function renderWorkspaceInput(
  label: string,
  value: string,
  onChange: (value: string) => void,
  disabled: boolean,
  minimum: number,
) {
  return (
    <label className="field-group workspace-field">
      <span>{label}</span>
      <input
        type="number"
        min={minimum}
        step="0.1"
        inputMode="decimal"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
      />
    </label>
  );
}

export function HardwareDashboard() {
  const {
    hardwareStatus,
    latestCapture,
    loading,
    refreshing,
    actionName,
    actionFeedback,
    error,
    refresh,
    plotterCalibration,
    plotterDevice,
    plotterWorkspace,
    walkHome,
    runPlotterTestAction,
    runDiagnosticPattern,
    setPlotterCalibration,
    setPlotterWorkspace,
    setPlotterPenHeights,
    capture,
  } = useHardwareDashboard();
  const [penPosUp, setPenPosUp] = useState("60");
  const [penPosDown, setPenPosDown] = useState("30");
  const [isPenHeightDirty, setIsPenHeightDirty] = useState(false);
  const [lastSyncedPenHeights, setLastSyncedPenHeights] =
    useState<PenHeightValues | null>(null);
  const [pendingAppliedPenHeights, setPendingAppliedPenHeights] =
    useState<PenHeightValues | null>(null);
  const [nativeResFactor, setNativeResFactor] = useState("1016");
  const [isCalibrationDirty, setIsCalibrationDirty] = useState(false);
  const [lastSyncedCalibration, setLastSyncedCalibration] =
    useState<CalibrationValue | null>(null);
  const [pendingAppliedCalibration, setPendingAppliedCalibration] =
    useState<CalibrationValue | null>(null);
  const [workspaceValues, setWorkspaceValues] = useState<WorkspaceValues>({
    pageWidthMm: "210",
    pageHeightMm: "297",
    marginLeftMm: "20",
    marginTopMm: "20",
    marginRightMm: "20",
    marginBottomMm: "20",
  });
  const [isWorkspaceDirty, setIsWorkspaceDirty] = useState(false);
  const [lastSyncedWorkspace, setLastSyncedWorkspace] =
    useState<WorkspaceValues | null>(null);
  const [pendingAppliedWorkspace, setPendingAppliedWorkspace] =
    useState<WorkspaceValues | null>(null);

  const plotterDetails = hardwareStatus?.plotter.details;
  const isAxiDraw = hardwareStatus?.plotter.driver === "axidraw-pyapi";
  const penTuning =
    plotterDetails && isRecord(plotterDetails.pen_tuning) ? plotterDetails.pen_tuning : null;
  const polledPenHeights =
    penTuning &&
    typeof penTuning.pen_pos_up === "number" &&
    typeof penTuning.pen_pos_down === "number"
      ? {
          penPosUp: String(penTuning.pen_pos_up),
          penPosDown: String(penTuning.pen_pos_down),
        }
      : null;
  const effectiveNativeResFactor =
    plotterCalibration &&
    typeof plotterCalibration.driver_calibration.native_res_factor === "number"
      ? String(plotterCalibration.driver_calibration.native_res_factor)
      : plotterDetails && typeof plotterDetails.native_res_factor === "number"
        ? String(plotterDetails.native_res_factor)
        : null;
  const calibrationValue = effectiveNativeResFactor
    ? { nativeResFactor: effectiveNativeResFactor }
    : null;
  const currentWorkspaceValue =
    plotterWorkspace !== null
      ? {
          pageWidthMm: String(plotterWorkspace.page_size_mm.width_mm),
          pageHeightMm: String(plotterWorkspace.page_size_mm.height_mm),
          marginLeftMm: String(plotterWorkspace.margins_mm.left_mm),
          marginTopMm: String(plotterWorkspace.margins_mm.top_mm),
          marginRightMm: String(plotterWorkspace.margins_mm.right_mm),
          marginBottomMm: String(plotterWorkspace.margins_mm.bottom_mm),
        }
      : null;

  useEffect(() => {
    if (!polledPenHeights) {
      return;
    }

    const shouldSyncDraft =
      lastSyncedPenHeights === null ||
      !isPenHeightDirty ||
      arePenHeightsEqual(pendingAppliedPenHeights, polledPenHeights);

    if (!shouldSyncDraft) {
      return;
    }

    if (
      penPosUp !== polledPenHeights.penPosUp ||
      penPosDown !== polledPenHeights.penPosDown
    ) {
      setPenPosUp(polledPenHeights.penPosUp);
      setPenPosDown(polledPenHeights.penPosDown);
    }

    if (!arePenHeightsEqual(lastSyncedPenHeights, polledPenHeights)) {
      setLastSyncedPenHeights(polledPenHeights);
    }

    if (arePenHeightsEqual(pendingAppliedPenHeights, polledPenHeights)) {
      setIsPenHeightDirty(false);
      setPendingAppliedPenHeights(null);
    }
  }, [
    isPenHeightDirty,
    lastSyncedPenHeights,
    pendingAppliedPenHeights,
    penPosDown,
    penPosUp,
    polledPenHeights,
  ]);

  useEffect(() => {
    if (
      actionFeedback?.action === "plotter-pen-heights" &&
      actionFeedback.tone === "error"
    ) {
      setPendingAppliedPenHeights(null);
    }
  }, [actionFeedback]);

  useEffect(() => {
    if (!calibrationValue) {
      return;
    }

    const shouldSyncDraft =
      lastSyncedCalibration === null ||
      !isCalibrationDirty ||
      areCalibrationValuesEqual(pendingAppliedCalibration, calibrationValue);

    if (!shouldSyncDraft) {
      return;
    }

    if (nativeResFactor !== calibrationValue.nativeResFactor) {
      setNativeResFactor(calibrationValue.nativeResFactor);
    }

    if (!areCalibrationValuesEqual(lastSyncedCalibration, calibrationValue)) {
      setLastSyncedCalibration(calibrationValue);
    }

    if (areCalibrationValuesEqual(pendingAppliedCalibration, calibrationValue)) {
      setIsCalibrationDirty(false);
      setPendingAppliedCalibration(null);
    }
  }, [
    calibrationValue,
    isCalibrationDirty,
    lastSyncedCalibration,
    nativeResFactor,
    pendingAppliedCalibration,
  ]);

  useEffect(() => {
    if (
      actionFeedback?.action === "plotter-calibration" &&
      actionFeedback.tone === "error"
    ) {
      setPendingAppliedCalibration(null);
    }
  }, [actionFeedback]);

  useEffect(() => {
    if (!currentWorkspaceValue) {
      return;
    }

    const shouldSyncDraft =
      lastSyncedWorkspace === null ||
      !isWorkspaceDirty ||
      areWorkspaceValuesEqual(pendingAppliedWorkspace, currentWorkspaceValue);

    if (!shouldSyncDraft) {
      return;
    }

    if (!areWorkspaceValuesEqual(workspaceValues, currentWorkspaceValue)) {
      setWorkspaceValues(currentWorkspaceValue);
    }

    if (!areWorkspaceValuesEqual(lastSyncedWorkspace, currentWorkspaceValue)) {
      setLastSyncedWorkspace(currentWorkspaceValue);
    }

    if (areWorkspaceValuesEqual(pendingAppliedWorkspace, currentWorkspaceValue)) {
      setIsWorkspaceDirty(false);
      setPendingAppliedWorkspace(null);
    }
  }, [
    currentWorkspaceValue,
    isWorkspaceDirty,
    lastSyncedWorkspace,
    pendingAppliedWorkspace,
    workspaceValues,
  ]);

  useEffect(() => {
    if (
      actionFeedback?.action === "plotter-workspace" &&
      actionFeedback.tone === "error"
    ) {
      setPendingAppliedWorkspace(null);
    }
  }, [actionFeedback]);

  if (loading && !hardwareStatus) {
    return (
      <main className="page-shell">
        <section className="hero-card">
          <h1>Booting local hardware control.</h1>
          <p>Waiting for backend status and latest capture metadata.</p>
        </section>
      </main>
    );
  }

  if (!hardwareStatus) {
    return (
      <main className="page-shell">
        <section className="hero-card">
          <h1>Hardware status unavailable.</h1>
          <p>Check that the backend is running on localhost and try again.</p>
          <div className="actions" style={{ marginTop: 16 }}>
            <button
              type="button"
              className="button-primary"
              onClick={() => void refresh()}
            >
              Retry
            </button>
          </div>
        </section>
      </main>
    );
  }

  const plotterDetailsRecord = hardwareStatus.plotter.details;
  const penTuningRecord = isRecord(plotterDetailsRecord.pen_tuning)
    ? plotterDetailsRecord.pen_tuning
    : null;
  const apiSurface =
    typeof plotterDetailsRecord.api_surface === "string"
      ? plotterDetailsRecord.api_surface
      : null;
  const plotApiSupported = plotterDetailsRecord.plot_api_supported === true;
  const manualApiSupported = plotterDetailsRecord.manual_api_supported === true;
  const lastTestAction =
    typeof plotterDetailsRecord.last_test_action === "string"
      ? plotterDetailsRecord.last_test_action
      : null;
  const lastTestActionStatus =
    typeof plotterDetailsRecord.last_test_action_status === "string"
      ? plotterDetailsRecord.last_test_action_status
      : null;
  const penHeightValidation = getPenHeightValidation(penPosUp, penPosDown);
  const calibrationValidation = getCalibrationValidation(nativeResFactor);
  const workspaceMetrics = getWorkspaceMetrics(workspaceValues);
  const workspaceValidation = getWorkspaceValidation(
    workspaceMetrics,
    plotterDevice?.plotter_bounds_mm ?? plotterWorkspace?.plotter_bounds_mm ?? null,
  );
  const configSource =
    typeof plotterDetailsRecord.config_source === "string"
      ? plotterDetailsRecord.config_source
      : null;
  const calibrationSource =
    plotterCalibration?.source ??
    (typeof plotterDetailsRecord.calibration_source === "string"
      ? plotterDetailsRecord.calibration_source
      : null);
  const motionScale =
    typeof plotterDetailsRecord.motion_scale === "number"
      ? plotterDetailsRecord.motion_scale
      : plotterCalibration?.motion_scale ?? null;
  const plotterModelLabel = plotterDevice?.plotter_model?.label ?? null;
  const plotterBoundsSource = plotterDevice?.plotter_bounds_source ?? null;
  const drawableWidth = workspaceMetrics.drawableWidthMm;
  const drawableHeight = workspaceMetrics.drawableHeightMm;
  const workspaceSourceLabel = plotterWorkspace?.source
    ? formatLabel(plotterWorkspace.source)
    : null;
  const drawableAreaValid =
    workspaceMetrics.drawableWidthMm !== null &&
    workspaceMetrics.drawableHeightMm !== null &&
    workspaceMetrics.drawableWidthMm > 0 &&
    workspaceMetrics.drawableHeightMm > 0 &&
    workspaceValidation === null;

  const penHeightDisabled =
    actionName !== null || hardwareStatus.plotter.busy || !hardwareStatus.plotter.available;
  const calibrationDisabled =
    actionName !== null || hardwareStatus.plotter.busy || !hardwareStatus.plotter.available;
  const workspaceDisabled =
    actionName !== null || hardwareStatus.plotter.busy || !hardwareStatus.plotter.available;

  function handlePenHeightChange(nextValues: PenHeightValues) {
    setPenPosUp(nextValues.penPosUp);
    setPenPosDown(nextValues.penPosDown);
    setIsPenHeightDirty(!arePenHeightsEqual(nextValues, lastSyncedPenHeights));
  }

  function handleCalibrationChange(nextValue: string) {
    setNativeResFactor(nextValue);
    setIsCalibrationDirty(
      !areCalibrationValuesEqual(
        { nativeResFactor: nextValue },
        lastSyncedCalibration,
      ),
    );
  }

  function handleWorkspaceChange(nextValues: WorkspaceValues) {
    setWorkspaceValues(nextValues);
    setIsWorkspaceDirty(!areWorkspaceValuesEqual(nextValues, lastSyncedWorkspace));
  }

  return (
    <main className="page-shell">
      <section className="hero">
        <div className="hero-card">
          <h1>LearnToDraw local control panel</h1>
          <p>
            Backend-owned hardware control for the first vertical slice. The UI
            polls device state, triggers mock actions, and previews the latest
            saved capture.
          </p>
        </div>

        <aside className="hero-metrics">
          <div className="metric">
            <span className="metric-label">Plotter driver</span>
            <span className="metric-value">{hardwareStatus.plotter.driver}</span>
          </div>
          <div className="metric">
            <span className="metric-label">Camera driver</span>
            <span className="metric-value">{hardwareStatus.camera.driver}</span>
          </div>
          <div className="metric">
            <span className="metric-label">Latest capture</span>
            <span className="metric-value">
              {latestCapture ? latestCapture.id.slice(0, 8) : "none"}
            </span>
          </div>
        </aside>
      </section>

      {error ? <div className="banner">{error}</div> : null}

      <section className="status-grid">
        <HardwareCard
          title="Plotter"
          status={hardwareStatus.plotter}
          notice={
            hardwareStatus.plotter.error
              ? { tone: "error", message: hardwareStatus.plotter.error }
              : actionFeedback &&
                  (actionFeedback.action === "plotter-walk-home" ||
                    actionFeedback.action === "plotter-calibration" ||
                    actionFeedback.action === "plotter-workspace" ||
                    actionFeedback.action === "plotter-pen-heights" ||
                    actionFeedback.action.startsWith("plotter-test:") ||
                    actionFeedback.action.startsWith("plotter-pattern:"))
                ? {
                    tone: actionFeedback.tone,
                    message: actionFeedback.message,
                  }
                : null
          }
          children={
            <div className="diagnostic-panel">
              {isAxiDraw ? (
                <>
                <div className="diagnostic-section">
                  <h3>AxiDraw controls</h3>
                  {!plotApiSupported && manualApiSupported && hardwareStatus.plotter.connected ? (
                    <div className="inline-notice inline-notice-info">
                      Diagnostics are available, but trusted SVG plotting is disabled until the
                      official pyaxidraw Plot API is installed and exposes plot_setup() and
                      plot_run().
                    </div>
                  ) : null}
                  <div className="actions">
                    <button
                      type="button"
                      className="button-primary"
                      onClick={() => void walkHome()}
                      disabled={
                        actionName !== null ||
                        hardwareStatus.plotter.busy ||
                        !hardwareStatus.plotter.available
                      }
                    >
                      Walk home
                    </button>
                    <button
                      type="button"
                      className="button-secondary"
                      onClick={() => void runPlotterTestAction("align")}
                      disabled={
                        actionName !== null ||
                        hardwareStatus.plotter.busy ||
                        !hardwareStatus.plotter.available
                      }
                    >
                      Disengage motors
                    </button>
                    <button
                      type="button"
                      className="button-secondary"
                      onClick={() => void runPlotterTestAction("raise_pen")}
                      disabled={
                        actionName !== null ||
                        hardwareStatus.plotter.busy ||
                        !hardwareStatus.plotter.available
                      }
                    >
                      Raise pen
                    </button>
                    <button
                      type="button"
                      className="button-secondary"
                      onClick={() => void runPlotterTestAction("lower_pen")}
                      disabled={
                        actionName !== null ||
                        hardwareStatus.plotter.busy ||
                        !hardwareStatus.plotter.available
                      }
                    >
                      Lower pen
                    </button>
                    <button
                      type="button"
                      className="button-secondary"
                      onClick={() => void runPlotterTestAction("cycle_pen")}
                      disabled={
                        actionName !== null ||
                        hardwareStatus.plotter.busy ||
                        !hardwareStatus.plotter.available
                      }
                    >
                      Cycle pen
                    </button>
                  </div>
                  <div className="diagnostic-subsection">
                    <h4>Pen heights</h4>
                    <div className="pen-height-grid">
                      <label className="field-group">
                        <span>Pen up</span>
                        <input
                          type="number"
                          min={0}
                          max={100}
                          value={penPosUp}
                          onChange={(event) =>
                            handlePenHeightChange({
                              penPosUp: event.target.value,
                              penPosDown,
                            })
                          }
                          disabled={penHeightDisabled}
                        />
                      </label>
                      <label className="field-group">
                        <span>Pen down</span>
                        <input
                          type="number"
                          min={0}
                          max={100}
                          value={penPosDown}
                          onChange={(event) =>
                            handlePenHeightChange({
                              penPosUp,
                              penPosDown: event.target.value,
                            })
                          }
                          disabled={penHeightDisabled}
                        />
                      </label>
                      <button
                        type="button"
                        className="button-secondary"
                        onClick={() => {
                          setPendingAppliedPenHeights({ penPosUp, penPosDown });
                          void setPlotterPenHeights(Number(penPosUp), Number(penPosDown));
                        }}
                        disabled={
                          penHeightDisabled ||
                          penHeightValidation !== null ||
                          arePenHeightsEqual(
                            { penPosUp, penPosDown },
                            lastSyncedPenHeights,
                          )
                        }
                      >
                        Apply heights
                      </button>
                    </div>
                    {penHeightValidation ? (
                      <div className="inline-notice inline-notice-error">
                        {penHeightValidation}
                      </div>
                    ) : null}
                    {penTuningRecord ? (
                      <p className="footer-note">
                        Effective backend tuning: up {String(penTuningRecord.pen_pos_up)} · down{" "}
                        {String(penTuningRecord.pen_pos_down)}
                      </p>
                    ) : null}
                  </div>
                </div>
                </>
              ) : null}

              <div className="diagnostic-section workspace-section">
                <div className="workspace-header">
                  <div>
                    <h3>Paper setup</h3>
                    <p className="hardware-meta">
                      Confirm the machine capability, set the paper on the plotter, and review
                      the drawable area before you start a run.
                    </p>
                  </div>
                </div>
                <div className="workspace-stack">
                  <div className="workspace-card">
                    <div className="workspace-card-header">
                      <h4>Plotter</h4>
                      <span className="workspace-unit-chip">Read only</span>
                    </div>
                    <ul className="details-list compact-details workspace-capability-list">
                      <li>
                        <span>Model</span>
                        <strong>{plotterModelLabel ?? "Model unavailable"}</strong>
                      </li>
                      <li>
                        <span>Safe plotter bounds</span>
                        <strong>
                          {plotterDevice
                            ? `${formatMm(plotterDevice.plotter_bounds_mm.width_mm)} x ${formatMm(
                                plotterDevice.plotter_bounds_mm.height_mm,
                              )}`
                            : "unknown"}
                        </strong>
                      </li>
                      {plotterBoundsSource ? (
                        <li>
                          <span>Bounds source</span>
                          <strong>{formatLabel(plotterBoundsSource)}</strong>
                        </li>
                      ) : null}
                    </ul>
                  </div>

                  <div className="workspace-layout">
                    <div className="workspace-card">
                      <div className="workspace-card-header">
                        <h4>Paper on plotter</h4>
                      </div>
                      <div className="workspace-form-sections">
                        <div className="workspace-form-section">
                          <div className="workspace-form-label">Paper size</div>
                          <div className="workspace-grid workspace-grid-two">
                            {renderWorkspaceInput(
                              "Width",
                              workspaceValues.pageWidthMm,
                              (nextValue) =>
                                handleWorkspaceChange({
                                  ...workspaceValues,
                                  pageWidthMm: nextValue,
                                }),
                              workspaceDisabled,
                              1,
                            )}
                            {renderWorkspaceInput(
                              "Height",
                              workspaceValues.pageHeightMm,
                              (nextValue) =>
                                handleWorkspaceChange({
                                  ...workspaceValues,
                                  pageHeightMm: nextValue,
                                }),
                              workspaceDisabled,
                              1,
                            )}
                          </div>
                        </div>

                        <div className="workspace-form-section">
                          <div className="workspace-form-label">Safe margins</div>
                          <div className="workspace-grid workspace-grid-margins">
                            {renderWorkspaceInput(
                              "Left",
                              workspaceValues.marginLeftMm,
                              (nextValue) =>
                                handleWorkspaceChange({
                                  ...workspaceValues,
                                  marginLeftMm: nextValue,
                                }),
                              workspaceDisabled,
                              0,
                            )}
                            {renderWorkspaceInput(
                              "Top",
                              workspaceValues.marginTopMm,
                              (nextValue) =>
                                handleWorkspaceChange({
                                  ...workspaceValues,
                                  marginTopMm: nextValue,
                                }),
                              workspaceDisabled,
                              0,
                            )}
                            {renderWorkspaceInput(
                              "Right",
                              workspaceValues.marginRightMm,
                              (nextValue) =>
                                handleWorkspaceChange({
                                  ...workspaceValues,
                                  marginRightMm: nextValue,
                                }),
                              workspaceDisabled,
                              0,
                            )}
                            {renderWorkspaceInput(
                              "Bottom",
                              workspaceValues.marginBottomMm,
                              (nextValue) =>
                                handleWorkspaceChange({
                                  ...workspaceValues,
                                  marginBottomMm: nextValue,
                                }),
                              workspaceDisabled,
                              0,
                            )}
                          </div>
                        </div>
                      </div>
                      <div className="section-actions workspace-actions">
                        <button
                          type="button"
                          className="button-secondary button-compact"
                          onClick={() => {
                            setPendingAppliedWorkspace(workspaceValues);
                            void setPlotterWorkspace({
                              page_width_mm: Number(workspaceValues.pageWidthMm),
                              page_height_mm: Number(workspaceValues.pageHeightMm),
                              margin_left_mm: Number(workspaceValues.marginLeftMm),
                              margin_top_mm: Number(workspaceValues.marginTopMm),
                              margin_right_mm: Number(workspaceValues.marginRightMm),
                              margin_bottom_mm: Number(workspaceValues.marginBottomMm),
                            });
                          }}
                          disabled={
                            workspaceDisabled ||
                            workspaceValidation !== null ||
                            areWorkspaceValuesEqual(workspaceValues, lastSyncedWorkspace)
                          }
                        >
                          Save paper setup
                        </button>
                      </div>
                    </div>

                    <div className="workspace-aside">
                      <div className="workspace-card workspace-preview-card">
                        <div className="workspace-card-header">
                          <h4>Preview</h4>
                          {workspaceSourceLabel ? (
                            <span className="workspace-source-label">
                              source {workspaceSourceLabel}
                            </span>
                          ) : null}
                        </div>
                        <div className="workspace-preview-summary">
                          <span className="workspace-preview-summary-label">Drawable area</span>
                          <strong className="workspace-preview-summary-value">
                            {formatMm(drawableWidth)} x {formatMm(drawableHeight)}
                          </strong>
                        </div>
                        {workspaceValidation ? (
                          <div className="inline-notice inline-notice-error workspace-inline-notice">
                            {workspaceValidation}
                          </div>
                        ) : null}
                        <PlotterWorkspacePreview
                          pageWidthMm={workspaceMetrics.pageWidthMm}
                          pageHeightMm={workspaceMetrics.pageHeightMm}
                          marginLeftMm={workspaceMetrics.marginLeftMm}
                          marginTopMm={workspaceMetrics.marginTopMm}
                          marginRightMm={workspaceMetrics.marginRightMm}
                          marginBottomMm={workspaceMetrics.marginBottomMm}
                          drawableWidthMm={workspaceMetrics.drawableWidthMm}
                          drawableHeightMm={workspaceMetrics.drawableHeightMm}
                          isValid={drawableAreaValid}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {isAxiDraw ? (
                <>
                <div className="diagnostic-section">
                  <h3>Diagnostic plots</h3>
                  <div className="actions">
                    <button
                      type="button"
                      className="button-secondary"
                      onClick={() => void runDiagnosticPattern("tiny-square")}
                      disabled={
                        actionName !== null ||
                        hardwareStatus.plotter.busy ||
                        !hardwareStatus.plotter.available
                      }
                    >
                      Tiny square
                    </button>
                    <button
                      type="button"
                      className="button-secondary"
                      onClick={() => void runDiagnosticPattern("dash-row")}
                      disabled={
                        actionName !== null ||
                        hardwareStatus.plotter.busy ||
                        !hardwareStatus.plotter.available
                      }
                    >
                      Dash row
                    </button>
                    <button
                      type="button"
                      className="button-secondary"
                      onClick={() => void runDiagnosticPattern("double-box")}
                      disabled={
                        actionName !== null ||
                        hardwareStatus.plotter.busy ||
                        !hardwareStatus.plotter.available
                      }
                    >
                      Double box
                    </button>
                  </div>
                </div>

                <div className="diagnostic-section">
                  <h3>Effective tuning</h3>
                  <ul className="details-list compact-details">
                    {apiSurface ? (
                      <li>
                        <span>API surface</span>
                        <strong>{apiSurface}</strong>
                      </li>
                    ) : null}
                    <li>
                      <span>Plot API support</span>
                      <strong>{plotApiSupported ? "yes" : "no"}</strong>
                    </li>
                    <li>
                      <span>Manual API support</span>
                      <strong>{manualApiSupported ? "yes" : "no"}</strong>
                    </li>
                    {motionScale !== null ? (
                      <li>
                        <span>Motion scale</span>
                        <strong>{motionScale.toFixed(6)}</strong>
                      </li>
                    ) : null}
                    {effectiveNativeResFactor ? (
                      <li>
                        <span>Native res factor</span>
                        <strong>{effectiveNativeResFactor}</strong>
                      </li>
                    ) : null}
                    {calibrationSource ? (
                      <li>
                        <span>Calibration source</span>
                        <strong>{formatLabel(calibrationSource)}</strong>
                      </li>
                    ) : null}
                    {configSource ? (
                      <li>
                        <span>Config source</span>
                        <strong>{formatLabel(configSource)}</strong>
                      </li>
                    ) : null}
                    {lastTestAction ? (
                      <li>
                        <span>Last test action</span>
                        <strong>
                          {formatLabel(lastTestAction)}
                          {lastTestActionStatus ? ` · ${lastTestActionStatus}` : ""}
                        </strong>
                      </li>
                    ) : null}
                    {penTuning
                      ? Object.entries(penTuning)
                          .filter(([key]) => key !== "pen_pos_up" && key !== "pen_pos_down")
                          .map(([key, value]) => (
                          <li key={key}>
                            <span>{key}</span>
                            <strong>{String(value)}</strong>
                          </li>
                          ))
                      : null}
                  </ul>
                </div>

                <div className="diagnostic-section">
                  <h3>Persisted calibration</h3>
                  <div className="pen-height-grid">
                    <label className="field-group">
                      <span>Native res factor</span>
                      <input
                        type="number"
                        min={0}
                        step="0.001"
                        value={nativeResFactor}
                        onChange={(event) => handleCalibrationChange(event.target.value)}
                        disabled={calibrationDisabled}
                      />
                    </label>
                    <button
                      type="button"
                      className="button-secondary"
                      onClick={() => {
                        setPendingAppliedCalibration({ nativeResFactor });
                        void setPlotterCalibration(Number(nativeResFactor));
                      }}
                      disabled={
                        calibrationDisabled ||
                        calibrationValidation !== null ||
                        areCalibrationValuesEqual(
                          { nativeResFactor },
                          lastSyncedCalibration,
                        )
                      }
                    >
                      Save calibration
                    </button>
                  </div>
                  {calibrationValidation ? (
                    <div className="inline-notice inline-notice-error">
                      {calibrationValidation}
                    </div>
                  ) : null}
                  {calibrationSource === "env_override" ? (
                    <div className="inline-notice inline-notice-info">
                      An environment override is currently active. Saved calibration will persist,
                      but it will not become the effective value until the override is removed and
                      the backend is restarted.
                    </div>
                  ) : null}
                  <p className="footer-note">
                    This saves the app-owned calibration record. Motion scale is derived from the
                    saved AxiDraw native resolution factor.
                  </p>
                </div>
                </>
              ) : null}
            </div>
          }
          footer={
            <p className="footer-note">
              Backend-controlled motion only. “Walk home” moves to the AxiDraw
              internal start position. “Disengage motors” enters AxiDraw align
              mode so the carriage can be repositioned by hand.
            </p>
          }
        />

        <HardwareCard
          title="Camera"
          actionLabel="Capture image"
          status={hardwareStatus.camera}
          onAction={capture}
          actionPending={actionName === "camera-capture"}
          notice={
            hardwareStatus.camera.error
              ? { tone: "error", message: hardwareStatus.camera.error }
              : actionFeedback?.action === "camera-capture"
                ? {
                    tone: actionFeedback.tone,
                    message: actionFeedback.message,
                  }
                : null
          }
          footer={
            <p className="footer-note">
              Captures are saved locally and served back through the backend.
            </p>
          }
        />
      </section>

      <PlotWorkflowPanel
        hardwareStatus={hardwareStatus}
        plotterWorkspace={plotterWorkspace}
      />

      <LatestCapturePanel capture={latestCapture} refreshing={refreshing} />
    </main>
  );
}
