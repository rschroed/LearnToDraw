import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import type {
  CaptureMetadata,
  CaptureReview,
  NormalizationCorners,
} from "../../types/hardware";

type CornerKey = keyof NormalizationCorners;

const CORNER_OPTIONS: readonly [CornerKey, string][] = [
  ["top_left", "Top left"],
  ["top_right", "Top right"],
  ["bottom_right", "Bottom right"],
  ["bottom_left", "Bottom left"],
];

const MAGNIFIER_WINDOW_PX = 120;

const MAGNIFIER_POSITIONS: Record<CornerKey, string> = {
  top_left: "bottom-right",
  top_right: "bottom-left",
  bottom_right: "top-left",
  bottom_left: "top-right",
};

interface CaptureReviewEditorProps {
  capture: CaptureMetadata;
  review: CaptureReview;
  busy: boolean;
  error: string | null;
  revision?: boolean;
  onCancel?: () => void;
  onConfirm: (corners: NormalizationCorners) => Promise<void>;
}

function cloneCorners(corners: NormalizationCorners): NormalizationCorners {
  return {
    top_left: [...corners.top_left] as [number, number],
    top_right: [...corners.top_right] as [number, number],
    bottom_right: [...corners.bottom_right] as [number, number],
    bottom_left: [...corners.bottom_left] as [number, number],
  };
}

export function mapClientPointToCapture(
  svg: SVGSVGElement,
  clientX: number,
  clientY: number,
  captureWidth: number,
  captureHeight: number,
): [number, number] | null {
  if (!Number.isFinite(clientX) || !Number.isFinite(clientY)) {
    return null;
  }
  const screenMatrix = svg.getScreenCTM();
  if (!screenMatrix) {
    return null;
  }
  const point = svg.createSVGPoint();
  point.x = clientX;
  point.y = clientY;
  const local = point.matrixTransform(screenMatrix.inverse());
  const x = Math.max(0, Math.min(captureWidth - 1, local.x));
  const y = Math.max(0, Math.min(captureHeight - 1, local.y));
  return [Number(x.toFixed(1)), Number(y.toFixed(1))];
}

