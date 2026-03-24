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
    setPlotterSafeBounds,
    setPlotterWorkspace,
    setPlotterPenHeights,
    capture,
    setCameraDevice,
  } = useHardwareDashboard();

  if (loading && !hardwareStatus) {
    return (
      <HardwareStartupState
        title="Booting local hardware control."
        message="Checking backend status."
      />
    );
  }

  if (!hardwareStatus) {
    return (
      <HardwareStartupState
        title="Local backend unavailable."
        message="Start the LearnToDraw API locally and retry. CameraBridge guidance will appear once the backend is reachable."
        error={error}
      >
        <button
          type="button"
          className="button-secondary"
          onClick={() => void refresh()}
        >
          Retry
        </button>
      </HardwareStartupState>
    );
  }

  return (
    <main className="page-shell">
      <section className="hero">
        <div className="hero-card">
          <h1>LearnToDraw local control panel</h1>
          <p>
            Backend-owned hardware control for local plotting and capture. The
            UI polls device state, triggers narrow backend actions, and previews
            the latest saved capture.
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
          setCameraDevice={setCameraDevice}
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
