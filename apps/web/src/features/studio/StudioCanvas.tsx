import { useEffect, useMemo, useState } from "react";

import { CaptureReviewEditor } from "../plot-workflow/CaptureReviewEditor";
import { isV2PageAlignedCapture } from "../plot-workflow/RunArtifactCompare";
import type { DrawingSession } from "../../types/drawing";
import type { NormalizationCorners } from "../../types/hardware";
import type { PlotRun, PlotRunCaptureReviewPayload } from "../../types/plotting";

type CanvasMode = "intended" | "observed" | "overlay" | "registration";

interface StudioCanvasProps {
  session: DrawingSession;
  runs: Record<string, PlotRun>;
  pageSize?: { width_mm: number; height_mm: number } | null;
  captureReview: PlotRunCaptureReviewPayload | null;
  busy: boolean;
  retryingCapture: boolean;
  error: string | null;
  onConfirmRegistration: (runId: string, corners: NormalizationCorners) => Promise<void>;
  onRetryCapture: (runId: string) => Promise<void>;
}

function readFinite(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function pageAspectFor(
  run: PlotRun | null,
  pageSize?: { width_mm: number; height_mm: number } | null,
) {
  const capture = run?.observed_result?.capture ?? run?.capture ?? null;
  const frame = capture?.normalized?.metadata.frame;
  if (frame && frame.page_width_mm > 0 && frame.page_height_mm > 0) {
    return frame.page_width_mm / frame.page_height_mm;
  }
  const preparation = run?.plotter_run_details.preparation;
  if (preparation && typeof preparation === "object") {
    const width = readFinite((preparation as Record<string, unknown>).page_width_mm);
    const height = readFinite((preparation as Record<string, unknown>).page_height_mm);
    if (width && height && width > 0 && height > 0) return width / height;
  }
  if (pageSize && pageSize.width_mm > 0 && pageSize.height_mm > 0) {
    return pageSize.width_mm / pageSize.height_mm;
  }
  return 210 / 297;
}

export function StudioCanvas({
  session,
  runs,
  pageSize = null,
  captureReview,
  busy,
  retryingCapture,
  error,
  onConfirmRegistration,
  onRetryCapture,
}: StudioCanvasProps) {
  const currentRun = session.current_run_id ? runs[session.current_run_id] ?? null : null;
  const latestObservedRun = useMemo(
    () =>
      [...session.iterations]
        .reverse()
        .map((iteration) => runs[iteration.run_id])
        .find((run) => Boolean(run?.observed_result?.capture ?? run?.capture)) ?? null,
    [runs, session.iterations],
  );
  const observation =
    latestObservedRun?.observed_result?.capture ?? latestObservedRun?.capture ?? null;
  const observedUrl =
    observation?.normalized?.rectified_grayscale_url ?? observation?.public_url ?? null;
  const intendedUrls = session.iterations
    .map((iteration) => runs[iteration.run_id]?.prepared_artifact?.public_url)
    .filter((url): url is string => Boolean(url));
  const proposalUrl =
    intendedUrls.length === 0 ? session.current_proposal?.asset.public_url ?? null : null;
  const overlayAvailable = Boolean(
    observedUrl && intendedUrls.length > 0 && isV2PageAlignedCapture(observation),
  );
  const [mode, setMode] = useState<CanvasMode>(
    session.status === "awaiting_capture_review" ? "registration" : "intended",
  );
  const [intendedOpacity, setIntendedOpacity] = useState(55);

  useEffect(() => {
    if (session.status === "awaiting_capture_review" && captureReview) {
      setMode("registration");
    } else if (observation) {
      setMode("observed");
    } else {
      setMode("intended");
    }
  }, [captureReview?.capture.id, observation?.id, session.status]);

  useEffect(() => {
    if (captureReview) return;
    if (mode === "overlay" && !overlayAvailable) setMode("observed");
    if (mode === "registration") {
      setMode(observation ? "observed" : "intended");
    }
  }, [captureReview, mode, observation, overlayAvailable]);

  const aspect = pageAspectFor(currentRun ?? latestObservedRun, pageSize);
  const hasIntended = intendedUrls.length > 0 || Boolean(proposalUrl);

  return (
    <section className="studio-canvas-panel" aria-label="Drawing canvas">
      <header className="studio-canvas-toolbar">
        <div>
          <p className="eyebrow">Paper</p>
          <h2>
            {mode === "observed"
              ? "What the camera sees"
              : mode === "overlay"
                ? "Intended versus observed"
                : mode === "registration"
                  ? "Register this observation"
                  : "What we intend to draw"}
          </h2>
        </div>
        <div className="studio-canvas-modes" aria-label="Canvas view">
          <button
            type="button"
            aria-pressed={mode === "intended"}
            disabled={!hasIntended}
            onClick={() => setMode("intended")}
          >
            Intended
          </button>
          <button
            type="button"
            aria-pressed={mode === "observed"}
            disabled={!observedUrl}
            onClick={() => setMode("observed")}
          >
            Observed
          </button>
          <button
            type="button"
            aria-pressed={mode === "overlay"}
            disabled={!overlayAvailable}
            onClick={() => setMode("overlay")}
          >
            Overlay
          </button>
          {captureReview ? (
            <button
              type="button"
              aria-pressed={mode === "registration"}
              onClick={() => setMode("registration")}
            >
              Register
            </button>
          ) : null}
        </div>
      </header>

      {mode === "registration" && captureReview ? (
        <div className="studio-registration-wrap">
          <div className="studio-registration-recovery">
            <p>
              If the page is blocked, blurred, or overexposed, take another photograph before
              placing its corners. The drawing will not be plotted again.
            </p>
            <button
              type="button"
              className="button-secondary"
              disabled={busy}
              onClick={() => void onRetryCapture(captureReview.run_id)}
            >
              {retryingCapture ? "Retaking photo…" : "Retake photo only"}
            </button>
          </div>
          <CaptureReviewEditor
            capture={captureReview.capture}
            review={captureReview.review}
            busy={busy}
            error={error}
            onConfirm={(corners) => onConfirmRegistration(captureReview.run_id, corners)}
          />
        </div>
      ) : (
        <div className="studio-paper-stage">
          <div className="studio-paper" style={{ aspectRatio: `${aspect}` }}>
            {mode === "observed" && observedUrl ? (
              <img src={observedUrl} alt="Latest registered drawing observation" />
            ) : null}

            {mode === "overlay" && observedUrl ? (
              <>
                <img src={observedUrl} alt="Latest registered drawing observation" />
                <div
                  className="studio-intended-stack studio-intended-stack-overlay"
                  style={{ opacity: intendedOpacity / 100 }}
                >
                  {intendedUrls.map((url, index) => (
                    <img key={url} src={url} alt={`Intended drawing pass ${index + 1}`} />
                  ))}
                </div>
              </>
            ) : null}

            {mode === "intended" ? (
              <div className="studio-intended-stack">
                {proposalUrl ? (
                  <img src={proposalUrl} alt="Proposed first drawing pass" />
                ) : null}
                {intendedUrls.map((url, index) => (
                  <img key={url} src={url} alt={`Intended drawing pass ${index + 1}`} />
                ))}
              </div>
            ) : null}

            {!hasIntended && !observedUrl ? (
              <div className="studio-paper-empty" role="status">
                <span className="studio-thinking-mark" aria-hidden="true" />
                <strong>The drawing plan is taking shape.</strong>
                <span>The first marks will appear here before anything moves.</span>
              </div>
            ) : null}
          </div>
        </div>
      )}

      {mode === "overlay" ? (
        <label className="studio-opacity-control">
          Intended opacity
          <input
            type="range"
            min="0"
            max="100"
            value={intendedOpacity}
            onChange={(event) => setIntendedOpacity(Number(event.target.value))}
          />
          <span>{intendedOpacity}%</span>
        </label>
      ) : null}

      {observation && !isV2PageAlignedCapture(observation) ? (
        <p className="studio-canvas-note">Legacy registration · overlay unavailable</p>
      ) : null}
    </section>
  );
}
