import { useEffect, useRef, useState } from "react";

import type {
  CaptureMetadata,
  CaptureReview,
  NormalizationCorners,
} from "../../types/hardware";

type CornerKey = keyof NormalizationCorners;

interface CaptureReviewEditorProps {
  capture: CaptureMetadata;
  review: CaptureReview;
  busy: boolean;
  onAccept: () => Promise<void>;
  onAdjust: (corners: NormalizationCorners) => Promise<void>;
  onReuseLast: () => Promise<void>;
}

function cornersEqual(left: NormalizationCorners, right: NormalizationCorners) {
  return (
    left.top_left[0] === right.top_left[0] &&
    left.top_left[1] === right.top_left[1] &&
    left.top_right[0] === right.top_right[0] &&
    left.top_right[1] === right.top_right[1] &&
    left.bottom_right[0] === right.bottom_right[0] &&
    left.bottom_right[1] === right.bottom_right[1] &&
    left.bottom_left[0] === right.bottom_left[0] &&
    left.bottom_left[1] === right.bottom_left[1]
  );
}

function cloneCorners(corners: NormalizationCorners): NormalizationCorners {
  return {
    top_left: [...corners.top_left] as [number, number],
    top_right: [...corners.top_right] as [number, number],
    bottom_right: [...corners.bottom_right] as [number, number],
    bottom_left: [...corners.bottom_left] as [number, number],
  };
}

