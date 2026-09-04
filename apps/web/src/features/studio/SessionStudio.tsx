import { useEffect, useRef, useState } from "react";

import { StatusPill } from "../../components/StatusPill";
import type { DrawingSessionStatus } from "../../types/drawing";
import { StudioCanvas } from "./StudioCanvas";
import { StudioConversation } from "./StudioConversation";
import { useStudioSession } from "./useStudioSession";

const STATUS_LABELS: Record<DrawingSessionStatus, string> = {
  planning: "Planning",
  awaiting_approval: "Ready for approval",
  running: "Drawing in progress",
  awaiting_capture_review: "Registration needed",
  observed: "Observation ready",
  proposal_ready: "Proposal ready",
  paused: "Paused for attention",
  stopping: "Stopping safely",
  completed: "Drawing complete",
  failed: "Session failed",
};

function activeSession(status: DrawingSessionStatus) {
  return ["running", "awaiting_capture_review", "stopping"].includes(status);
}

export function SessionStudio({ sessionId }: { sessionId: string }) {
  const controller = useStudioSession(sessionId);
  const [showEmergencyConfirm, setShowEmergencyConfirm] = useState(false);
  const emergencyCancelRef = useRef<HTMLButtonElement | null>(null);
  const planHeadingRef = useRef<HTMLHeadingElement | null>(null);
  const recoveryHeadingRef = useRef<HTMLHeadingElement | null>(null);
  const session = controller.session;
  const currentRun = session?.current_run_id
    ? controller.runs[session.current_run_id] ?? null
    : null;
  const completionEvents = session?.events.filter(
    (event) => event.type === "session_completed",
  ) ?? [];
  const completionMessage = completionEvents[completionEvents.length - 1]?.message;

  useEffect(() => {
    if (showEmergencyConfirm) emergencyCancelRef.current?.focus();
  }, [showEmergencyConfirm]);

  useEffect(() => {
    const activeElement = document.activeElement;
    if (activeElement instanceof HTMLInputElement || activeElement instanceof HTMLTextAreaElement) {
      return;
    }
    if (session?.status === "awaiting_approval") planHeadingRef.current?.focus();
    if (session?.status === "paused") recoveryHeadingRef.current?.focus();
  }, [session?.status]);

  if (controller.loading && !session) {
    return (
      <main className="studio-loading" aria-live="polite">
        <span className="studio-thinking-mark" aria-hidden="true" />
        <h1>Opening the studio…</h1>
      </main>
    );
  }

  if (!session) {
    return (
      <main className="studio-loading">
        <h1>This drawing could not be opened.</h1>
        <p>{controller.error ?? "The session may no longer be available."}</p>
        <a className="button-secondary" href="/gallery">Return to gallery</a>
      </main>
    );
  }

  const plotterReady = controller.hardwareStatus?.plotter.available === true;
  const cameraReady = controller.hardwareStatus?.camera.available === true;
  const canRetryCapture = Boolean(
    currentRun &&
      currentRun.capture_mode === "auto" &&
      currentRun.stage_states.plot?.status === "completed" &&
      ["completed", "failed", "awaiting_capture_review"].includes(currentRun.status),
  );
  const canEmergencyStop = Boolean(
    currentRun && ["pending", "plotting"].includes(currentRun.status),
  );

  return (
    <main className="studio-session-shell">
      <header className="studio-session-heading">
        <div>
          <p className="eyebrow">Drawing session</p>
          <h1>{session.intent}</h1>
          <div className="studio-session-meta">
            <strong>{STATUS_LABELS[session.status]}</strong>
            <span aria-hidden="true">·</span>
            <span>{session.pass_count === 1 ? "1 pass" : `${session.pass_count} passes`}</span>
            {session.session_version === 1 ? <span>Legacy session</span> : null}
          </div>
        </div>
        <div className="studio-session-readiness" aria-label="Machine readiness">
          <StatusPill
            label="Studio"
            value={controller.hardwareStatus ? "online" : "offline"}
            tone={controller.hardwareStatus ? "ok" : "warn"}
          />
          <StatusPill label="Plotter" value={plotterReady ? "ready" : "attention"} tone={plotterReady ? "ok" : "warn"} />
          <StatusPill label="Camera" value={cameraReady ? "ready" : "attention"} tone={cameraReady ? "ok" : "warn"} />
        </div>
      </header>

      <div className="sr-only" role="status" aria-live="polite">
        {STATUS_LABELS[session.status]}. Pass {session.pass_count}.
      </div>

      {controller.hardwareError ? (
        <div className="studio-attention-banner" role="status">
          <strong>Local studio connection needs attention.</strong>
          <span>{controller.hardwareError} The current physical pass will finish safely.</span>
        </div>
      ) : null}

      {session.advisor.available === false ? (
        <div className="studio-attention-banner" role="status">
          <strong>Creative advisor unavailable.</strong>
          <span>{session.advisor.message}</span>
        </div>
      ) : null}

      {controller.error && session.status !== "awaiting_capture_review" ? (
        <div className="banner" role="alert">{controller.error}</div>
      ) : null}

      <div className="studio-workspace">
        <div className="studio-artwork-column">
          <StudioCanvas
            session={session}
            runs={controller.runs}
            captureReview={controller.captureReview}
            busy={
              controller.busyAction === "register" ||
              controller.busyAction === "retry-capture"
            }
            retryingCapture={controller.busyAction === "retry-capture"}
            error={controller.captureReview ? controller.error : null}
            onConfirmRegistration={controller.confirmRegistration}
            onRetryCapture={controller.retryCapture}
          />

          {session.status === "planning" ? (
            <section className="studio-plan-card studio-plan-card-thinking" aria-live="polite">
              <p className="eyebrow">Planning</p>
              <h2>Finding the first useful marks</h2>
              <p>No hardware will move until a safe SVG preview is ready and you approve it.</p>
            </section>
          ) : null}

          {session.status === "awaiting_approval" && session.plan ? (
            <section className="studio-plan-card">
              <div className="studio-plan-copy">
                <div>
                  <p className="eyebrow">Drawing plan</p>
                  <h2 ref={planHeadingRef} tabIndex={-1}>{session.plan.summary}</h2>
                </div>
                <dl className="studio-plan-details">
                  <div>
                    <dt>Use of the paper</dt>
                    <dd>{session.plan.paper_strategy}</dd>
                  </div>
                  <div>
                    <dt>Finished when</dt>
                    <dd>{session.plan.completion_intent}</dd>
                  </div>
                </dl>
              </div>
              <div className="studio-approval">
                <p>
                  Approving authorizes an attended sequence of plot, photograph, and agent-decision
                  cycles. It may add more than one permanent layer without asking again.
                </p>
                <button
                  type="button"
                  className="button-primary"
                  disabled={controller.busyAction !== null || !plotterReady || !cameraReady}
                  onClick={() => void controller.approve()}
                >
                  {controller.busyAction === "approve" ? "Authorizing…" : "Approve and begin"}
                </button>
              </div>
            </section>
          ) : null}

          {session.status === "paused" ? (
            <section className="studio-recovery" aria-labelledby="recovery-title">
              <div>
                <p className="eyebrow">Needs attention</p>
                <h2 id="recovery-title" ref={recoveryHeadingRef} tabIndex={-1}>
                  The drawing is safely paused.
                </h2>
                <p>{session.requested_human_action ?? session.error ?? "Inspect the latest observation before continuing."}</p>
              </div>
              <div className="studio-recovery-actions">
                {canRetryCapture && currentRun ? (
                  <button
                    type="button"
                    className="button-secondary"
                    disabled={controller.busyAction !== null}
                    onClick={() => void controller.retryCapture(currentRun.id)}
                  >
                    {controller.busyAction === "retry-capture" ? "Retaking…" : "Retake photo only"}
                  </button>
                ) : null}
                <button
                  type="button"
                  className="button-primary"
                  disabled={controller.busyAction !== null || !plotterReady || !cameraReady}
                  onClick={() => void controller.resume()}
                >
                  {controller.busyAction === "resume" ? "Rechecking…" : "Resume session"}
                </button>
              </div>
            </section>
          ) : null}

          {session.status === "completed" ? (
            <section className="studio-complete">
              <p className="eyebrow">Complete</p>
              <h2>The studio decided the drawing has arrived.</h2>
              <p>{completionMessage}</p>
              <div className="studio-complete-actions">
                <a className="button-secondary" href="/gallery">View gallery</a>
                <a className="button-primary" href="/">Create another drawing</a>
              </div>
            </section>
          ) : null}

          {session.status === "failed" ? (
            <section className="studio-recovery" aria-labelledby="failed-title">
              <div>
                <p className="eyebrow">Session stopped</p>
                <h2 id="failed-title">This drawing needs a fresh start.</h2>
                <p>{session.error ?? "The session could not continue safely."}</p>
              </div>
              <a className="button-primary" href="/">Create another drawing</a>
            </section>
          ) : null}
        </div>

        <StudioConversation
          session={session}
          busyAction={controller.busyAction}
          onSend={controller.sendMessage}
        />
      </div>

      {session.session_version === 2 && session.authorization.approved_at && activeSession(session.status) ? (
        <div className="studio-stop-dock" aria-label="Session controls">
          <div>
            <strong>{session.status === "stopping" ? "Finishing the current safe boundary…" : "The studio is authorized to continue."}</strong>
            <span>Guidance waits for the next decision; stop requests never interrupt persistence.</span>
          </div>
          <button
            type="button"
            className="button-secondary"
            disabled={controller.busyAction !== null || session.status === "stopping"}
            onClick={() => void controller.stopAfterPass()}
          >
            {controller.busyAction === "stop-after-pass" ? "Stopping…" : "Stop after this pass"}
          </button>
          <button
            type="button"
            className="button-danger"
            disabled={
              controller.busyAction !== null ||
              session.status === "stopping" ||
              !canEmergencyStop
            }
            onClick={() => setShowEmergencyConfirm(true)}
          >
            Emergency stop
          </button>
        </div>
      ) : null}

      {showEmergencyConfirm ? (
        <div className="studio-confirm-modal" role="alertdialog" aria-modal="true" aria-labelledby="emergency-title" aria-describedby="emergency-description">
          <div className="studio-confirm-card">
            <p className="eyebrow">Emergency intervention</p>
            <h2 id="emergency-title">Pause the active plot?</h2>
            <p id="emergency-description">
              The AxiDraw pauses after its current path segment—not as an instant power cut. No
              capture or later agent pass will begin, and resuming a partially plotted SVG is not
              supported.
            </p>
            <div>
              <button ref={emergencyCancelRef} type="button" className="button-secondary" onClick={() => setShowEmergencyConfirm(false)}>
                Keep drawing
              </button>
              <button
                type="button"
                className="button-danger"
                onClick={() => {
                  setShowEmergencyConfirm(false);
                  void controller.emergencyStop();
                }}
              >
                Pause after current segment
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </main>
  );
}
