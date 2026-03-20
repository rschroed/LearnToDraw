import { LatestCapturePanel } from "../../components/LatestCapturePanel";
import { PlotWorkflowPanel } from "../plot-workflow/PlotWorkflowPanel";
import { CameraPanel } from "./CameraPanel";
import { HardwareStartupState } from "./HardwareStartupState";
import { PlotterPanel } from "./PlotterPanel";
import { useHardwareDashboard } from "./useHardwareDashboard";


export function HardwareDashboard() {
  const {
    hardwareStatus,
    latestCapture,
    loading,
    refreshing,
    helperStatus,
    helperConnectionState,
    helperActionName,
    actionName,
    actionFeedback,
    error,
    refresh,
    openHelper,
    startBackend,
    restartBackend,
    plotterCalibration,
    plotterDevice,
    plotterWorkspace,
    walkHome,
    runPlotterTestAction,
    runDiagnosticPattern,
    setPlotterCalibration,
    setPlotterSafeBounds,
    setPlotterWorkspace,
    setPlotterPenHeights,
    capture,
  } = useHardwareDashboard();

  const helperStartupTitle =
    helperActionName !== null ||
    helperStatus?.state === "starting" ||
    helperStatus?.backend_health === "starting"
      ? "Starting local camera backend."
      : helperConnectionState === "missing"
        ? "Local helper not running."
        : helperStatus?.state === "failed"
          ? "Camera backend failed to start."
          : helperStatus?.state === "stopped"
            ? "Camera backend stopped."
            : "Hardware status unavailable.";
  const helperStartupMessage =
    helperActionName !== null ||
    helperStatus?.state === "starting" ||
    helperStatus?.backend_health === "starting"
      ? "Waiting for the helper-managed backend to come online."
      : helperConnectionState === "missing"
        ? "Open the LearnToDraw helper to bring localhost control online, then retry if needed."
        : helperStatus?.state === "failed"
          ? helperStatus.last_error ?? "The local helper could not start the camera backend."
          : helperStatus?.state === "stopped"
            ? "The local helper is reachable, but the camera backend is not running."
            : "Check that the backend is running on localhost and try again.";

  if (loading && !hardwareStatus && helperConnectionState === "unknown" && !helperStatus) {
    return (
      <HardwareStartupState
        title="Booting local hardware control."
        message="Checking backend and helper status."
      />
    );
  }

  if (!hardwareStatus) {
    return (
      <HardwareStartupState
        title={helperStartupTitle}
        message={helperStartupMessage}
        error={error}
      >
        {helperConnectionState === "missing" ? (
          <>
            <button
              type="button"
              className="button-primary"
              onClick={() => openHelper()}
            >
              Open helper
            </button>
            <button
              type="button"
              className="button-secondary"
              onClick={() => void refresh()}
            >
              Retry
            </button>
          </>
        ) : null}
        {helperStatus?.state === "stopped" ? (
          <button
            type="button"
            className="button-primary"
            disabled={helperActionName !== null}
            onClick={() => void startBackend()}
          >
            {helperActionName === "start" ? "Starting..." : "Start backend"}
          </button>
        ) : null}
        {helperStatus?.state === "failed" ? (
          <button
            type="button"
            className="button-primary"
            disabled={helperActionName !== null}
            onClick={() => void restartBackend()}
          >
            {helperActionName === "restart" ? "Restarting..." : "Restart backend"}
          </button>
        ) : null}
      </HardwareStartupState>
    );
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
      {helperConnectionState === "missing" ? (
        <div className="banner" style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <span>
            Backend is running, but the local helper is not. Dashboard start and
            restart controls are unavailable until the helper is open.
          </span>
          <button
            type="button"
            className="button-secondary"
            onClick={() => openHelper()}
          >
            Open helper
          </button>
          <button
            type="button"
            className="button-secondary"
            onClick={() => void refresh()}
          >
            Retry
          </button>
        </div>
      ) : null}

      <section className="status-grid">
        <PlotterPanel
          hardwareStatus={hardwareStatus}
          plotterCalibration={plotterCalibration}
          plotterDevice={plotterDevice}
          plotterWorkspace={plotterWorkspace}
          actionName={actionName}
          actionFeedback={actionFeedback}
          walkHome={walkHome}
          runPlotterTestAction={runPlotterTestAction}
          runDiagnosticPattern={runDiagnosticPattern}
          setPlotterCalibration={setPlotterCalibration}
          setPlotterSafeBounds={setPlotterSafeBounds}
          setPlotterWorkspace={setPlotterWorkspace}
          setPlotterPenHeights={setPlotterPenHeights}
        />

        <CameraPanel
          cameraStatus={hardwareStatus.camera}
          actionName={actionName}
          actionFeedback={actionFeedback}
          capture={capture}
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
