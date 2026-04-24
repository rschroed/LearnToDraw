import { useEffect, useMemo, useState } from "react";

import type { CaptureMetadata } from "../types/hardware";

type CaptureVariantKey = "raw" | "normalized" | "debug";

interface CaptureVariantOption {
  key: CaptureVariantKey;
  label: string;
  url: string;
}

interface LatestCapturePanelProps {
  capture: CaptureMetadata | null;
  refreshing: boolean;
}

export function LatestCapturePanel({
  capture,
  refreshing,
}: LatestCapturePanelProps) {
  const variantOptions = useMemo(() => {
    if (!capture) {
      return [] as CaptureVariantOption[];
    }
    const options: CaptureVariantOption[] = [
      {
        key: "raw",
        label: "Raw",
        url: capture.public_url,
      },
    ];
    if (capture.normalized) {
      options.push(
        {
          key: "normalized",
          label: "Normalized",
          url: capture.normalized.rectified_grayscale_url,
        },
        {
          key: "debug",
          label: "Debug",
          url: capture.normalized.debug_overlay_url,
        },
      );
    }
    return options;
  }, [capture]);
  const defaultVariant: CaptureVariantKey = capture?.normalized ? "normalized" : "raw";
  const [variant, setVariant] = useState<CaptureVariantKey>(defaultVariant);

  useEffect(() => {
    setVariant(defaultVariant);
  }, [defaultVariant, capture?.id]);

  const selectedVariant =
    variantOptions.find((option) => option.key === variant) ?? variantOptions[0] ?? null;
  const footerLabel = selectedVariant ? `${selectedVariant.label} variant` : null;

  return (
    <section className="capture-panel latest-capture-panel">
      <header>
        <div>
          <h2>Latest Capture</h2>
          <div className="hardware-meta">
            {capture
              ? `Saved at ${new Date(capture.timestamp).toLocaleString()}`
              : "No captures saved yet"}
          </div>
        </div>
        <div className="capture-panel-actions latest-capture-panel-actions">
          {variantOptions.length > 1 ? (
            <div className="artifact-variant-selector" role="group" aria-label="Latest capture variant">
              {variantOptions.map((option) => (
                <button
                  key={option.key}
                  type="button"
                  className={
                    option.key === variant
                      ? "artifact-variant-button artifact-variant-button-active"
                      : "artifact-variant-button"
                  }
                  aria-pressed={option.key === variant}
                  onClick={() => setVariant(option.key)}
                >
                  {option.label}
                </button>
              ))}
            </div>
          ) : null}
          <button type="button" className="button-secondary" disabled>
            {refreshing ? "Refreshing..." : "Disk-backed"}
          </button>
        </div>
      </header>

      <div className="capture-frame latest-capture-frame">
        {capture ? (
          <img
            src={selectedVariant?.url ?? capture.public_url}
            alt={
              selectedVariant
                ? `${selectedVariant.label.toLowerCase()} latest camera capture ${capture.id}`
                : `Latest camera capture ${capture.id}`
            }
          />
        ) : (
          <div className="empty-state">
            Trigger a capture to save a local artifact and preview it here.
          </div>
        )}
      </div>

      {capture ? (
        <div className="capture-meta latest-capture-meta">
          <div className="capture-meta-grid latest-capture-meta-grid">
            <div className="capture-meta-item latest-capture-meta-item">
              <span>Saved at</span>
              <strong>{new Date(capture.timestamp).toLocaleString()}</strong>
            </div>
            <div className="capture-meta-item latest-capture-meta-item">
              <span>Dimensions</span>
              <strong>
                {capture.width} x {capture.height}
              </strong>
            </div>
            <div className="capture-meta-item latest-capture-meta-item">
              <span>Format</span>
              <strong>{capture.mime_type}</strong>
            </div>
            {footerLabel ? (
              <div className="capture-meta-item latest-capture-meta-item">
                <span>Viewing</span>
                <strong>{footerLabel}</strong>
              </div>
            ) : null}
          </div>
          <p className="footer-note capture-meta-path latest-capture-meta-path">{capture.file_path}</p>
        </div>
      ) : null}
    </section>
  );
}