export function CaptureReviewEditor({
  capture,
  review,
  busy,
  error,
  revision = false,
  onCancel,
  onConfirm,
}: CaptureReviewEditorProps) {
  const startingCorners = review.confirmed_corners ?? review.proposed_corners;
  const [draftCorners, setDraftCorners] = useState<NormalizationCorners>(() =>
    cloneCorners(startingCorners),
  );
  const [selectedCorner, setSelectedCorner] = useState<CornerKey>("top_left");
  const [draggingCorner, setDraggingCorner] = useState<CornerKey | null>(null);
  const [isAdjusting, setIsAdjusting] = useState(false);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const startingCornersSignature = JSON.stringify(startingCorners);

  useEffect(() => {
    setDraftCorners(JSON.parse(startingCornersSignature) as NormalizationCorners);
    setSelectedCorner("top_left");
    setDraggingCorner(null);
    setIsAdjusting(false);
  }, [capture.id, startingCornersSignature]);

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

  useEffect(() => {
    if (!isAdjusting || typeof document === "undefined") {
      return undefined;
    }
    const handleDocumentKeyDown = (event: KeyboardEvent) => {
      if (busy || event.defaultPrevented) {
        return;
      }
      const step = event.shiftKey ? 10 : 1;
      const deltas: Partial<Record<string, [number, number]>> = {
        ArrowLeft: [-step, 0],
        ArrowRight: [step, 0],
        ArrowUp: [0, -step],
        ArrowDown: [0, step],
      };
      const delta = deltas[event.key];
      if (!delta) {
        return;
      }
      event.preventDefault();
      nudgeCorner(selectedCorner, delta[0], delta[1]);
    };
    document.addEventListener("keydown", handleDocumentKeyDown);
    return () => document.removeEventListener("keydown", handleDocumentKeyDown);
  }, [busy, capture.height, capture.width, draftCorners, isAdjusting, selectedCorner]);

  function setCorner(key: CornerKey, point: [number, number]) {
    setDraftCorners((current) => ({ ...current, [key]: point }));
  }

  function updateCorner(clientX: number, clientY: number, key: CornerKey) {
    const svg = svgRef.current;
    if (!svg) {
      return;
    }
    const point = mapClientPointToCapture(
      svg,
      clientX,
      clientY,
      capture.width,
      capture.height,
    );
    if (point) {
      setCorner(key, point);
    }
  }

  function nudgeCorner(key: CornerKey, deltaX: number, deltaY: number) {
    const [x, y] = draftCorners[key];
    setCorner(key, [
      Math.max(0, Math.min(capture.width - 1, x + deltaX)),
      Math.max(0, Math.min(capture.height - 1, y + deltaY)),
    ]);
  }

  function handleCornerKeyDown(
    event: React.KeyboardEvent<SVGGElement | HTMLButtonElement>,
    key: CornerKey,
  ) {
    if (busy) {
      return;
    }
    const step = event.shiftKey ? 10 : 1;
    const deltas: Partial<Record<string, [number, number]>> = {
      ArrowLeft: [-step, 0],
      ArrowRight: [step, 0],
      ArrowUp: [0, -step],
      ArrowDown: [0, step],
    };
    const delta = deltas[event.key];
    if (!delta) {
      return;
    }
    event.preventDefault();
    setSelectedCorner(key);
    nudgeCorner(key, delta[0], delta[1]);
  }

  function resetDraftCorners() {
    setDraftCorners(cloneCorners(startingCorners));
    setSelectedCorner("top_left");
    setDraggingCorner(null);
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
          preserveAspectRatio="xMidYMid meet"
          className="capture-review-svg"
          aria-label="Captured page with registration corners"
          onPointerDown={(event) => {
            if (!interactive || busy) {
              return;
            }
            updateCorner(event.clientX, event.clientY, selectedCorner);
          }}
          onPointerMove={(event) => {
            if (interactive && !busy && draggingCorner) {
              updateCorner(event.clientX, event.clientY, draggingCorner);
            }
          }}
          onPointerUp={() => setDraggingCorner(null)}
          onPointerCancel={() => setDraggingCorner(null)}
          onPointerLeave={() => setDraggingCorner(null)}
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
          {CORNER_OPTIONS.map(([key, name]) => {
            const point = draftCorners[key];
            const label = name
              .split(" ")
              .map((part) => part[0].toUpperCase())
              .join("");
            return (
              <g
                key={key}
                className={selectedCorner === key ? "capture-review-corner-selected" : undefined}
                role={interactive ? "button" : undefined}
                tabIndex={interactive && !busy ? 0 : undefined}
                aria-disabled={interactive ? busy : undefined}
                aria-label={interactive ? `${name} corner` : undefined}
                onFocus={interactive ? () => setSelectedCorner(key) : undefined}
                onKeyDown={interactive ? (event) => handleCornerKeyDown(event, key) : undefined}
                onPointerDown={
                  interactive
                      ? (event) => {
                        if (busy) {
                          return;
                        }
                        event.preventDefault();
                        event.stopPropagation();
                        event.currentTarget.setPointerCapture(event.pointerId);
                        setSelectedCorner(key);
                        setDraggingCorner(key);
                        updateCorner(event.clientX, event.clientY, key);
                      }
                    : undefined
                }
              >
                {interactive ? (
                  <circle className="capture-review-handle-target" cx={point[0]} cy={point[1]} r="34" />
                ) : null}
                <circle
                  className={
                    interactive
                      ? "capture-review-handle capture-review-handle-interactive"
                      : "capture-review-handle"
                  }
                  cx={point[0]}
                  cy={point[1]}
                  r={interactive ? 16 : 12}
                />
                <text
                  x={point[0] + (interactive ? 22 : 14)}
                  y={point[1] - (interactive ? 22 : 14)}
                  className="capture-review-label"
                >
                  {label}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    );
  }

  function renderCornerMagnifier() {
    const [x, y] = draftCorners[selectedCorner];
    const cornerName = CORNER_OPTIONS.find(([key]) => key === selectedCorner)?.[1] ?? "Corner";
    const halfWindow = MAGNIFIER_WINDOW_PX / 2;
    const oppositePosition = MAGNIFIER_POSITIONS[selectedCorner];

    return (
      <aside
        className={`capture-review-magnifier capture-review-magnifier-opposite-${oppositePosition}`}
        aria-label={`Magnified ${cornerName.toLowerCase()} corner`}
      >
        <div className="capture-review-magnifier-heading">
          <strong>{cornerName} detail</strong>
          <span>
            {x.toFixed(1)}, {y.toFixed(1)} px
          </span>
        </div>
        <svg
          viewBox={`${x - halfWindow} ${y - halfWindow} ${MAGNIFIER_WINDOW_PX} ${MAGNIFIER_WINDOW_PX}`}
          preserveAspectRatio="xMidYMid meet"
          className="capture-review-magnifier-svg"
          role="img"
          aria-label={`${cornerName} at ${x.toFixed(1)}, ${y.toFixed(1)} raw pixels`}
        >
          <image href={capture.public_url} x="0" y="0" width={capture.width} height={capture.height} />
          <line
            className="capture-review-magnifier-crosshair"
            x1={x - halfWindow}
            y1={y}
            x2={x + halfWindow}
            y2={y}
          />
          <line
            className="capture-review-magnifier-crosshair"
            x1={x}
            y1={y - halfWindow}
            x2={x}
            y2={y + halfWindow}
          />
          <circle className="capture-review-magnifier-center" cx={x} cy={y} r="1.5" />
        </svg>
      </aside>
    );
  }

  const registrationModal = isAdjusting ? (
    <div
      className="capture-review-modal"
      role="dialog"
      aria-modal="true"
      aria-label="Register captured page"
    >
      <div
        className="capture-review-modal-backdrop"
        onClick={() => {
          if (!busy) {
            setIsAdjusting(false);
          }
        }}
      />
      <div className="capture-review-modal-panel">
        <header className="capture-review-modal-header">
          <div>
            <h3>{revision ? "Adjust captured page" : "Register captured page"}</h3>
            <p>Choose a corner, then click or drag it onto the physical paper corner.</p>
          </div>
          <button
            type="button"
            className="button-ghost"
            onClick={() => setIsAdjusting(false)}
            disabled={busy}
          >
            Close
          </button>
        </header>
        <div className="capture-review-corner-controls" aria-label="Selected corner">
          {CORNER_OPTIONS.map(([key, label]) => (
            <button
              key={key}
              type="button"
              className={
                key === selectedCorner
                  ? "artifact-variant-button artifact-variant-button-active"
                  : "artifact-variant-button"
              }
              aria-pressed={key === selectedCorner}
              disabled={busy}
              onClick={() => setSelectedCorner(key)}
              onKeyDown={(event) => handleCornerKeyDown(event, key)}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="capture-review-modal-stage">
          {renderCaptureCanvas(true)}
          {renderCornerMagnifier()}
        </div>
        <div className="capture-review-modal-footer">
          <div>
            <p className="capture-review-caption">
              Use the detail view to place the crosshair exactly on the paper corner. Arrow keys
              work anywhere in this dialog and nudge by 1 raw pixel; hold Shift for 10.
            </p>
            {error ? (
              <p className="capture-review-error" role="alert">
                {error}
              </p>
            ) : null}
          </div>
          <div className="capture-review-actions">
            <button
              type="button"
              className="artifact-variant-button"
              disabled={busy}
              onClick={resetDraftCorners}
            >
              Reset
            </button>
            <button
              type="button"
              className="artifact-variant-button artifact-variant-button-active"
              disabled={busy}
              onClick={() => void onConfirm(draftCorners)}
            >
              {busy ? "Registering…" : revision ? "Save registration" : "Register capture"}
            </button>
          </div>
        </div>
      </div>
    </div>
  ) : null;

  return (
    <>
      <div className="capture-review-shell">
        {renderCaptureCanvas(false)}
        <div className="capture-review-meta">
          <p className="capture-review-caption">
            {revision ? "Refine the saved manual page registration." : "Manual page registration required."}
          </p>
          <p className="capture-review-caption">
            Place each labeled point on the matching physical paper corner.
          </p>
        </div>
        <div className="capture-review-actions">
          {revision && onCancel ? (
            <button
              type="button"
              className="artifact-variant-button"
              disabled={busy}
              onClick={onCancel}
            >
              Back to comparison
            </button>
          ) : null}
          <button
            type="button"
            className="artifact-variant-button artifact-variant-button-active"
            disabled={busy}
            onClick={() => setIsAdjusting(true)}
          >
            {revision ? "Adjust corners" : "Register page"}
          </button>
        </div>
      </div>
      {registrationModal && typeof document !== "undefined"
        ? createPortal(registrationModal, document.body)
        : null}
    </>
  );
}
