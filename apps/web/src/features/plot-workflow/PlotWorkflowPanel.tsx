import type { ChangeEvent } from "react";

import type { HardwareStatus, PlotterWorkspace } from "../../types/hardware";
import type { PlotRun, PlotStageState } from "../../types/plotting";

import { usePlotWorkflow } from "./usePlotWorkflow";

interface PlotWorkflowPanelProps {
  hardwareStatus: HardwareStatus;
  plotterWorkspace: PlotterWorkspace | null;
}

function getStageLabel(run: PlotRun | null) {
  if (!run) {
    return "No active run";
  }
  if (run.status === "plotting") {
    return "Plotting";
  }
  if (run.status === "capturing") {
    return "Capturing";
  }
  if (run.status === "completed") {
    return "Completed";
  }
  if (run.status === "failed") {
    return "Failed";
  }
  return "Preparing";
}

function getRunStatusTone(status: PlotRun["status"] | "idle") {
  if (status === "completed") {
    return "ok";
  }
  if (status === "pending" || status === "plotting" || status === "capturing") {
    return "warn";
  }
  if (status === "failed") {
    return "warn";
  }
  return "ok";
}

function formatStageState(stageState: PlotStageState) {
  if (stageState.status === "in_progress") {
    return "in progress";
  }
  return stageState.status;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function formatPhysicalSize(width: unknown, height: unknown) {
  if (typeof width !== "number" || typeof height !== "number") {
    return null;
  }
  return `${width.toFixed(1).replace(/\.0$/, "")} × ${height
    .toFixed(1)
    .replace(/\.0$/, "")} mm`;
}

export function PlotWorkflowPanel({
  hardwareStatus,
  plotterWorkspace,
}: PlotWorkflowPanelProps) {
  const {
    selectedAsset,
    selectionSource,
    latestRun,
    recentRuns,
    loading,
    refreshing,
    busyAction,
    activeRun,
    sizingMode,
    error,
    notice,
    createBuiltInPattern,
    uploadSvg,
    startRun,
    setSizingMode,
  } = usePlotWorkflow();
  const fitWithinDrawableAreaSupported = hardwareStatus.plotter.driver !== "axidraw-pyapi";
  const fitWithinDrawableAreaSelectedAndUnsupported =
    sizingMode === "fit_to_draw_area" && !fitWithinDrawableAreaSupported;

  const startDisabled =
    !selectedAsset ||
    activeRun ||
    busyAction === "start" ||
    fitWithinDrawableAreaSelectedAndUnsupported ||
    !hardwareStatus.plotter.available ||
    !hardwareStatus.camera.available ||
    hardwareStatus.plotter.busy ||
    hardwareStatus.camera.busy;

  const latestStatus = latestRun?.status ?? "idle";
  const latestRunUsesDifferentSource =
    selectionSource === "manual" &&
    selectedAsset !== null &&
    latestRun !== null &&
    latestRun.asset.id !== selectedAsset.id;
  const uploadedNativeSizingWarning =
    selectedAsset?.kind === "uploaded_svg" && sizingMode === "native";
  const preparation =
    latestRun && isRecord(latestRun.plotter_run_details.preparation)
      ? latestRun.plotter_run_details.preparation
      : null;
  const sourceSize = preparation
    ? formatPhysicalSize(preparation.source_width, preparation.source_height)
    : null;
  const preparedSize = preparation
    ? formatPhysicalSize(preparation.prepared_width_mm, preparation.prepared_height_mm)
    : null;
  const sourceUnits =
    preparation && typeof preparation.source_units === "string"
      ? preparation.source_units
      : null;
  const unitsInferred = preparation?.units_inferred === true;
  const drawableAreaSummary = plotterWorkspace
    ? `${plotterWorkspace.drawable_area_mm.width_mm.toFixed(1).replace(/\.0$/, "")} × ${plotterWorkspace.drawable_area_mm.height_mm
        .toFixed(1)
        .replace(/\.0$/, "")} mm`
    : null;

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) {
      void uploadSvg(file);
      event.target.value = "";
    }
  }

  return (
    <>
      <section className="workflow-grid">
        <section className="workflow-panel">
          <header className="workflow-header">
            <div>
              <h2>Plot Workflow</h2>
              <div className="hardware-meta">
                Prepare a local SVG, run a local plot, and compare planned
                versus captured output.
              </div>
            </div>
            <span
              className={`status-pill status-pill-${getRunStatusTone(latestStatus)}`}
            >
              <span className="status-pill-dot" />
              Run state: {latestRun ? getStageLabel(latestRun) : "idle"}
            </span>
          </header>

          {error ? <div className="banner">{error}</div> : null}
          {notice ? (
            <div className={`inline-notice inline-notice-${notice.tone}`}>
              {notice.message}
            </div>
          ) : null}

          <div className="workflow-actions">
            <label className="button-secondary file-button">
              {busyAction === "upload" ? "Uploading..." : "Upload SVG"}
              <input
                type="file"
                accept=".svg,image/svg+xml"
                onChange={onFileChange}
                disabled={busyAction !== null}
              />
            </label>
            <button
              type="button"
              className="button-secondary"
              onClick={() => void createBuiltInPattern()}
              disabled={busyAction !== null}
            >
              {busyAction === "pattern" ? "Building..." : "Load test-grid"}
            </button>
            <button
              type="button"
              className="button-primary"
              onClick={() => void startRun()}
              disabled={startDisabled}
            >
              {busyAction === "start" ? "Starting..." : "Start plot run"}
            </button>
          </div>

          <div className="workflow-settings">
            <label className="field-group workflow-select">
              <span>Plot sizing</span>
              <select
                value={sizingMode}
                onChange={(event) => setSizingMode(event.target.value as typeof sizingMode)}
                disabled={busyAction !== null || activeRun}
              >
                <option value="native">Use authored size</option>
                <option
                  value="fit_to_draw_area"
                  disabled={!fitWithinDrawableAreaSupported}
                >
                  Fit within drawable area
                </option>
              </select>
            </label>
            {fitWithinDrawableAreaSelectedAndUnsupported ? (
              <div className="inline-notice inline-notice-error">
                Fit within drawable area is temporarily disabled for real AxiDraw plotting
                because it can exceed safe machine bounds. Use authored size only for SVGs
                with explicit physical units.
              </div>
            ) : null}
            {uploadedNativeSizingWarning ? (
              <div className="inline-notice inline-notice-info">
                Use authored size only works for uploaded SVGs that declare physical dimensions
                such as mm, cm, or in. Unitless uploads should use Fit within drawable area.
              </div>
            ) : null}
            <p className="footer-note">
              Current drawable area: {drawableAreaSummary ?? "unknown"}. Built-in diagnostic
              patterns use explicit physical SVG dimensions in the backend.
            </p>
          </div>

          <div className="selection-grid">
            <div className="selection-card">
              <h3>Selected source</h3>
              {selectedAsset ? (
                <>
                  <p className="selection-meta">
                    {selectedAsset.kind === "built_in_pattern"
                      ? `Built-in pattern${selectedAsset.pattern_id ? ` · ${selectedAsset.pattern_id}` : ""}`
                      : "Uploaded SVG"}
                  </p>
                  <div className="preview-frame preview-frame-small">
                    <img
                      src={selectedAsset.public_url}
                      alt={`Selected plot asset ${selectedAsset.name}`}
                    />
                  </div>
                  <p className="footer-note">
                    Staged source: {selectedAsset.name} · saved at{" "}
                    {new Date(selectedAsset.timestamp).toLocaleString()}
                  </p>
                  {latestRunUsesDifferentSource ? (
                    <p className="footer-note">
                      Latest run used a different source: {latestRun.asset.name}.
                    </p>
                  ) : null}
                </>
              ) : (
                <div className="empty-state">
                  Choose a built-in pattern or upload a local SVG to preview it
                  and stage it for plotting.
                </div>
              )}
            </div>

            <div className="selection-card">
              <h3>Run stages</h3>
              {latestRun ? (
                <div className="stage-list">
                  {(
                    Object.entries(latestRun.stage_states) as Array<
                      [keyof PlotRun["stage_states"], PlotStageState]
                    >
                  ).map(([stage, stageState]) => (
                    <div
                      key={stage}
                      className={`stage-item stage-item-${stageState.status}`}
                    >
                      <strong>{stage}</strong>
                      <span>{formatStageState(stageState)}</span>
                      <span>{stageState.message ?? "Waiting"}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-state">
                  Start a plot run to see prepare, plot, and capture progression.
                </div>
              )}
              <p className="footer-note">
                {refreshing
                  ? "Refreshing run state..."
                  : loading
                    ? "Loading plot workflow..."
                    : "Run state is polled over local HTTP."}
              </p>
              {preparation ? (
                <div className="workflow-sizing-summary">
                  <p className="footer-note">
                    Source size: {sourceSize ?? "unknown"}
                    {sourceUnits ? ` · units ${sourceUnits}` : ""}
                    {unitsInferred ? " · inferred for preparation" : ""}
                  </p>
                  <p className="footer-note">
                    Prepared size: {preparedSize ?? "unknown"} · mode {latestRun?.sizing_mode}
                  </p>
                </div>
              ) : null}
            </div>
          </div>
        </section>

        <section className="comparison-panel">
          <header className="workflow-header">
            <div>
              <h2>Planned vs captured</h2>
              <div className="hardware-meta">
                Latest run detail with side-by-side artifact comparison.
              </div>
            </div>
            {latestRun ? (
              <span
                className={`status-pill status-pill-${getRunStatusTone(
                  latestRun.status,
                )}`}
              >
                <span className="status-pill-dot" />
                {latestRun.status}
              </span>
            ) : null}
          </header>

          <div className="comparison-grid">
            <div>
              <h3>Planned output</h3>
              <div className="preview-frame">
                {latestRun ? (
                  <img
                    src={latestRun.asset.public_url}
                    alt={`Planned output for ${latestRun.asset.name}`}
                  />
                ) : (
                  <div className="empty-state">
                    Your latest run preview will appear here.
                  </div>
                )}
              </div>
            </div>

            <div>
              <h3>Captured output</h3>
              <div className="preview-frame">
                {latestRun?.capture ? (
                  <img
                    src={latestRun.capture.public_url}
                    alt={`Captured output for run ${latestRun.id}`}
                  />
                ) : (
                  <div className="empty-state">
                    {latestRun?.status === "failed"
                      ? latestRun.error ?? "Run failed before capture completed."
                      : latestRun?.capture_mode === "skip"
                        ? "Capture was skipped for this diagnostic run."
                        : "Capture will appear here once the run reaches the camera stage."}
                  </div>
                )}
              </div>
            </div>
          </div>

          {latestRun ? (
            <p className="footer-note">
              Run {latestRun.id.slice(0, 8)} · {latestRun.purpose}
              {" · "}asset {latestRun.asset.name}
              {latestRun.capture
                ? ` · capture ${latestRun.capture.id.slice(0, 8)}`
                : latestRun.capture_mode === "skip"
                  ? " · capture skipped"
                : ""}
            </p>
          ) : null}
        </section>
      </section>

      <section className="runs-panel">
        <header className="workflow-header">
          <div>
            <h2>Recent runs</h2>
            <div className="hardware-meta">
              Compact local run history for debugging and quick inspection.
            </div>
          </div>
        </header>

        {recentRuns.length > 0 ? (
          <ul className="run-list">
            {recentRuns.map((run) => (
              <li key={run.id} className="run-list-item">
                <div>
                  <strong>{run.asset_name}</strong>
                  <div className="hardware-meta">
                    {run.asset_kind === "built_in_pattern"
                      ? "built-in pattern"
                      : "uploaded svg"}
                    {` · ${run.purpose}`}
                  </div>
                </div>
                <div className="run-list-meta">
                  <span
                    className={`status-pill status-pill-${getRunStatusTone(
                      run.status,
                    )}`}
                  >
                    <span className="status-pill-dot" />
                    {run.status}
                  </span>
                  <span>{run.id.slice(0, 8)}</span>
                  <span>{new Date(run.created_at).toLocaleString()}</span>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <div className="empty-state">
            No plot runs yet. Create the built-in test pattern or upload an SVG
            to start the first run.
          </div>
        )}
      </section>
    </>
  );
}
