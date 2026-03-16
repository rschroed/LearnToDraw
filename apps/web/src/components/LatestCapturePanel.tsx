import type { CaptureMetadata } from "../types/hardware";

interface LatestCapturePanelProps {
  capture: CaptureMetadata | null;
  refreshing: boolean;
}

export function LatestCapturePanel({
  capture,
  refreshing,
}: LatestCapturePanelProps) {
  return (
    <section className="capture-panel">
      <header>
        <div>
          <h2>Latest Capture</h2>
          <div className="hardware-meta">
            {capture
              ? `Saved at ${new Date(capture.timestamp).toLocaleString()}`
              : "No captures saved yet"}
          </div>
        </div>
        <button type="button" className="button-secondary" disabled>
          {refreshing ? "Refreshing..." : "Disk-backed"}
        </button>
      </header>

      <div className="capture-frame">
        {capture ? (
          <img
            src={capture.public_url}
            alt={`Latest camera capture ${capture.id}`}
          />
        ) : (
          <div className="empty-state">
            Trigger a capture to save a local artifact and preview it here.
          </div>
        )}
      </div>

      {capture ? (
        <p className="footer-note">
          {capture.width} x {capture.height} · {capture.mime_type} · {capture.file_path}
        </p>
      ) : null}
    </section>
  );
}
