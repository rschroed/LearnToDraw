import { useMemo, useState } from "react";

import { StatusPill } from "../../components/StatusPill";
import { PlotWorkflowPanel } from "../plot-workflow/PlotWorkflowPanel";
import { usePlotWorkflow } from "../plot-workflow/usePlotWorkflow";
import { HardwareStartupState } from "./HardwareStartupState";
import { MachineSetupPanel } from "./MachineSetupPanel";
import { useHardwareDashboard } from "./useHardwareDashboard";

type DashboardTab = "workflow" | "machine" | "history";

function getGlobalBlocker({
  plotterAvailable,
  cameraAvailable,
  workspaceError,
}: {
  plotterAvailable: boolean;
  cameraAvailable: boolean;
  workspaceError: string | null;
}) {
  if (workspaceError) {
    return `Paper setup needs attention before plotting: ${workspaceError}`;
  }
  if (!plotterAvailable) {
    return "Plotter unavailable. Review the Machine tab before starting the plotter/camera loop.";
  }
  if (!cameraAvailable) {
    return "Camera unavailable. Review the Machine tab before starting the plotter/camera loop.";
  }
  return null;
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
    setPlotterSafeBounds,
    setPlotterWorkspace,
    setPlotterPenHeights,
    capture,
    setCameraDevice,
  } = useHardwareDashboard();
  const plotWorkflow = usePlotWorkflow();
  const [activeTab, setActiveTab] = useState<DashboardTab>("workflow");

  const globalBlocker = useMemo(
    () =>
      hardwareStatus
        ? getGlobalBlocker({
            plotterAvailable: hardwareStatus.plotter.available,
            cameraAvailable: hardwareStatus.camera.available,
            workspaceError:
              plotterWorkspace?.is_valid === false ? plotterWorkspace.validation_error : null,
          })
        : null,
    [hardwareStatus, plotterWorkspace],
  );

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
    <main className="app-shell">
      <header className="app-topbar">
        <div className="topbar-copy">
          <p className="eyebrow">LearnToDraw</p>
          <h1>Workflow-first local operator</h1>
          <p className="topbar-subtitle">
            Stage an artwork, run the plotter/camera loop, and inspect the saved result
            without moving hardware control out of the backend.
          </p>
        </div>

        <div className="topbar-side">
          <div className="readiness-bar">
            <StatusPill label="Backend" value={refreshing ? "refreshing" : "online"} />
            <StatusPill
              label="Plotter"
              value={hardwareStatus.plotter.available ? "ready" : "offline"}
              tone={hardwareStatus.plotter.available ? "ok" : "warn"}
            />
            <StatusPill
              label="Camera"
              value={hardwareStatus.camera.available ? "ready" : "offline"}
              tone={hardwareStatus.camera.available ? "ok" : "warn"}
            />
          </div>
          <button
            type="button"
            className="button-secondary"
            onClick={() => void refresh()}
          >
            Refresh
          </button>
        </div>
      </header>

      <nav className="app-tabs" aria-label="Primary views">
        {(["workflow", "machine", "history"] as DashboardTab[]).map((tab) => (
          <button
            key={tab}
            type="button"
            className={`app-tab${activeTab === tab ? " app-tab-active" : ""}`}
            aria-pressed={activeTab === tab}
            onClick={() => setActiveTab(tab)}
          >
            {tab[0].toUpperCase()}
            {tab.slice(1)}
          </button>
        ))}
      </nav>

      {error ? <div className="banner">{error}</div> : null}
      {globalBlocker ? <div className="global-blocker">{globalBlocker}</div> : null}

      {activeTab === "workflow" ? (
        <PlotWorkflowPanel
          controller={plotWorkflow}
          hardwareStatus={hardwareStatus}
          plotterWorkspace={plotterWorkspace}
          latestCapture={latestCapture}
        />
      ) : null}

      {activeTab === "machine" ? (
        <MachineSetupPanel
          hardwareStatus={hardwareStatus}
          plotterCalibration={plotterCalibration}
          plotterDevice={plotterDevice}
          plotterWorkspace={plotterWorkspace}
          latestCapture={latestCapture}
          refreshing={refreshing}
          actionName={actionName}
          actionFeedback={actionFeedback}
          walkHome={walkHome}
          runPlotterTestAction={runPlotterTestAction}
          runDiagnosticPattern={runDiagnosticPattern}
          setPlotterCalibration={setPlotterCalibration}
          setPlotterSafeBounds={setPlotterSafeBounds}
          setPlotterWorkspace={setPlotterWorkspace}
          setPlotterPenHeights={setPlotterPenHeights}
          capture={capture}
          setCameraDevice={setCameraDevice}
        />
      ) : null}

      {activeTab === "history" ? (
        <PlotWorkflowPanel
          controller={plotWorkflow}
          hardwareStatus={hardwareStatus}
          plotterWorkspace={plotterWorkspace}
          latestCapture={latestCapture}
          mode="history"
        />
      ) : null}
    </main>
  );
}
