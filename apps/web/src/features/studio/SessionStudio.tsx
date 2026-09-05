import { useEffect, useRef, useState } from "react";

import { StatusPill } from "../../components/StatusPill";
import type { DrawingSessionStatus } from "../../types/drawing";
import { StudioCanvas } from "./StudioCanvas";
import { StudioConversation } from "./StudioConversation";
import { StudioProgressPanel } from "./StudioProgressPanel";
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
  abandoned: "Left unfinished",
};

function activeSession(status: DrawingSessionStatus) {
  return ["running", "awaiting_capture_review", "stopping"].includes(status);
}

export function SessionStudio({
  sessionId,
  navigate,
}: {
  sessionId: string;
  navigate: (path: string) => void;
}) {
  const controller = useStudioSession(sessionId);
  const [showEmergencyConfirm, setShowEmergencyConfirm] = useState(false);
  const [showNewDrawingConfirm, setShowNewDrawingConfirm] = useState(false);
  const [startNewAfterFinish, setStartNewAfterFinish] = useState(false);
  const [paperReady, setPaperReady] = useState(false);
  const emergencyCancelRef = useRef<HTMLButtonElement | null>(null);
  const newDrawingCancelRef = useRef<HTMLButtonElement | null>(null);
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
    if (showNewDrawingConfirm) newDrawingCancelRef.current?.focus();
  }, [showNewDrawingConfirm]);

  useEffect(() => {
    setPaperReady(false);
  }, [session?.current_proposal?.asset.id]);

  useEffect(() => {
    if (
      startNewAfterFinish &&
      session &&
      ["completed", "abandoned"].includes(session.status)
    ) {
      navigate("/new");
    }
  }, [navigate, session, startNewAfterFinish]);

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
  const pageSize = controller.plotterWorkspace?.page_size_mm ?? null;
  const pageOrientation = pageSize
    ? pageSize.width_mm > pageSize.height_mm
      ? "landscape"
      : pageSize.height_mm > pageSize.width_mm
        ? "portrait"
        : "square"
    : null;
  const hasPlottedWork = session.pass_count > 0;
  const isEnded = ["completed", "failed", "abandoned"].includes(session.status);
  const advisorNeedsAttention =
    session.advisor.available === false ||
    session.error?.toLowerCase().includes("drawing advisor") === true;

  async function abandonAndStart() {
    const succeeded = await controller.abandon();
    if (succeeded) navigate("/new");
  }

  async function finishAndStart() {
    setStartNewAfterFinish(true);
    setShowNewDrawingConfirm(false);
    const succeeded = await controller.finish();
    if (!succeeded) setStartNewAfterFinish(false);
  }

  function requestNewDrawing() {
    if (isEnded) {
      navigate("/new");
      return;
    }
    setShowNewDrawingConfirm(true);
  }

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
        <div className="studio-session-heading-actions">
          <div className="studio-session-readiness" aria-label="Machine readiness">
            <StatusPill
              label="Studio"
              value={controller.hardwareStatus ? "online" : "offline"}
              tone={controller.hardwareStatus ? "ok" : "warn"}
            />
            <StatusPill label="Plotter" value={plotterReady ? "ready" : "attention"} tone={plotterReady ? "ok" : "warn"} />
            <StatusPill label="Camera" value={cameraReady ? "ready" : "attention"} tone={cameraReady ? "ok" : "warn"} />
          </div>
          <button
            type="button"
            className="button-secondary"
            disabled={controller.busyAction !== null}
            onClick={requestNewDrawing}
          >
            New drawing
          </button>
        </div>
      </header>

      <StudioProgressPanel session={session} run={currentRun} />

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
            pageSize={controller.plotterWorkspace?.page_size_mm}
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
              <h2>Designing and reviewing the first pass</h2>
              <p>
                The advisor is ranking what matters, drawing a candidate, and checking the rendered
                page before showing it. Detailed vector plans can take a few minutes. No hardware
                will move until a safe preview is ready and you approve it.
              </p>
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
                {session.plan.creative_criteria.length > 0 ? (
                  <div className="studio-creative-criteria">
                    <h3>What matters most</h3>
                    <ol>
                      {session.plan.creative_criteria.map((criterion) => (
                        <li key={criterion}>{criterion}</li>
                      ))}
                    </ol>
                  </div>
                ) : null}
                {session.current_proposal?.quality_review ? (
                  <div className="studio-quality-review">
                    <strong>
                      {session.current_proposal.quality_review.revision_applied
                        ? "Revised once before preview"
                        : "Candidate passed creative review"}
                    </strong>
                    <p>{session.current_proposal.quality_review.summary}</p>
                    <details>
                      <summary>Criterion review</summary>
                      <ol>
                        {session.current_proposal.quality_review.criterion_assessments.map(
                          (item) => (
                            <li key={item.rank}>
                              <span>{item.criterion}</span>
                              <small>{item.outcome.replace("_", " ")}: {item.assessment}</small>
                            </li>
                          ),
                        )}
                      </ol>
                    </details>
                  </div>
                ) : null}
              </div>
              <div className="studio-approval">
                <div className="studio-paper-preflight">
                  <div>
                    <strong>Before the plotter moves</strong>
                    <span>
                      {pageSize && pageOrientation
                        ? `${pageSize.width_mm} × ${pageSize.height_mm} mm · ${pageOrientation}`
                        : "Paper setup is unavailable."}
                    </span>
                  </div>
                  <label>
                    <input
                      type="checkbox"
                      checked={paperReady}
                      disabled={controller.busyAction !== null || !pageSize}
                      onChange={(event) => setPaperReady(event.target.checked)}
                    />
                    <span>I have a blank sheet loaded in this orientation and a pen installed.</span>
                  </label>
                  <a href="/controls">Change paper or machine setup</a>
                </div>
                <p>
                  Approving authorizes an attended sequence of plot, photograph, and agent-decision
                  cycles. It may add more than one permanent layer without asking again.
                </p>
                <button
                  type="button"
                  className="button-primary"
                  disabled={
                    controller.busyAction !== null ||
                    !plotterReady ||
                    !cameraReady ||
                    !pageSize ||
                    !paperReady
                  }
                  onClick={() => void controller.approve(paperReady)}
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
                {advisorNeedsAttention ? (
                  <a className="button-secondary" href="/controls">Change advisor</a>
                ) : null}
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
                {hasPlottedWork ? (
                  <button
                    type="button"
                    className="button-secondary"
                    disabled={controller.busyAction !== null}
                    onClick={() => void controller.finish()}
                  >
                    {controller.busyAction === "finish" ? "Finishing…" : "Finish drawing"}
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
                <a className="button-primary" href="/new">Create another drawing</a>
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
              <a className="button-primary" href="/new">Create another drawing</a>
            </section>
          ) : null}

          {session.status === "abandoned" ? (
            <section className="studio-recovery">
              <div>
                <p className="eyebrow">Left unfinished</p>
                <h2>This session will not make another move.</h2>
                <p>Its plan, events, and any completed passes remain available here for reference.</p>
              </div>
              <a className="button-primary" href="/new">Start a new drawing</a>
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
            className="button-secondary"
            disabled={controller.busyAction !== null || session.status === "stopping"}
            onClick={() => void controller.finish()}
          >
            {controller.busyAction === "finish" ? "Finishing…" : "Finish drawing"}
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

      {showNewDrawingConfirm ? (
        <div
          className="studio-confirm-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="new-drawing-title"
          aria-describedby="new-drawing-description"
        >
          <div className="studio-confirm-card">
            <p className="eyebrow">New drawing</p>
            <h2 id="new-drawing-title">
              {hasPlottedWork ? "What should happen to this drawing?" : "Leave this draft?"}
            </h2>
            <p id="new-drawing-description">
              {hasPlottedWork
                ? session.status === "paused"
                  ? "You can preserve it as a completed drawing or leave it unfinished. Neither choice moves the machine."
                  : "The current plot and photograph must finish safely. The studio will then complete this drawing and open a blank prompt."
                : "Nothing has been plotted. The unused plan will remain in Gallery as an unfinished session."}
            </p>
            <div>
              <button
                ref={newDrawingCancelRef}
                type="button"
                className="button-secondary"
                onClick={() => setShowNewDrawingConfirm(false)}
              >
                Keep this session
              </button>
              {hasPlottedWork && session.status === "paused" ? (
                <button
                  type="button"
                  className="button-secondary"
                  disabled={controller.busyAction !== null}
                  onClick={() => void abandonAndStart()}
                >
                  Leave unfinished
                </button>
              ) : null}
              <button
                type="button"
                className="button-primary"
                disabled={controller.busyAction !== null}
                onClick={() => {
                  if (hasPlottedWork) {
                    void finishAndStart();
                  } else {
                    void abandonAndStart();
                  }
                }}
              >
                {hasPlottedWork
                  ? session.status === "paused"
                    ? "Finish and start new"
                    : "Finish this pass, then start new"
                  : "Abandon and start new"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </main>
  );
}
