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
        <div className="capture-meta">
          <div className="capture-meta-grid">
            <div className="capture-meta-item">
              <span>Saved at</span>
              <strong>{new Date(capture.timestamp).toLocaleString()}</strong>
            </div>
            <div className="capture-meta-item">
              <span>Dimensions</span>
              <strong>
                {capture.width} x {capture.height}
              </strong>
            </div>
            <div className="capture-meta-item">
              <span>Format</span>
              <strong>{capture.mime_type}</strong>
            </div>
          </div>
          <p className="footer-note capture-meta-path">{capture.file_path}</p>
        </div>
      ) : null}
    </section>
  );
}
