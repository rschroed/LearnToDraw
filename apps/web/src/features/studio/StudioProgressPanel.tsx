import type { DrawingSession } from "../../types/drawing";
import type { PlotRun } from "../../types/plotting";
import { deriveStudioProgress } from "./studioProgress";

export function StudioProgressPanel({
  session,
  run,
}: {
  session: DrawingSession;
  run: PlotRun | null;
}) {
  const progress = deriveStudioProgress(session, run);

  return (
    <section
      className="studio-progress"
      data-tone={progress.tone}
      aria-labelledby="studio-progress-title"
      aria-live="polite"
      aria-atomic="true"
    >
      <div className="studio-progress-copy">
        <div className="studio-progress-now">
          <span className="studio-progress-pulse" aria-hidden="true" />
          <span>Right now</span>
          <span aria-hidden="true">·</span>
          <span>{progress.passLabel}</span>
        </div>
        <h2 id="studio-progress-title">{progress.title}</h2>
        <p>{progress.detail}</p>
      </div>
      <ol className="studio-progress-steps" aria-label="Drawing cycle">
        {progress.steps.map((step) => (
          <li
            key={step.id}
            className="studio-progress-step"
            data-state={step.state}
            aria-current={step.state === "active" || step.state === "attention" ? "step" : undefined}
          >
            <span className="studio-progress-step-mark" aria-hidden="true" />
            <span>{step.label}</span>
            <span className="sr-only">
              {step.state === "complete"
                ? " complete"
                : step.state === "attention"
                  ? " needs attention"
                  : step.state === "active"
                    ? " in progress"
                    : " pending"}
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}
