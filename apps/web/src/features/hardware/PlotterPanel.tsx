import { HardwareCard } from "../../components/HardwareCard";
import type {
  HardwareStatus,
  PlotterCalibration,
  PlotterDeviceSettings,
  PlotterWorkspace,
} from "../../types/hardware";
import { PlotterWorkspacePreview } from "./PlotterWorkspacePreview";
import type {
  ActionFeedback,
  ActionName,
  DiagnosticPatternId,
  PlotterDiagnosticAction,
} from "./hardwareDashboardTypes";
import {
  formatLabel,
  formatMm,
  getCalibrationValidation,
  getPenHeightValidation,
  getSafeBoundsValidation,
  getWorkspaceMetrics,
  getWorkspaceValidation,
  isRecord,
} from "./hardwareDashboardUtils";
import { usePlotterFormDrafts } from "./usePlotterFormDrafts";


interface PlotterPanelProps {
  hardwareStatus: HardwareStatus;
  plotterCalibration: PlotterCalibration | null;
  plotterDevice: PlotterDeviceSettings | null;
  plotterWorkspace: PlotterWorkspace | null;
  actionName: ActionName;
  actionFeedback: ActionFeedback | null;
  walkHome: () => Promise<void>;
  runPlotterTestAction: (action: PlotterDiagnosticAction) => Promise<void>;
  runDiagnosticPattern: (patternId: DiagnosticPatternId) => Promise<void>;
  setPlotterCalibration: (nativeResFactor: number) => Promise<void>;
  setPlotterSafeBounds: (safeBounds: {
    width_mm: number | null;
    height_mm: number | null;
  }) => Promise<void>;
  setPlotterWorkspace: (workspace: {
    page_width_mm: number;
    page_height_mm: number;
    margin_left_mm: number;
    margin_top_mm: number;
    margin_right_mm: number;
    margin_bottom_mm: number;
  }) => Promise<void>;
  setPlotterPenHeights: (penPosUp: number, penPosDown: number) => Promise<void>;
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


export function PlotterPanel({
  hardwareStatus,
  plotterCalibration,
  plotterDevice,
  plotterWorkspace,
  actionName,
  actionFeedback,
  walkHome,
  runPlotterTestAction,
  runDiagnosticPattern,
  setPlotterCalibration,
  setPlotterSafeBounds,
  setPlotterWorkspace,
  setPlotterPenHeights,
}: PlotterPanelProps) {
  const plotterDetails = hardwareStatus.plotter.details;
  const isAxiDraw = hardwareStatus.plotter.driver === "axidraw-pyapi";
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

  const formDrafts = usePlotterFormDrafts({
    polledPenHeights,
    effectiveNativeResFactor,
    plotterDevice,
    plotterWorkspace,
    actionFeedback,
  });

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
  const penHeightValidation = getPenHeightValidation(
    formDrafts.penPosUp,
    formDrafts.penPosDown,
  );
  const calibrationValidation = getCalibrationValidation(formDrafts.nativeResFactor);
  const nominalPlotterBounds = plotterDevice?.nominal_plotter_bounds_mm ?? null;
  const safeBoundsValidation = getSafeBoundsValidation(
    formDrafts.safeBoundsValues,
    nominalPlotterBounds,
  );
  const workspaceMetrics = getWorkspaceMetrics(formDrafts.workspaceValues);
  const workspaceValidation = getWorkspaceValidation(
    workspaceMetrics,
    plotterDevice?.plotter_bounds_mm ?? plotterWorkspace?.plotter_bounds_mm ?? null,
  );
  const persistedWorkspaceValidationError =
    plotterWorkspace?.is_valid === false
      ? plotterWorkspace.validation_error ??
        "Saved paper setup no longer fits the current plotter bounds."
      : null;
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
  const nominalPlotterBoundsSource =
    plotterDevice?.nominal_plotter_bounds_source ?? null;
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
  const safeBoundsDisabled =
    actionName !== null || hardwareStatus.plotter.busy || !hardwareStatus.plotter.available;
  const workspaceDisabled =
    actionName !== null || hardwareStatus.plotter.busy || !hardwareStatus.plotter.available;

  return (
    <HardwareCard
      title="Plotter"
      status={hardwareStatus.plotter}
      notice={
        hardwareStatus.plotter.error
          ? { tone: "error", message: hardwareStatus.plotter.error }
          : actionFeedback &&
              (actionFeedback.action === "plotter-walk-home" ||
                actionFeedback.action === "plotter-calibration" ||
                actionFeedback.action === "plotter-safe-bounds" ||
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
      footer={
        <p className="footer-note">
          Backend-controlled motion only. “Walk home” moves to the AxiDraw
          internal start position. “Disengage motors” enters AxiDraw align mode
          so the carriage can be repositioned by hand.
        </p>
      }
    >
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
                      value={formDrafts.penPosUp}
                      onChange={(event) =>
                        formDrafts.setPenDraft({
                          penPosUp: event.target.value,
                          penPosDown: formDrafts.penPosDown,
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
                      value={formDrafts.penPosDown}
                      onChange={(event) =>
                        formDrafts.setPenDraft({
                          penPosUp: formDrafts.penPosUp,
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
                      formDrafts.stagePenHeightsApply();
                      void setPlotterPenHeights(
                        Number(formDrafts.penPosUp),
                        Number(formDrafts.penPosDown),
                      );
                    }}
                    disabled={
                      penHeightDisabled ||
                      penHeightValidation !== null ||
                      formDrafts.penHeightsSynced
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
                <span className="workspace-unit-chip">Backend owned</span>
              </div>
              <ul className="details-list compact-details workspace-capability-list">
                <li>
                  <span>Model</span>
                  <strong>{plotterModelLabel ?? "Model unavailable"}</strong>
                </li>
                <li>
                  <span>Nominal machine bounds</span>
                  <strong>
                    {plotterDevice
                      ? `${formatMm(plotterDevice.nominal_plotter_bounds_mm.width_mm)} x ${formatMm(
                          plotterDevice.nominal_plotter_bounds_mm.height_mm,
                        )}`
                      : "unknown"}
                  </strong>
                </li>
                {nominalPlotterBoundsSource ? (
                  <li>
                    <span>Nominal source</span>
                    <strong>{formatLabel(nominalPlotterBoundsSource)}</strong>
                  </li>
                ) : null}
                <li>
                  <span>Operational safe bounds</span>
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
                    <span>Operational source</span>
                    <strong>{formatLabel(plotterBoundsSource)}</strong>
                  </li>
                ) : null}
              </ul>
              {isAxiDraw ? (
                <div className="diagnostic-subsection">
                  <h4>Operational safe bounds</h4>
                  <div className="workspace-grid workspace-grid-two">
                    {renderWorkspaceInput(
                      "Width",
                      formDrafts.safeBoundsValues.widthMm,
                      (nextValue) =>
                        formDrafts.setSafeBoundsDraft({
                          ...formDrafts.safeBoundsValues,
                          widthMm: nextValue,
                        }),
                      safeBoundsDisabled,
                      1,
                    )}
                    {renderWorkspaceInput(
                      "Height",
                      formDrafts.safeBoundsValues.heightMm,
                      (nextValue) =>
                        formDrafts.setSafeBoundsDraft({
                          ...formDrafts.safeBoundsValues,
                          heightMm: nextValue,
                        }),
                      safeBoundsDisabled,
                      1,
                    )}
                  </div>
                  <div className="section-actions workspace-actions">
                    <button
                      type="button"
                      className="button-secondary button-compact"
                      onClick={() => {
                        formDrafts.stageSafeBoundsApply();
                        void setPlotterSafeBounds({
                          width_mm: Number(formDrafts.safeBoundsValues.widthMm),
                          height_mm: Number(formDrafts.safeBoundsValues.heightMm),
                        });
                      }}
                      disabled={
                        safeBoundsDisabled ||
                        safeBoundsValidation !== null ||
                        formDrafts.safeBoundsSynced
                      }
                    >
                      Save safe bounds
                    </button>
                    <button
                      type="button"
                      className="button-secondary button-compact"
                      onClick={() => {
                        formDrafts.clearPendingSafeBoundsApply();
                        void setPlotterSafeBounds({
                          width_mm: null,
                          height_mm: null,
                        });
                      }}
                      disabled={
                        safeBoundsDisabled ||
                        plotterBoundsSource === "default_clearance"
                      }
                    >
                      Reset to default clearance
                    </button>
                  </div>
                  {safeBoundsValidation ? (
                    <div className="inline-notice inline-notice-error workspace-inline-notice">
                      {safeBoundsValidation}
                    </div>
                  ) : null}
                  <p className="footer-note">
                    Operational safe bounds are the backend-owned plotting envelope. Default
                    clearance trims the nominal machine travel on the far right and bottom
                    edges.
                  </p>
                </div>
              ) : null}
            </div>

            <div className="workspace-layout">
              <div className="workspace-card">
                <div className="workspace-card-header">
                  <h4>Paper on plotter</h4>
                </div>
                {persistedWorkspaceValidationError ? (
                  <div className="inline-notice inline-notice-error workspace-inline-notice">
                    Saved paper setup is invalid for the current machine bounds:{" "}
                    {persistedWorkspaceValidationError} Update it and save before plotting.
                  </div>
                ) : null}
                <div className="workspace-form-sections">
                  <div className="workspace-form-section">
                    <div className="workspace-form-label">Paper size</div>
                    <div className="workspace-grid workspace-grid-two">
                      {renderWorkspaceInput(
                        "Width",
                        formDrafts.workspaceValues.pageWidthMm,
                        (nextValue) =>
                          formDrafts.setWorkspaceDraft({
                            ...formDrafts.workspaceValues,
                            pageWidthMm: nextValue,
                          }),
                        workspaceDisabled,
                        1,
                      )}
                      {renderWorkspaceInput(
                        "Height",
                        formDrafts.workspaceValues.pageHeightMm,
                        (nextValue) =>
                          formDrafts.setWorkspaceDraft({
                            ...formDrafts.workspaceValues,
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
                        formDrafts.workspaceValues.marginLeftMm,
                        (nextValue) =>
                          formDrafts.setWorkspaceDraft({
                            ...formDrafts.workspaceValues,
                            marginLeftMm: nextValue,
                          }),
                        workspaceDisabled,
                        0,
                      )}
                      {renderWorkspaceInput(
                        "Top",
                        formDrafts.workspaceValues.marginTopMm,
                        (nextValue) =>
                          formDrafts.setWorkspaceDraft({
                            ...formDrafts.workspaceValues,
                            marginTopMm: nextValue,
                          }),
                        workspaceDisabled,
                        0,
                      )}
                      {renderWorkspaceInput(
                        "Right",
                        formDrafts.workspaceValues.marginRightMm,
                        (nextValue) =>
                          formDrafts.setWorkspaceDraft({
                            ...formDrafts.workspaceValues,
                            marginRightMm: nextValue,
                          }),
                        workspaceDisabled,
                        0,
                      )}
                      {renderWorkspaceInput(
                        "Bottom",
                        formDrafts.workspaceValues.marginBottomMm,
                        (nextValue) =>
                          formDrafts.setWorkspaceDraft({
                            ...formDrafts.workspaceValues,
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
                      formDrafts.stageWorkspaceApply();
                      void setPlotterWorkspace({
                        page_width_mm: Number(formDrafts.workspaceValues.pageWidthMm),
                        page_height_mm: Number(formDrafts.workspaceValues.pageHeightMm),
                        margin_left_mm: Number(formDrafts.workspaceValues.marginLeftMm),
                        margin_top_mm: Number(formDrafts.workspaceValues.marginTopMm),
                        margin_right_mm: Number(formDrafts.workspaceValues.marginRightMm),
                        margin_bottom_mm: Number(formDrafts.workspaceValues.marginBottomMm),
                      });
                    }}
                    disabled={
                      workspaceDisabled ||
                      workspaceValidation !== null ||
                      formDrafts.workspaceSynced
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
              {persistedWorkspaceValidationError ? (
                <div className="inline-notice inline-notice-error">
                  Plotting is blocked until the paper setup fits the current machine bounds.
                </div>
              ) : null}
              <div className="actions">
                <button
                  type="button"
                  className="button-secondary"
                  onClick={() => void runDiagnosticPattern("tiny-square")}
                  disabled={
                    actionName !== null ||
                    hardwareStatus.plotter.busy ||
                    !hardwareStatus.plotter.available ||
                    persistedWorkspaceValidationError !== null
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
                    !hardwareStatus.plotter.available ||
                    persistedWorkspaceValidationError !== null
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
                    !hardwareStatus.plotter.available ||
                    persistedWorkspaceValidationError !== null
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
                    value={formDrafts.nativeResFactor}
                    onChange={(event) => formDrafts.setCalibrationDraft(event.target.value)}
                    disabled={calibrationDisabled}
                  />
                </label>
                <button
                  type="button"
                  className="button-secondary"
                  onClick={() => {
                    formDrafts.stageCalibrationApply();
                    void setPlotterCalibration(Number(formDrafts.nativeResFactor));
                  }}
                  disabled={
                    calibrationDisabled ||
                    calibrationValidation !== null ||
                    formDrafts.calibrationSynced
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
    </HardwareCard>
  );
}