export function CaptureReviewEditor({
  capture,
  review,
  busy,
  onAccept,
  onAdjust,
  onReuseLast,
}: CaptureReviewEditorProps) {
  const [draftCorners, setDraftCorners] = useState<NormalizationCorners>(() =>
    cloneCorners(review.proposed_corners),
  );
  const [activeCorner, setActiveCorner] = useState<CornerKey | null>(null);
  const [isAdjusting, setIsAdjusting] = useState(false);
  const [isDirty, setIsDirty] = useState(false);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const previousCaptureIdRef = useRef(capture.id);
  const previousProposalSignatureRef = useRef(JSON.stringify(review.proposed_corners));
  const proposalSignature = JSON.stringify(review.proposed_corners);

  useEffect(() => {
    const captureChanged = previousCaptureIdRef.current !== capture.id;
    const proposalChanged = previousProposalSignatureRef.current !== proposalSignature;
    if (captureChanged || (proposalChanged && !isAdjusting && !isDirty && activeCorner === null)) {
      setDraftCorners(cloneCorners(review.proposed_corners));
      setActiveCorner(null);
      setIsDirty(false);
    }
    if (captureChanged) {
      setIsAdjusting(false);
    }
    previousCaptureIdRef.current = capture.id;
    previousProposalSignatureRef.current = proposalSignature;
  }, [activeCorner, capture.id, isAdjusting, isDirty, proposalSignature, review.proposed_corners]);

  useEffect(() => {
    if (!isAdjusting || typeof document === "undefined") {
      return undefined;
    }
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [isAdjusting]);

  const hasAdjustment = !cornersEqual(draftCorners, review.proposed_corners);

  function updateCorner(clientX: number, clientY: number, key: CornerKey) {
    const svg = svgRef.current;
    if (!svg) {
      return;
    }
    const rect = svg.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) {
      return;
    }
    const x = Math.max(
      0,
      Math.min(capture.width, ((clientX - rect.left) / rect.width) * capture.width),
    );
    const y = Math.max(
      0,
      Math.min(capture.height, ((clientY - rect.top) / rect.height) * capture.height),
    );
    setDraftCorners((current) => ({
      ...current,
      [key]: [Number(x.toFixed(1)), Number(y.toFixed(1))],
    }));
    setIsDirty(true);
  }

  function resetDraftCorners() {
    setDraftCorners(cloneCorners(review.proposed_corners));
    setActiveCorner(null);
    setIsDirty(false);
  }

  function openAdjustMode() {
    resetDraftCorners();
    setIsAdjusting(true);
  }

  function closeAdjustMode() {
    resetDraftCorners();
    setIsAdjusting(false);
  }

  function renderCaptureCanvas(interactive: boolean) {
    return (
      <div
        className={
          interactive ? "capture-review-frame capture-review-frame-modal" : "capture-review-frame"
        }
      >
        <svg
          ref={interactive ? svgRef : null}
          viewBox={`0 0 ${capture.width} ${capture.height}`}
          className="capture-review-svg"
          onPointerMove={(event) => {
            if (interactive && activeCorner) {
              updateCorner(event.clientX, event.clientY, activeCorner);
            }
          }}
          onPointerUp={() => {
            if (interactive) {
              setActiveCorner(null);
            }
          }}
          onPointerCancel={() => {
            if (interactive) {
              setActiveCorner(null);
            }
          }}
          onPointerLeave={() => {
            if (interactive) {
              setActiveCorner(null);
            }
          }}
        >
          <image href={capture.public_url} x="0" y="0" width={capture.width} height={capture.height} />
          <polygon
            className="capture-review-polygon"
            points={[
              draftCorners.top_left.join(","),
              draftCorners.top_right.join(","),
              draftCorners.bottom_right.join(","),
              draftCorners.bottom_left.join(","),
            ].join(" ")}
          />
          {(
            [
              ["top_left", draftCorners.top_left, "TL"],
              ["top_right", draftCorners.top_right, "TR"],
              ["bottom_right", draftCorners.bottom_right, "BR"],
              ["bottom_left", draftCorners.bottom_left, "BL"],
            ] as const
          ).map(([key, point, label]) => (
            <g key={key}>
              <circle
                className={
                  interactive
                    ? "capture-review-handle capture-review-handle-interactive"
                    : "capture-review-handle"
                }
                cx={point[0]}
                cy={point[1]}
                r={interactive ? 18 : 12}
                onPointerDown={
                  interactive
                    ? (event) => {
                        event.preventDefault();
                        event.currentTarget.setPointerCapture(event.pointerId);
                        setActiveCorner(key);
                        updateCorner(event.clientX, event.clientY, key);
                      }
                    : undefined
                }
              />
              <text
                x={point[0] + (interactive ? 22 : 14)}
                y={point[1] - (interactive ? 22 : 14)}
                className="capture-review-label"
              >
                {label}
              </text>
            </g>
          ))}
        </svg>
      </div>
    );
  }

  return (
    <>
      <div className="capture-review-shell">
        {renderCaptureCanvas(false)}
        <div className="capture-review-meta">
          <p className="capture-review-caption">
            {`Detection: ${review.detector_method} · confidence ${review.detector_confidence.toFixed(2)}`}
          </p>
          <p className="capture-review-caption">
            Accept when the suggested quad is already usable, or open adjust mode to fine-tune the page corners.
          </p>
        </div>
        <div className="capture-review-actions">
          <button
            type="button"
            className="artifact-variant-button artifact-variant-button-active"
            disabled={busy}
            onClick={() => void onAccept()}
          >
            Accept
          </button>
          <button
            type="button"
            className="artifact-variant-button"
            disabled={busy}
            onClick={openAdjustMode}
          >
            Adjust
          </button>
          <button
            type="button"
            className="artifact-variant-button"
            disabled={busy || !review.reuse_last_available}
            onClick={() => void onReuseLast()}
          >
            Reuse last
          </button>
        </div>
      </div>
      {isAdjusting ? (
        <div className="capture-review-modal" role="dialog" aria-modal="true" aria-label="Adjust capture corners">
          <div
            className="capture-review-modal-backdrop"
            onClick={() => {
              if (!busy) {
                closeAdjustMode();
              }
            }}
          />
          <div className="capture-review-modal-panel">
            <header className="capture-review-modal-header">
              <div>
                <h3>Adjust capture corners</h3>
                <p>{`Drag each corner onto the paper edge, then apply the adjusted quad.`}</p>
              </div>
              <button type="button" className="button-ghost" onClick={closeAdjustMode} disabled={busy}>
                Close
              </button>
            </header>
            <div className="capture-review-modal-stage">{renderCaptureCanvas(true)}</div>
            <div className="capture-review-modal-footer">
              <p className="capture-review-caption">
                {`Detection: ${review.detector_method} · confidence ${review.detector_confidence.toFixed(2)}`}
              </p>
              <div className="capture-review-actions">
                <button type="button" className="artifact-variant-button" disabled={busy || !isDirty} onClick={resetDraftCorners}>
                  Reset
                </button>
                <button
                  type="button"
                  className="artifact-variant-button"
                  disabled={busy || !review.reuse_last_available}
                  onClick={() => void onReuseLast()}
                >
                  Reuse last
                </button>
                <button
                  type="button"
                  className="artifact-variant-button artifact-variant-button-active"
                  disabled={busy || !hasAdjustment}
                  onClick={() => void onAdjust(draftCorners)}
                >
                  Apply adjusted quad
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
