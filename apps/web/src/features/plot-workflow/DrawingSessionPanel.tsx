import { useState } from "react";

import type { PlotAsset } from "../../types/plotting";
import { useDrawingSession } from "./useDrawingSession";

interface DrawingSessionPanelProps {
  selectedAsset: PlotAsset | null;
  plotStartBlocked: boolean;
  onRunStarted: () => Promise<void>;
}

const STATUS_LABELS = {
  planning: "Planning",
  awaiting_approval: "Ready for approval",
  running: "Plotting or capturing",
  awaiting_capture_review: "Registration needs review",
  observed: "Observation ready",
  proposal_ready: "Next layer ready",
  paused: "Paused",
  stopping: "Stopping safely",
  completed: "Iteration limit reached",
  failed: "Session stopped",
  abandoned: "Left unfinished",
};

export function DrawingSessionPanel({
  selectedAsset,
  plotStartBlocked,
  onRunStarted,
}: DrawingSessionPanelProps) {
  const [intent, setIntent] = useState("");
  const [iterationLimit, setIterationLimit] = useState(3);
  const controller = useDrawingSession(onRunStarted);
  const session = controller.session;
  const currentIteration = session
    ? session.iterations[session.iterations.length - 1] ?? null
    : null;
  const proposal = currentIteration?.next_proposal ?? null;
  const validIterationLimit = Number.isInteger(iterationLimit)
    && iterationLimit >= 2
    && iterationLimit <= 10;
  const canRequestAdvice = session?.status === "observed" && session.advisor.available;
  const canPlotProposal = session?.status === "proposal_ready" && !plotStartBlocked;

  return (
    <section className="panel drawing-session-panel">
      <header className="drawing-session-header">
        <div>
          <p className="eyebrow">Iterative drawing</p>
          <h2>Observe, then add another pass</h2>
          <p className="drawing-session-explainer">
            Each pass adds ink to the same sheet. The advisor can interpret the registered photo,
            but every proposed layer must be previewed and explicitly plotted here.
          </p>
        </div>
        {session ? (
          <span
            className={`status-pill status-pill-${session.status === "failed" ? "warn" : "ok"}`}
          >
            <span className="status-pill-dot" />
            {STATUS_LABELS[session.status]}
          </span>
        ) : null}
      </header>

      <div className="drawing-session-start">
        <label>
          Drawing intent
          <textarea
            value={intent}
            onChange={(event) => setIntent(event.target.value)}
            placeholder="For example: a lively field of flowers with varied height and rhythm"
            rows={2}
          />
        </label>
        <label>
          Passes
          <input
            type="number"
            min="2"
            max="10"
            value={iterationLimit}
            onChange={(event) => setIterationLimit(Number(event.target.value))}
          />
        </label>
        <button
          type="button"
          className="button-secondary"
          disabled={
            !selectedAsset ||
            intent.trim().length < 3 ||
            !validIterationLimit ||
            plotStartBlocked ||
            controller.busyAction !== null
          }
          onClick={() =>
            selectedAsset && void controller.start(intent.trim(), selectedAsset.id, iterationLimit)
          }
        >
          {controller.busyAction === "create"
            ? "Starting…"
            : "Start session and plot first pass"}
        </button>
      </div>

      {controller.error ? <div className="banner">{controller.error}</div> : null}

      {session && currentIteration ? (
        <div className="drawing-session-current">
          <div className="drawing-session-summary">
            <div>
              <span className="summary-label">Intent</span>
              <strong>{session.intent}</strong>
            </div>
            <div>
              <span className="summary-label">Progress</span>
              <strong>
                Pass {currentIteration.number}
                {session.iteration_limit ? ` of ${session.iteration_limit}` : ""}
              </strong>
            </div>
            <div>
              <span className="summary-label">Mode</span>
              <strong>Additive · same sheet</strong>
            </div>
          </div>

          <ol className="drawing-session-history" aria-label="Drawing session pass history">
            {session.iterations.map((iteration) => (
              <li key={iteration.run_id}>
                <span>Pass {iteration.number}</span>
                <strong>{iteration.asset.name}</strong>
                <span>
                  {iteration.number === currentIteration.number
                    ? STATUS_LABELS[session.status]
                    : "Observed"}
                </span>
              </li>
            ))}
          </ol>

          {session.status === "observed" ? (
            <div className="drawing-session-next-action">
              <div>
                <strong>Registered observation ready</strong>
                <p>
                  Request a visual interpretation and a new SVG layer. This does not move the
                  plotter.
                </p>
                {!session.advisor.available && session.advisor.message ? (
                  <p className="drawing-session-advisor-note">{session.advisor.message}</p>
                ) : null}
              </div>
              <button
                type="button"
                className="button-secondary"
                disabled={!canRequestAdvice || controller.busyAction !== null}
                onClick={() => void controller.requestAdvice()}
              >
                {controller.busyAction === "advice" ? "Interpreting…" : "Request next pass"}
              </button>
            </div>
          ) : null}

          {session.status === "proposal_ready" && proposal ? (
            <div className="drawing-proposal">
              <div className="drawing-proposal-copy">
                <span className="summary-label">Interpretation</span>
                <p>{proposal.interpretation}</p>
                <p className="drawing-session-advisor-note">
                  Proposed layer only: this adds permanent marks and cannot remove existing ink.
                </p>
                <button
                  type="button"
                  className="button-primary"
                  disabled={!canPlotProposal || controller.busyAction !== null}
                  onClick={() => void controller.approve()}
                >
                  {controller.busyAction === "approve" ? "Starting plot…" : "Plot proposed layer"}
                </button>
              </div>
              <div className="drawing-proposal-preview">
                <img src={proposal.asset.public_url} alt="Proposed additive SVG layer" />
              </div>
            </div>
          ) : null}

          {session.status === "failed" && session.error ? (
            <div className="banner">{session.error}</div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
