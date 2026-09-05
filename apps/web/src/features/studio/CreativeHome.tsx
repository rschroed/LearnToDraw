import { useEffect, useRef, useState, type FormEvent } from "react";

import { StatusPill } from "../../components/StatusPill";
import {
  createDrawingSession,
  fetchHardwareStatus,
  fetchLatestDrawingSession,
} from "../../lib/api";
import type { DrawingSession } from "../../types/drawing";
import type { HardwareStatus } from "../../types/hardware";

const RESUMABLE_STATUSES = new Set([
  "planning",
  "awaiting_approval",
  "running",
  "awaiting_capture_review",
  "paused",
  "stopping",
]);

export function CreativeHome({
  navigate,
  resumeActive = true,
}: {
  navigate: (path: string) => void;
  resumeActive?: boolean;
}) {
  const [intent, setIntent] = useState("");
  const [hardware, setHardware] = useState<HardwareStatus | null>(null);
  const [recentSession, setRecentSession] = useState<DrawingSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    Promise.all([fetchHardwareStatus(), fetchLatestDrawingSession()])
      .then(([status, latest]) => {
        if (!mountedRef.current) return;
        setHardware(status);
        setRecentSession(latest.session);
        setError(null);
        if (
          resumeActive &&
          latest.session &&
          RESUMABLE_STATUSES.has(latest.session.status)
        ) {
          navigate(`/sessions/${latest.session.id}`);
        }
      })
      .catch((loadError) => {
        if (!mountedRef.current) return;
        setError(
          loadError instanceof Error ? loadError.message : "The local studio is unavailable.",
        );
      })
      .finally(() => {
        if (mountedRef.current) setLoading(false);
      });
    return () => {
      mountedRef.current = false;
    };
  }, [resumeActive]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const nextIntent = intent.trim();
    if (nextIntent.length < 3 || creating) return;
    try {
      setCreating(true);
      setError(null);
      const session = await createDrawingSession(nextIntent);
      navigate(`/sessions/${session.id}`);
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Unable to start a drawing.");
    } finally {
      if (mountedRef.current) setCreating(false);
    }
  }

  const plotterReady = hardware?.plotter.available === true;
  const cameraReady = hardware?.camera.available === true;
  const ready = plotterReady && cameraReady;

  return (
    <main className="creative-home">
      <section className="creative-home-hero">
        <div className="creative-home-kicker">
          <span className="studio-orbit" aria-hidden="true" />
          <span>A drawing studio that looks, responds, and keeps going</span>
        </div>
        <h1>What should we draw?</h1>
        <p className="creative-home-lede">
          Begin with an idea. The studio will propose a composition and show its first marks before
          the plotter moves.
        </p>

        <form className="creative-prompt" onSubmit={submit}>
          <label htmlFor="creative-intent" className="sr-only">Drawing idea</label>
          <textarea
            id="creative-intent"
            value={intent}
            rows={4}
            autoFocus
            maxLength={1000}
            placeholder="A pelican riding a bicycle through a field of loose, joyful flowers…"
            onChange={(event) => setIntent(event.target.value)}
          />
          <div className="creative-prompt-footer">
            <span>The first step is only a plan and preview.</span>
            <button
              type="submit"
              className="button-primary creative-submit"
              disabled={
                intent.trim().length < 3 || loading || creating || Boolean(error && !hardware)
              }
            >
              {creating ? "Creating the plan…" : "Create a drawing"}
            </button>
          </div>
        </form>

        {error ? (
          <div className="creative-home-blocker" role="alert">
            <strong>{hardware ? "The studio needs attention." : "Local backend unavailable."}</strong>
            <span>{error}</span>
            <a href="/controls">Open Controls</a>
          </div>
        ) : null}

        {!loading && hardware && !ready ? (
          <div className="creative-home-blocker" role="status">
            <strong>Hardware setup will be needed before approval.</strong>
            <span>
              {!plotterReady && !cameraReady
                ? "The plotter and camera need attention."
                : !plotterReady
                  ? "The plotter needs attention."
                  : "The camera needs attention."}
            </span>
            <a href="/controls">Open Controls</a>
          </div>
        ) : null}

        <div className="creative-home-links">
          {recentSession ? (
            <a href={`/sessions/${recentSession.id}`}>Open recent drawing</a>
          ) : null}
          <a href="/gallery">Browse gallery</a>
          <a href="/controls">Manual plotting and Controls</a>
        </div>
      </section>

      <aside className="creative-readiness" aria-label="Studio readiness">
        <span>{loading ? "Checking the studio…" : ready ? "Ready to create" : "Setup needed"}</span>
        <div>
          <StatusPill label="Plotter" value={plotterReady ? "ready" : "attention"} tone={plotterReady ? "ok" : "warn"} />
          <StatusPill label="Camera" value={cameraReady ? "ready" : "attention"} tone={cameraReady ? "ok" : "warn"} />
        </div>
      </aside>
    </main>
  );
}
