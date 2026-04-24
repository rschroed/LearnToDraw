import { useMemo } from "react";

import { LatestCapturePanel } from "../../components/LatestCapturePanel";
import { StatusPill } from "../../components/StatusPill";
import type {
  CaptureMetadata,
  HardwareStatus,
  PlotterCalibration,
  PlotterDeviceSettings,
  PlotterWorkspace,
} from "../../types/hardware";
import { CameraPanel } from "./CameraPanel";
import { parseCameraStatus } from "./cameraPanelModel";
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
import { PlotterWorkspacePreview } from "./PlotterWorkspacePreview";
import { usePlotterFormDrafts } from "./usePlotterFormDrafts";

interface MachineSetupPanelProps {
  hardwareStatus: HardwareStatus;
  plotterCalibration: PlotterCalibration | null;
  plotterDevice: PlotterDeviceSettings | null;
  plotterWorkspace: PlotterWorkspace | null;
  latestCapture: CaptureMetadata | null;
  refreshing: boolean;
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
  capture: () => Promise<void>;
  setCameraDevice: (deviceId: string | null) => Promise<void>;
}

function renderWorkspaceInput({
  label,
  value,
  onChange,
  disabled,
  minimum,
  compact = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
  minimum: number;
  compact?: boolean;
}) {
  return (
    <label className={`field-group workspace-field${compact ? " workspace-field-compact" : ""}`}>
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

function formatBounds(
  bounds: {
    width_mm: number;
    height_mm: number;
  } | null,
) {
  if (!bounds) {
    return "unknown";
  }
  return `${formatMm(bounds.width_mm)} x ${formatMm(bounds.height_mm)}`;
}

function getSectionNotice(
  actionFeedback: ActionFeedback | null,
  matches: (action: Exclude<ActionName, null>) => boolean,
) {
  if (!actionFeedback) {
    return null;
  }
  if (!matches(actionFeedback.action)) {
    return null;
  }
  return actionFeedback;
}

export function MachineSetupPanel({
  hardwareStatus,
  plotterCalibration,
  plotterDevice,
  plotterWorkspace,
  latestCapture,
  refreshing,
  actionName,
  actionFeedback,
  walkHome,
  runPlotterTestAction,
  runDiagnosticPattern,
  setPlotterCalibration,
  setPlotterSafeBounds,
  setPlotterWorkspace,
  setPlotterPenHeights,
  capture,
  setCameraDevice,
}: MachineSetupPanelProps) {
  const plotterDetails = hardwareStatus.plotter.details;
  const parsedCameraStatus = useMemo(() => parseCameraStatus(hardwareStatus.camera), [hardwareStatus.camera]);
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

  const apiSurface =
    typeof plotterDetails.api_surface === "string" ? plotterDetails.api_surface : null;
  const plotApiSupported = plotterDetails.plot_api_supported === true;
  const manualApiSupported = plotterDetails.manual_api_supported === true;
  const lastTestAction =
    typeof plotterDetails.last_test_action === "string" ? plotterDetails.last_test_action : null;
  const lastTestActionStatus =
    typeof plotterDetails.last_test_action_status === "string"
      ? plotterDetails.last_test_action_status
      : null;
  const configSource =
    typeof plotterDetails.config_source === "string" ? plotterDetails.config_source : null;
  const motionScale =
    typeof plotterDetails.motion_scale === "number"
      ? plotterDetails.motion_scale
      : plotterCalibration?.motion_scale ?? null;
  const calibrationSource =
    plotterCalibration?.source ??
    (typeof plotterDetails.calibration_source === "string"
      ? plotterDetails.calibration_source
      : null);
  const plotterModelLabel = plotterDevice?.plotter_model?.label ?? "Model unavailable";
  const nominalPlotterBounds = plotterDevice?.nominal_plotter_bounds_mm ?? null;
  const workspaceBounds = plotterDevice?.plotter_bounds_mm ?? plotterWorkspace?.plotter_bounds_mm ?? null;
  const workspaceMetrics = getWorkspaceMetrics(formDrafts.workspaceValues);
  const workspaceValidation = getWorkspaceValidation(workspaceMetrics, workspaceBounds);
  const persistedWorkspaceValidationError =
    plotterWorkspace?.is_valid === false
      ? plotterWorkspace.validation_error ??
        "Saved paper setup no longer fits the current machine bounds."
      : null;
  const safeBoundsValidation = getSafeBoundsValidation(
    formDrafts.safeBoundsValues,
    nominalPlotterBounds,
  );
  const penHeightValidation = getPenHeightValidation(formDrafts.penPosUp, formDrafts.penPosDown);
  const calibrationValidation = getCalibrationValidation(formDrafts.nativeResFactor);
  const drawableAreaValid =
    workspaceMetrics.drawableWidthMm !== null &&
    workspaceMetrics.drawableHeightMm !== null &&
    workspaceMetrics.drawableWidthMm > 0 &&
    workspaceMetrics.drawableHeightMm > 0 &&
    workspaceValidation === null;
  const plotterUnavailable = !hardwareStatus.plotter.available || hardwareStatus.plotter.busy;
  const workspaceDisabled = actionName !== null || plotterUnavailable;
  const safeBoundsDisabled = actionName !== null || plotterUnavailable;
  const penHeightDisabled = actionName !== null || plotterUnavailable;
  const calibrationDisabled = actionName !== null || plotterUnavailable;
  const workspaceNeedsUpdate =
    persistedWorkspaceValidationError !== null ||
    workspaceValidation !== null ||
    !formDrafts.workspaceSynced ||
    !hardwareStatus.plotter.available;
  const paperSetupReady =
    !workspaceNeedsUpdate &&
    hardwareStatus.plotter.connected &&
    hardwareStatus.plotter.available;
  const paperNotice =
    hardwareStatus.plotter.error
      ? { tone: "error" as const, message: hardwareStatus.plotter.error }
      : getSectionNotice(
          actionFeedback,
          (action) => action === "plotter-workspace" || action === "plotter-safe-bounds",
        );
  const testActionsNotice =
    persistedWorkspaceValidationError !== null
      ? {
          tone: "error" as const,
          message: "Plotting is blocked until the paper setup fits the current machine bounds.",
        }
      : getSectionNotice(
          actionFeedback,
          (action) =>
            action === "plotter-walk-home" ||
            action.startsWith("plotter-test:") ||
            action.startsWith("plotter-pattern:"),
        );
  const diagnosticsNotice = getSectionNotice(
    actionFeedback,
    (action) => action === "plotter-pen-heights" || action === "plotter-calibration",
  );
  const quietMachineDetails = [
    { label: "Model", value: plotterModelLabel },
    { label: "Driver", value: hardwareStatus.plotter.driver },
    {
      label: "Connection",
      value: hardwareStatus.plotter.connected ? "Connected" : "Disconnected",
    },
    {
      label: "Availability",
      value: hardwareStatus.plotter.available ? "Ready" : "Offline",
    },
    { label: "Activity", value: hardwareStatus.plotter.busy ? "Busy" : "Idle" },
    lastTestAction
      ? {
          label: "Last action",
          value: `${formatLabel(lastTestAction)}${
            lastTestActionStatus ? ` · ${lastTestActionStatus}` : ""
          }`,
        }
      : null,
  ].filter(
    (item): item is { label: string; value: string } => item !== null,
  );
  const diagnosticItems = [
    apiSurface ? { label: "API surface", value: apiSurface } : null,
    { label: "Plot API support", value: plotApiSupported ? "Yes" : "No" },
    { label: "Manual API support", value: manualApiSupported ? "Yes" : "No" },
    motionScale !== null ? { label: "Motion scale", value: motionScale.toFixed(6) } : null,
    effectiveNativeResFactor
      ? { label: "Native res factor", value: effectiveNativeResFactor }
      : null,
    calibrationSource ? { label: "Calibration source", value: formatLabel(calibrationSource) } : null,
    configSource ? { label: "Config source", value: formatLabel(configSource) } : null,
    parsedCameraStatus.kind === "camerabridge" && parsedCameraStatus.details.base_url
      ? { label: "CameraBridge URL", value: parsedCameraStatus.details.base_url }
      : null,
    parsedCameraStatus.kind === "camerabridge" && parsedCameraStatus.details.session_owner_id
      ? { label: "Session owner", value: parsedCameraStatus.details.session_owner_id }
      : null,
    parsedCameraStatus.kind === "camerabridge" && parsedCameraStatus.details.active_device_id
      ? { label: "Active device id", value: parsedCameraStatus.details.active_device_id }
      : null,
    parsedCameraStatus.kind === "camerabridge" &&
    parsedCameraStatus.details.persisted_selected_device_id
      ? {
          label: "Persisted camera id",
          value: parsedCameraStatus.details.persisted_selected_device_id,
        }
      : null,
    parsedCameraStatus.kind === "camerabridge" &&
    parsedCameraStatus.details.effective_selected_device_id
      ? {
          label: "Effective camera id",
          value: parsedCameraStatus.details.effective_selected_device_id,
        }
      : null,
    parsedCameraStatus.kind === "camerabridge" && parsedCameraStatus.details.last_capture_id
      ? { label: "Last capture id", value: parsedCameraStatus.details.last_capture_id }
      : null,
    parsedCameraStatus.kind === "camerabridge" && parsedCameraStatus.details.resolution
      ? { label: "Camera resolution", value: parsedCameraStatus.details.resolution }
      : null,
  ].filter((item): item is { label: string; value: string } => item !== null);

  return (
    <section className="machine-setup-layout">
      <aside className="machine-secondary-rail">
        <section className="panel machine-test-panel">
          <header className="machine-quiet-header">
            <div>
              <h2>Plotter</h2>
              <p className="hardware-meta">
                {plotterModelLabel} · {hardwareStatus.plotter.connected ? "Connected" : "Disconnected"}
              </p>
            </div>
            <StatusPill
              label="State"
              value={hardwareStatus.plotter.available ? "Ready" : "Offline"}
              tone={hardwareStatus.plotter.available ? "ok" : "warn"}
            />
          </header>

          {testActionsNotice ? (
            <div className={`inline-notice inline-notice-${testActionsNotice.tone}`}>
              {testActionsNotice.message}
            </div>
          ) : null}

          <div className="machine-action-group">
            <p className="machine-inline-label">Actions</p>
            <div className="actions machine-quiet-actions">
              <button
                type="button"
                className="button-secondary button-compact"
                onClick={() => void walkHome()}
                disabled={actionName !== null || plotterUnavailable}
              >
                Walk home
              </button>
              <button
                type="button"
                className="button-secondary button-compact"
                onClick={() => void runPlotterTestAction("align")}
                disabled={actionName !== null || plotterUnavailable}
              >
                Disengage motors
              </button>
              <button
                type="button"
                className="button-secondary button-compact"
                onClick={() => void runPlotterTestAction("raise_pen")}
                disabled={actionName !== null || plotterUnavailable}
              >
                Raise pen
              </button>
              <button
                type="button"
                className="button-secondary button-compact"
                onClick={() => void runPlotterTestAction("lower_pen")}
                disabled={actionName !== null || plotterUnavailable}
              >
                Lower pen
              </button>
              <button
                type="button"
                className="button-secondary button-compact"
                onClick={() => void runPlotterTestAction("cycle_pen")}
                disabled={actionName !== null || plotterUnavailable}
              >
                Cycle pen
              </button>
            </div>
          </div>

          {isAxiDraw ? (
            <div className="machine-action-group">
              <p className="machine-inline-label">Patterns</p>
              <div className="actions machine-quiet-actions">
                <button
                  type="button"
                  className="button-secondary button-compact"
                  onClick={() => void runDiagnosticPattern("tiny-square")}
                  disabled={actionName !== null || plotterUnavailable || persistedWorkspaceValidationError !== null}
                >
                  Tiny square
                </button>
                <button
                  type="button"
                  className="button-secondary button-compact"
                  onClick={() => void runDiagnosticPattern("dash-row")}
                  disabled={actionName !== null || plotterUnavailable || persistedWorkspaceValidationError !== null}
                >
                  Dash row
                </button>
                <button
                  type="button"
                  className="button-secondary button-compact"
                  onClick={() => void runDiagnosticPattern("double-box")}
                  disabled={actionName !== null || plotterUnavailable || persistedWorkspaceValidationError !== null}
                >
                  Double box
                </button>
              </div>
            </div>
          ) : null}

          <details className="machine-disclosure machine-embedded-disclosure">
            <summary>Machine details</summary>
            <div className="machine-disclosure-body">
              <dl className="machine-detail-list">
                {quietMachineDetails.map((item) => (
                  <div key={item.label} className="machine-detail-row">
                    <dt>{item.label}</dt>
                    <dd>{item.value}</dd>
                  </div>
                ))}
              </dl>
            </div>
          </details>
        </section>

        <CameraPanel
          cameraStatus={hardwareStatus.camera}
          actionName={actionName}
          actionFeedback={actionFeedback}
          capture={capture}
          setCameraDevice={setCameraDevice}
        />

        <LatestCapturePanel capture={latestCapture} refreshing={refreshing} />

        <details className="panel machine-disclosure">
          <summary>Diagnostics</summary>
          <div className="machine-disclosure-body">
            {diagnosticsNotice ? (
              <div className={`inline-notice inline-notice-${diagnosticsNotice.tone}`}>
                {diagnosticsNotice.message}
              </div>
            ) : null}

            <dl className="machine-detail-list machine-detail-list-diagnostics">
              {diagnosticItems.map((item) => (
                <div key={item.label} className="machine-detail-row">
                  <dt>{item.label}</dt>
                  <dd>{item.value}</dd>
                </div>
              ))}
              {penTuning
                ? Object.entries(penTuning)
                    .filter(([key]) => key !== "pen_pos_up" && key !== "pen_pos_down")
                    .map(([key, value]) => (
                      <div key={key} className="machine-detail-row">
                        <dt>{formatLabel(key)}</dt>
                        <dd>{String(value)}</dd>
                      </div>
                    ))
                : null}
            </dl>

            {isAxiDraw ? (
              <div className="machine-diagnostics-grid">
                <section className="machine-diagnostic-block">
                  <h3>Pen heights</h3>
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
                    <div className="inline-notice inline-notice-error">{penHeightValidation}</div>
                  ) : null}
                </section>

                <section className="machine-diagnostic-block">
                  <h3>Calibration</h3>
                  <div className="pen-height-grid machine-calibration-grid">
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
                    <div className="inline-notice inline-notice-error">{calibrationValidation}</div>
                  ) : null}
                  {calibrationSource === "env_override" ? (
                    <div className="inline-notice inline-notice-info">
                      An environment override is active. Saved calibration will persist, but
                      it will not become effective until the override is removed and the backend
                      is restarted.
                    </div>
                  ) : null}
                </section>
              </div>
            ) : null}
          </div>
        </details>
      </aside>

      <section className="panel machine-paper-panel">
        <header className="machine-paper-header">
          <div className="machine-paper-header-copy">
            <p className="eyebrow">Machine</p>
            <h2>Paper setup</h2>
            <p className="machine-paper-meta">
              Bounds: {formatBounds(workspaceBounds)}
            </p>
          </div>

          <div className="machine-paper-header-side">
            <StatusPill
              label="Setup"
              value={paperSetupReady ? "Ready for plotting" : "Needs update"}
              tone={paperSetupReady ? "ok" : "warn"}
            />
            {isAxiDraw ? (
              <div className="machine-safe-bounds">
                <p className="machine-inline-label">Safe bounds</p>
                <div className="machine-safe-bounds-grid">
                  {renderWorkspaceInput({
                    label: "Width",
                    value: formDrafts.safeBoundsValues.widthMm,
                    onChange: (widthMm) =>
                      formDrafts.setSafeBoundsDraft({
                        ...formDrafts.safeBoundsValues,
                        widthMm,
                      }),
                    disabled: safeBoundsDisabled,
                    minimum: 1,
                    compact: true,
                  })}
                  {renderWorkspaceInput({
                    label: "Height",
                    value: formDrafts.safeBoundsValues.heightMm,
                    onChange: (heightMm) =>
                      formDrafts.setSafeBoundsDraft({
                        ...formDrafts.safeBoundsValues,
                        heightMm,
                      }),
                    disabled: safeBoundsDisabled,
                    minimum: 1,
                    compact: true,
                  })}
                </div>
                <div className="machine-inline-actions">
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
                    Save
                  </button>
                  <button
                    type="button"
                    className="button-ghost button-compact"
                    onClick={() => {
                      formDrafts.clearPendingSafeBoundsApply();
                      void setPlotterSafeBounds({ width_mm: null, height_mm: null });
                    }}
                    disabled={
                      safeBoundsDisabled ||
                      plotterDevice?.plotter_bounds_source === "default_clearance"
                    }
                  >
                    Reset
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        </header>

        {paperNotice ? (
          <div className={`inline-notice inline-notice-${paperNotice.tone}`}>{paperNotice.message}</div>
        ) : null}
        {safeBoundsValidation ? (
          <div className="inline-notice inline-notice-error machine-inline-notice">
            {safeBoundsValidation}
          </div>
        ) : null}
        {persistedWorkspaceValidationError ? (
          <div className="inline-notice inline-notice-error machine-inline-notice">
            Saved paper setup is invalid for the current machine bounds:{" "}
            {persistedWorkspaceValidationError}
          </div>
        ) : null}
        {workspaceValidation ? (
          <div className="inline-notice inline-notice-error machine-inline-notice">
            {workspaceValidation}
          </div>
        ) : null}

        <div className="machine-paper-preview-wrap">
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

        <div className="machine-paper-status-strip">
          <span>Drawable area</span>
          <strong>
            {formatMm(workspaceMetrics.drawableWidthMm)} x {formatMm(workspaceMetrics.drawableHeightMm)}
          </strong>
        </div>

        <div className="machine-paper-form">
          <div className="machine-paper-group">
            <div className="workspace-form-label">Page size</div>
            <div className="workspace-grid workspace-grid-two">
              {renderWorkspaceInput({
                label: "Width",
                value: formDrafts.workspaceValues.pageWidthMm,
                onChange: (pageWidthMm) =>
                  formDrafts.setWorkspaceDraft({
                    ...formDrafts.workspaceValues,
                    pageWidthMm,
                  }),
                disabled: workspaceDisabled,
                minimum: 1,
              })}
              {renderWorkspaceInput({
                label: "Height",
                value: formDrafts.workspaceValues.pageHeightMm,
                onChange: (pageHeightMm) =>
                  formDrafts.setWorkspaceDraft({
                    ...formDrafts.workspaceValues,
                    pageHeightMm,
                  }),
                disabled: workspaceDisabled,
                minimum: 1,
              })}
            </div>
          </div>

          <div className="machine-paper-group">
            <div className="workspace-form-label">Margins</div>
            <div className="workspace-grid workspace-grid-margins">
              {renderWorkspaceInput({
                label: "Left",
                value: formDrafts.workspaceValues.marginLeftMm,
                onChange: (marginLeftMm) =>
                  formDrafts.setWorkspaceDraft({
                    ...formDrafts.workspaceValues,
                    marginLeftMm,
                  }),
                disabled: workspaceDisabled,
                minimum: 0,
              })}
              {renderWorkspaceInput({
                label: "Top",
                value: formDrafts.workspaceValues.marginTopMm,
                onChange: (marginTopMm) =>
                  formDrafts.setWorkspaceDraft({
                    ...formDrafts.workspaceValues,
                    marginTopMm,
                  }),
                disabled: workspaceDisabled,
                minimum: 0,
              })}
              {renderWorkspaceInput({
                label: "Right",
                value: formDrafts.workspaceValues.marginRightMm,
                onChange: (marginRightMm) =>
                  formDrafts.setWorkspaceDraft({
                    ...formDrafts.workspaceValues,
                    marginRightMm,
                  }),
                disabled: workspaceDisabled,
                minimum: 0,
              })}
              {renderWorkspaceInput({
                label: "Bottom",
                value: formDrafts.workspaceValues.marginBottomMm,
                onChange: (marginBottomMm) =>
                  formDrafts.setWorkspaceDraft({
                    ...formDrafts.workspaceValues,
                    marginBottomMm,
                  }),
                disabled: workspaceDisabled,
                minimum: 0,
              })}
            </div>
          </div>
        </div>

        <div className="section-actions workspace-actions">
          <button
            type="button"
            className="button-primary"
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
      </section>
    </section>
  );
}
