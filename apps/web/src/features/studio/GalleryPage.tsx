import { useEffect, useState } from "react";

import { fetchDrawingSessions } from "../../lib/api";
import type { DrawingSessionSummary } from "../../types/drawing";

function formatDate(timestamp: string) {
  return new Date(timestamp).toLocaleDateString([], {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function GalleryPage() {
  const [sessions, setSessions] = useState<DrawingSessionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchDrawingSessions()
      .then((response) => {
        if (!active) return;
        setSessions(response.sessions);
        setError(null);
      })
      .catch((loadError) => {
        if (!active) return;
        setError(loadError instanceof Error ? loadError.message : "Unable to load the gallery.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <main className="gallery-page">
      <header className="gallery-heading">
        <div>
          <p className="eyebrow">Gallery</p>
          <h1>Drawings made through observation</h1>
          <p>Return to an active session or revisit how a completed drawing developed.</p>
        </div>
        <a className="button-primary" href="/">Create a drawing</a>
      </header>

      {loading ? <p role="status">Loading sessions…</p> : null}
      {error ? <div className="banner" role="alert">{error}</div> : null}
      {!loading && !error && sessions.length === 0 ? (
        <section className="gallery-empty">
          <h2>The gallery is waiting for its first drawing.</h2>
          <p>Start with an idea; planning happens before any machine movement.</p>
          <a className="button-primary" href="/">Create a drawing</a>
        </section>
      ) : null}

      <div className="gallery-grid">
        {sessions.map((session) => (
          <a key={session.id} className="gallery-card" href={`/sessions/${session.id}`}>
            <div className="gallery-card-preview">
              {session.preview_url ? (
                <img src={session.preview_url} alt="" />
              ) : (
                <span aria-hidden="true" className="studio-orbit" />
              )}
            </div>
            <div className="gallery-card-copy">
              <div className="gallery-card-status">
                <span>{session.status.replace(/_/g, " ")}</span>
                {session.session_version === 1 ? <span>Legacy</span> : null}
              </div>
              <h2>{session.intent}</h2>
              <p>
                {session.pass_count === 1 ? "1 pass" : `${session.pass_count} passes`} · {formatDate(session.updated_at)}
              </p>
            </div>
          </a>
        ))}
      </div>
    </main>
  );
}
