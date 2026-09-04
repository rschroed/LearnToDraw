import { StatusPill } from "../../components/StatusPill";
import { HardwareStartupState } from "../hardware/HardwareStartupState";
import { MachineSetupPanel } from "../hardware/MachineSetupPanel";
import { useHardwareDashboard } from "../hardware/useHardwareDashboard";
import { PlotWorkflowPanel } from "../plot-workflow/PlotWorkflowPanel";
import { usePlotWorkflow } from "../plot-workflow/usePlotWorkflow";

export function ControlsPage() {
  const hardware = useHardwareDashboard();
  const workflow = usePlotWorkflow();

  if (hardware.loading && !hardware.hardwareStatus) {
    return <HardwareStartupState title="Opening Controls." message="Checking local hardware." />;
  }

  if (!hardware.hardwareStatus) {
    return (
      <HardwareStartupState
        title="Local backend unavailable."
        message="Start the LearnToDraw API locally and retry."
        error={hardware.error}
      >
        <button type="button" className="button-secondary" onClick={() => void hardware.refresh()}>
          Retry
        </button>
      </HardwareStartupState>
    );
  }

  return (
    <main className="controls-page">
      <header className="controls-heading">
        <div>
          <p className="eyebrow">Controls</p>
          <h1>Machine setup and manual work</h1>
          <p>Operational tools stay here, separate from the creative session.</p>
        </div>
        <div className="readiness-bar">
          <StatusPill label="Plotter" value={hardware.hardwareStatus.plotter.available ? "ready" : "attention"} tone={hardware.hardwareStatus.plotter.available ? "ok" : "warn"} />
          <StatusPill label="Camera" value={hardware.hardwareStatus.camera.available ? "ready" : "attention"} tone={hardware.hardwareStatus.camera.available ? "ok" : "warn"} />
          <button type="button" className="button-secondary" onClick={() => void hardware.refresh()}>
            {hardware.refreshing ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </header>

      {hardware.error ? <div className="banner" role="alert">{hardware.error}</div> : null}

      <section className="controls-section">
        <div className="controls-section-heading">
          <p className="eyebrow">Setup and diagnostics</p>
          <h2>Paper, plotter, and camera</h2>
        </div>
        <MachineSetupPanel
          hardwareStatus={hardware.hardwareStatus}
          plotterCalibration={hardware.plotterCalibration}
          plotterDevice={hardware.plotterDevice}
          plotterWorkspace={hardware.plotterWorkspace}
          latestCapture={hardware.latestCapture}
          refreshing={hardware.refreshing}
          actionName={hardware.actionName}
          actionFeedback={hardware.actionFeedback}
          walkHome={hardware.walkHome}
          runPlotterTestAction={hardware.runPlotterTestAction}
          runDiagnosticPattern={hardware.runDiagnosticPattern}
          setPlotterCalibration={hardware.setPlotterCalibration}
          setPlotterSafeBounds={hardware.setPlotterSafeBounds}
          setPlotterWorkspace={hardware.setPlotterWorkspace}
          setPlotterPenHeights={hardware.setPlotterPenHeights}
          capture={hardware.capture}
          setCameraDevice={hardware.setCameraDevice}
        />
      </section>

      <section className="controls-section controls-manual-workflow">
        <div className="controls-section-heading">
          <p className="eyebrow">Manual plotting</p>
          <h2>Upload, plot, capture, and inspect an SVG</h2>
          <p>This retains the original explicit operator workflow, including manual registration.</p>
        </div>
        <PlotWorkflowPanel
          controller={workflow}
          hardwareStatus={hardware.hardwareStatus}
          plotterWorkspace={hardware.plotterWorkspace}
          latestCapture={hardware.latestCapture}
        />
      </section>
    </main>
  );
}
