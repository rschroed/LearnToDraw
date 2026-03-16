import { useEffect, useState } from "react";

import { HardwareCard } from "../../components/HardwareCard";
import { LatestCapturePanel } from "../../components/LatestCapturePanel";
import { PlotWorkflowPanel } from "../plot-workflow/PlotWorkflowPanel";

import { useHardwareDashboard } from "./useHardwareDashboard";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function formatLabel(value: string) {
  return value.replace(/_/g, " ");
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
    returnToOrigin,
    runPlotterTestAction,
    runDiagnosticPattern,
    setPlotterPenHeights,
    capture,
  } = useHardwareDashboard();
  const [penPosUp, setPenPosUp] = useState("60");
  const [penPosDown, setPenPosDown] = useState("30");

  useEffect(() => {
    const plotterDetails = hardwareStatus?.plotter.details;
    const penTuning =
      plotterDetails && isRecord(plotterDetails.pen_tuning) ? plotterDetails.pen_tuning : null;
    if (penTuning && typeof penTuning.pen_pos_up === "number") {
      setPenPosUp(String(penTuning.pen_pos_up));
    }
    if (penTuning && typeof penTuning.pen_pos_down === "number") {
      setPenPosDown(String(penTuning.pen_pos_down));
    }
  }, [hardwareStatus?.plotter.details]);

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

  const plotterDetails = hardwareStatus.plotter.details;
  const isAxiDraw = hardwareStatus.plotter.driver === "axidraw-pyapi";
  const penTuning = isRecord(plotterDetails.pen_tuning) ? plotterDetails.pen_tuning : null;
  const apiSurface =
    typeof plotterDetails.api_surface === "string" ? plotterDetails.api_surface : null;
  const lastTestAction =
    typeof plotterDetails.last_test_action === "string"
      ? plotterDetails.last_test_action
      : null;
  const lastTestActionStatus =
    typeof plotterDetails.last_test_action_status === "string"
      ? plotterDetails.last_test_action_status
      : null;

  const penHeightDisabled =
    actionName !== null || hardwareStatus.plotter.busy || !hardwareStatus.plotter.available;

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
          actionLabel="Return to origin"
          status={hardwareStatus.plotter}
          onAction={returnToOrigin}
          actionPending={actionName === "plotter-return"}
          notice={
            hardwareStatus.plotter.error
              ? { tone: "error", message: hardwareStatus.plotter.error }
              : actionFeedback &&
                  (actionFeedback.action === "plotter-return" ||
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
            isAxiDraw ? (
              <div className="diagnostic-panel">
                <div className="diagnostic-section">
                  <h3>Pen heights</h3>
                  <div className="pen-height-grid">
                    <label className="field-group">
                      <span>Pen up</span>
                      <input
                        type="number"
                        min={0}
                        max={100}
                        value={penPosUp}
                        onChange={(event) => setPenPosUp(event.target.value)}
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
                        onChange={(event) => setPenPosDown(event.target.value)}
                        disabled={penHeightDisabled}
                      />
                    </label>
                    <button
                      type="button"
                      className="button-secondary"
                      onClick={() =>
                        void setPlotterPenHeights(Number(penPosUp), Number(penPosDown))
                      }
                      disabled={
                        penHeightDisabled ||
                        penPosUp.trim() === "" ||
                        penPosDown.trim() === ""
                      }
                    >
                      Apply heights
                    </button>
                  </div>
                </div>

                <div className="diagnostic-section">
                  <h3>AxiDraw diagnostics</h3>
                  <div className="actions">
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
                      Align motors
                    </button>
                  </div>
                </div>

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
              </div>
            ) : null
          }
          footer={
            <p className="footer-note">
              Backend-controlled motion only. “Return to origin” means move back
              to the configured setup origin, not true hardware homing.
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

      <PlotWorkflowPanel hardwareStatus={hardwareStatus} />

      <LatestCapturePanel capture={latestCapture} refreshing={refreshing} />
    </main>
  );
}
