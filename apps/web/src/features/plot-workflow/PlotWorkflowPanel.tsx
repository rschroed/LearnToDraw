import { useEffect, useMemo, useRef, useState, type CSSProperties, type ChangeEvent, type ReactNode } from "react";

import { fetchPlotRun } from "../../lib/api";
import type {
  CaptureMetadata,
  CaptureReview,
  HardwareStatus,
  NormalizationCorners,
  PlotterWorkspace,
} from "../../types/hardware";
import type { PlotAsset, PlotRun, PlotRunSummary } from "../../types/plotting";
import {
  formatPhysicalSize,
  formatResultMeta,
  formatRunMetaStrip,
  formatShortTimestamp,
  getRunStatusTone,
  getStageLabel,
  getStepSummaryItems,
  getStepSummaryNote,
  isRecord,
} from "./plotWorkflowFormatters";
import type { PlotWorkflowController } from "./usePlotWorkflow";

type PlotWorkflowMode = "workflow" | "history";
type CaptureVariantKey = "raw" | "normalized" | "debug";
type CornerKey = keyof NormalizationCorners;

interface PlotWorkflowPanelProps {
  controller: PlotWorkflowController;
  hardwareStatus: HardwareStatus;
  plotterWorkspace: PlotterWorkspace | null;
  latestCapture: CaptureMetadata | null;
  mode?: PlotWorkflowMode;
}

interface RunDetailRow {
  label: string;
  value: string;
}

interface CaptureVariantOption {
  key: CaptureVariantKey;
  label: string;
  url: string;
}

function resolvePreparedArtifactUrl(publicUrl: string) {
  if (/^https?:\/\//.test(publicUrl)) {
    return publicUrl;
  }
  if (typeof window === "undefined") {
    return publicUrl;
  }
  const { protocol, hostname, port } = window.location;
  if ((hostname === "127.0.0.1" || hostname === "localhost") && port !== "8000") {
    return `${protocol}//${hostname}:8000${publicUrl}`;
  }
  return publicUrl;
}

function getWorkflowBlockerMessage({
  selectedAsset,
  hardwareStatus,
  plotterWorkspace,
  busyAction,
  activeRun,
}: {
  selectedAsset: PlotWorkflowController["selectedAsset"];
  hardwareStatus: HardwareStatus;
  plotterWorkspace: PlotterWorkspace | null;
  busyAction: PlotWorkflowController["busyAction"];
  activeRun: boolean;
}) {
  if (activeRun) {
    return "A run is already in progress. Wait for it to finish before starting another.";
  }
  if (!selectedAsset) {
    return "Stage an SVG or load the test grid to begin a plot run.";
  }
  if (plotterWorkspace?.is_valid === false) {
    return `Paper setup needs attention before plotting: ${
      plotterWorkspace.validation_error ??
      "saved paper setup no longer fits the current machine bounds."
    }`;
  }
  if (!hardwareStatus.plotter.available) {
    return "The plotter is not ready. Review the Machine tab and restore plotter availability.";
  }
  if (!hardwareStatus.camera.available) {
    return "The camera is not ready. Review the Machine tab and restore camera readiness before running the loop.";
  }
  if (hardwareStatus.plotter.busy || hardwareStatus.camera.busy || busyAction === "start") {
    return "A machine action is still in progress. Wait for the hardware to return to idle.";
  }
  return null;
}

function formatRunKindLabel(kind: PlotAsset["kind"]) {
  return kind === "built_in_pattern" ? "Built-in pattern" : "Uploaded SVG";
}

function getHistoryRowThumbnail(run: PlotRun | null) {
  if (!run) {
    return null;
  }
  const resultCapture = run.observed_result?.capture ?? run.capture ?? null;
  if (resultCapture) {
    return {
      url: resultCapture.public_url,
      alt: `Result preview for ${run.asset.name}`,
      label: "result",
    };
  }
  if (run.prepared_artifact) {
    return {
      url: resolvePreparedArtifactUrl(run.prepared_artifact.public_url),
      alt: `Prepared preview for ${run.asset.name}`,
      label: "prepared",
    };
  }
  return {
    url: run.asset.public_url,
    alt: `Source preview for ${run.asset.name}`,
    label: "source",
  };
}

function getStatusLabel(status: PlotRun["status"]) {
  if (status === "completed") {
    return "Completed";
  }
  if (status === "failed") {
    return "Failed";
  }
  if (status === "capturing") {
    return "Capturing";
  }
  if (status === "plotting") {
    return "Plotting";
  }
  return "Preparing";
}

function getPreparationDetails(run: PlotRun | null) {
  const preparation =
    run && isRecord(run.plotter_run_details.preparation)
      ? run.plotter_run_details.preparation
      : null;
  const sourceSize = preparation
    ? formatPhysicalSize(preparation.source_width, preparation.source_height)
    : null;
  const preparedSize = preparation
    ? formatPhysicalSize(preparation.prepared_width_mm, preparation.prepared_height_mm)
    : null;
  const pageSize = preparation
    ? formatPhysicalSize(preparation.page_width_mm, preparation.page_height_mm)
    : null;
  const drawableArea = preparation
    ? formatPhysicalSize(preparation.drawable_width_mm, preparation.drawable_height_mm)
    : null;

  return [
    sourceSize ? { label: "Source size", value: sourceSize } : null,
    preparedSize ? { label: "Prepared size", value: preparedSize } : null,
    pageSize ? { label: "Page size", value: pageSize } : null,
    drawableArea ? { label: "Drawable area", value: drawableArea } : null,
  ].filter((detail): detail is RunDetailRow => detail !== null);
}

function asFiniteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function getPreparedPageAspectRatio(run: PlotRun | null): number | null {
  if (!run || !isRecord(run.plotter_run_details)) {
    return null;
  }
  const preparation = isRecord(run.plotter_run_details.preparation)
    ? run.plotter_run_details.preparation
    : null;
  if (!preparation) {
    return null;
  }

  const pageWidthMm = asFiniteNumber(preparation.page_width_mm);
  const pageHeightMm = asFiniteNumber(preparation.page_height_mm);
  if (
    pageWidthMm === null ||
    pageHeightMm === null ||
    pageWidthMm <= 0 ||
    pageHeightMm <= 0
  ) {
    return null;
  }
  return pageWidthMm / pageHeightMm;
}

function getSelectedVariantFooter({
  capture,
  selectedVariant,
  resultFooter,
}: {
  capture: CaptureMetadata | null;
  selectedVariant: CaptureVariantOption | null;
  resultFooter: string | null;
}) {
  if (
    selectedVariant?.key === "normalized" &&
    capture?.normalized?.metadata.frame?.kind !== "page_aligned"
  ) {
    return resultFooter ? `${selectedVariant.label} · Legacy frame · ${resultFooter}` : "Normalized · Legacy frame";
  }
  if (selectedVariant && resultFooter) {
    return `${selectedVariant.label} · ${resultFooter}`;
  }
  if (selectedVariant) {
    return selectedVariant.label;
  }
  return resultFooter;
}

function getNormalizedPageAspectRatio(capture: CaptureMetadata | null): number | null {
  const frame = capture?.normalized?.metadata.frame;
  if (!frame || frame.kind !== "page_aligned" || frame.page_width_mm <= 0 || frame.page_height_mm <= 0) {
    return null;
  }
  return frame.page_width_mm / frame.page_height_mm;
}

function getSelectedVariantFrameStyle({
  capture,
  selectedVariant,
}: {
  capture: CaptureMetadata | null;
  selectedVariant: CaptureVariantOption | null;
}): CSSProperties | undefined {
  if (selectedVariant?.key === "normalized") {
    const normalizedAspectRatio = getNormalizedPageAspectRatio(capture);
    if (normalizedAspectRatio !== null) {
      return { aspectRatio: `${normalizedAspectRatio}` };
    }
    const legacyAspectRatio = capture?.normalized?.metadata.output.aspect_ratio;
    if (legacyAspectRatio) {
      return { aspectRatio: `${legacyAspectRatio}` };
    }
  }
  return undefined;
}

function getCollapsedRowMeta(summary: PlotRunSummary, includeTimestamp: boolean) {
  const tokens = [formatRunKindLabel(summary.asset_kind)];
  if (summary.purpose !== "normal") {
    tokens.push(summary.purpose);
  }
  if (includeTimestamp) {
    tokens.push(formatShortTimestamp(summary.created_at));
  }
  return tokens.filter(Boolean).join(" · ");
}

function getExpandedMeta(run: PlotRun | PlotRunSummary, kindLabel: string) {
  return formatRunMetaStrip({
    kindLabel,
    run,
  });
}

function getResultFooter({
  capture,
  run,
}: {
  capture: CaptureMetadata | null;
  run: PlotRun | null;
}) {
  if (capture) {
    return formatResultMeta({ capture, includeTimestamp: false });
  }
  if (run?.capture_mode === "skip") {
    return "Capture skipped";
  }
  if (run?.status === "failed") {
    return run.error ?? "No result saved";
  }
  return null;
}

function getCaptureVariantOptions(capture: CaptureMetadata | null): CaptureVariantOption[] {
  if (!capture) {
    return [];
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
}

function getDefaultCaptureVariant(capture: CaptureMetadata | null): CaptureVariantKey {
  return capture?.normalized ? "normalized" : "raw";
}

function ArtifactCard({
  className,
  title,
  imageUrl,
  alt,
  emptyMessage,
  footer,
  headerActions,
  frameStyle,
  frameContent,
}: {
  className?: string;
  title: string;
  imageUrl?: string | null;
  alt?: string;
  emptyMessage: string;
  footer?: string | null;
  headerActions?: ReactNode;
  frameStyle?: CSSProperties;
  frameContent?: ReactNode;
}) {
  return (
    <article className={className ? `artifact-card ${className}` : "artifact-card"}>
      <header className="artifact-card-header">
        <h3>{title}</h3>
        {headerActions ? <div className="artifact-card-actions">{headerActions}</div> : null}
      </header>
      <div className="artifact-frame" style={frameStyle}>
        {frameContent ? (
          frameContent
        ) : imageUrl ? (
          <img src={imageUrl} alt={alt ?? title} />
        ) : (
          <div className="empty-state">{emptyMessage}</div>
        )}
      </div>
      {footer ? <p className="artifact-footer">{footer}</p> : null}
    </article>
  );
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

function CaptureReviewEditor({
  capture,
  review,
  busy,
  onAccept,
  onAdjust,
  onReuseLast,
}: {
  capture: CaptureMetadata;
  review: CaptureReview;
  busy: boolean;
  onAccept: () => Promise<void>;
  onAdjust: (corners: NormalizationCorners) => Promise<void>;
  onReuseLast: () => Promise<void>;
}) {
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
    const x = Math.max(0, Math.min(capture.width, ((clientX - rect.left) / rect.width) * capture.width));
    const y = Math.max(0, Math.min(capture.height, ((clientY - rect.top) / rect.height) * capture.height));
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
        className={interactive ? "capture-review-frame capture-review-frame-modal" : "capture-review-frame"}
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

function RunCaptureReview({
  run,
  preparedImageUrl,
  preparedPageAspectRatio,
  reviewCapture,
  review,
  reviewBusy,
  onAccept,
  onAdjust,
  onReuseLast,
}: {
  run: PlotRun;
  preparedImageUrl: string | null;
  preparedPageAspectRatio: number | null;
  reviewCapture: CaptureMetadata;
  review: CaptureReview;
  reviewBusy: boolean;
  onAccept: () => Promise<void>;
  onAdjust: (corners: NormalizationCorners) => Promise<void>;
  onReuseLast: () => Promise<void>;
}) {
  const preparedFrameStyle =
    preparedPageAspectRatio !== null ? { aspectRatio: `${preparedPageAspectRatio}` } : undefined;

  return (
    <div className="run-artifact-compare">
      <ArtifactCard
        className="artifact-card-prepared"
        title="Prepared"
        imageUrl={preparedImageUrl}
        alt={`Prepared output for run ${run.id}`}
        emptyMessage="Prepared output unavailable."
        footer={run.asset.name}
        frameStyle={preparedFrameStyle}
      />
      <article className="artifact-card artifact-card-result">
        <header className="artifact-card-header">
          <h3>Review capture</h3>
        </header>
        <div className="artifact-frame artifact-frame-review">
          <CaptureReviewEditor
            capture={reviewCapture}
            review={review}
            busy={reviewBusy}
            onAccept={onAccept}
            onAdjust={onAdjust}
            onReuseLast={onReuseLast}
          />
        </div>
        <p className="artifact-footer">Normalization will continue after you confirm the page corners.</p>
      </article>
    </div>
  );
}

function RunHeader({
  title,
  status,
  tone,
  meta,
}: {
  title: string;
  status: string;
  tone: ReturnType<typeof getRunStatusTone>;
  meta: string;
}) {
  return (
    <header className="run-header">
      <div className="run-header-main">
        <h3>{title}</h3>
        <span className={`status-pill status-pill-${tone}`}>
          <span className="status-pill-dot" />
          {status}
        </span>
      </div>
      <p className="run-meta-strip">{meta}</p>
    </header>
  );
}

function RunStepSummary({ run }: { run: PlotRun | null }) {
  const items = getStepSummaryItems(run);
  const note = getStepSummaryNote(run);

  if (!run || items.length === 0) {
    return null;
  }

  return (
    <section className="run-step-summary">
      <div className="run-step-strip">
        {items.map((item) => (
          <span key={item.key} className={`run-step-pill run-step-pill-${item.tone}`}>
            {item.label}
          </span>
        ))}
      </div>
      {note ? <p className="run-step-note">{note}</p> : null}
    </section>
  );
}

function RunDetailsBlock({ rows }: { rows: RunDetailRow[] }) {
  if (rows.length === 0) {
    return null;
  }

  return (
    <section className="run-details-block">
      <h4>Details</h4>
      <dl className="run-details-grid">
        {rows.map((row) => (
          <div key={row.label} className="run-details-row">
            <dt>{row.label}</dt>
            <dd>{row.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function RunSourceInspect({
  asset,
  open,
  onToggle,
}: {
  asset: PlotAsset | null;
  open: boolean;
  onToggle: () => void;
}) {
  if (!asset) {
    return null;
  }

  return (
    <section className="run-source-section">
      <button type="button" className="button-ghost source-inspect-toggle" onClick={onToggle}>
        {open ? "Hide source" : "View source"}
      </button>

      {open ? (
        <div className="source-inspect-drawer">
          <ArtifactCard
            title="Source"
            imageUrl={asset.public_url}
            alt={`Source reference ${asset.name}`}
            emptyMessage="Source preview unavailable."
            footer={asset.name}
          />
        </div>
      ) : null}
    </section>
  );
}

function RunArtifactCompare({
  preparedImageUrl,
  preparedAlt,
  preparedFooter,
  resultCapture,
  resultAlt,
  resultFooter,
  preparedEmptyMessage,
  resultEmptyMessage,
  preparedPageAspectRatio,
}: {
  preparedImageUrl: string | null;
  preparedAlt: string;
  preparedFooter: string | null;
  resultCapture: CaptureMetadata | null;
  resultAlt: string;
  resultFooter: string | null;
  preparedEmptyMessage: string;
  resultEmptyMessage: string;
  preparedPageAspectRatio: number | null;
}) {
  const variantOptions = useMemo(
    () => getCaptureVariantOptions(resultCapture),
    [resultCapture],
  );
  const defaultVariant = getDefaultCaptureVariant(resultCapture);
  const [resultVariant, setResultVariant] = useState<CaptureVariantKey>(defaultVariant);

  useEffect(() => {
    setResultVariant(defaultVariant);
  }, [defaultVariant, resultCapture?.id]);

  const selectedVariant =
    variantOptions.find((option) => option.key === resultVariant) ?? variantOptions[0] ?? null;
  const variantFooter = getSelectedVariantFooter({
    capture: resultCapture,
    selectedVariant,
    resultFooter,
  });
  const preparedFrameStyle =
    preparedPageAspectRatio !== null ? { aspectRatio: `${preparedPageAspectRatio}` } : undefined;
  const resultFrameStyle = getSelectedVariantFrameStyle({
    capture: resultCapture,
    selectedVariant,
  });

  return (
    <div className="run-artifact-compare">
      <ArtifactCard
        className="artifact-card-prepared"
        title="Prepared"
        imageUrl={preparedImageUrl}
        alt={preparedAlt}
        emptyMessage={preparedEmptyMessage}
        footer={preparedFooter}
        frameStyle={preparedFrameStyle}
      />
      <ArtifactCard
        className="artifact-card-result"
        title="Result"
        imageUrl={selectedVariant?.url ?? null}
        alt={
          selectedVariant
            ? `${selectedVariant.label.toLowerCase()} ${resultAlt}`
            : resultAlt
        }
        emptyMessage={resultEmptyMessage}
        footer={variantFooter}
        frameStyle={resultFrameStyle}
        headerActions={
          variantOptions.length > 1 ? (
            <div className="artifact-variant-selector" role="group" aria-label="Result variant">
              {variantOptions.map((option) => (
                <button
                  key={option.key}
                  type="button"
                  className={
                    option.key === resultVariant
                      ? "artifact-variant-button artifact-variant-button-active"
                      : "artifact-variant-button"
                  }
                  aria-pressed={option.key === resultVariant}
                  onClick={() => setResultVariant(option.key)}
                >
                  {option.label}
                </button>
              ))}
            </div>
          ) : null
        }
      />
    </div>
  );
}

function ExpandedRunSummary({
  title,
  meta,
  status,
  statusTone,
  run,
  preparedImageUrl,
  resultCapture,
  sourceAsset,
  sourceInspectOpen,
  onToggleSource,
}: {
  title: string;
  meta: string;
  status: string;
  statusTone: ReturnType<typeof getRunStatusTone>;
  run: PlotRun | null;
  preparedImageUrl: string | null;
  resultCapture: CaptureMetadata | null;
  sourceAsset: PlotAsset | null;
  sourceInspectOpen: boolean;
  onToggleSource: () => void;
}) {
  const detailRows = getPreparationDetails(run);
  const preparedPageAspectRatio = getPreparedPageAspectRatio(run);

  return (
    <section className="run-summary-card">
      <RunHeader title={title} status={status} tone={statusTone} meta={meta} />

      <RunArtifactCompare
        preparedImageUrl={preparedImageUrl}
        preparedAlt={run ? `Prepared output for run ${run.id}` : "Prepared output"}
        preparedFooter={sourceAsset?.name ?? null}
        resultCapture={resultCapture}
        resultAlt={run ? `Result image for run ${run.id}` : "Result image"}
        resultFooter={getResultFooter({ capture: resultCapture, run })}
        preparedEmptyMessage={
          run ? "Prepared output unavailable." : "Prepared output appears after a run is prepared."
        }
        resultEmptyMessage={
          run
            ? run.capture_mode === "skip"
              ? "Capture skipped for this run."
              : run.status === "failed"
                ? run.error ?? "No result saved."
                : "Result appears once the run reaches capture."
            : "No saved result yet."
        }
        preparedPageAspectRatio={preparedPageAspectRatio}
      />

      <RunStepSummary run={run} />
      <RunDetailsBlock rows={detailRows} />
      <RunSourceInspect asset={sourceAsset} open={sourceInspectOpen} onToggle={onToggleSource} />
    </section>
  );
}

function WorkflowRunSummary({
  displayRun,
  pendingCaptureReview,
  selectedAsset,
  latestCapture,
  reviewBusy,
  onAcceptCaptureReview,
  onAdjustCaptureReview,
  onReuseLastCaptureReview,
  sourceOpen,
  onToggleSource,
}: {
  displayRun: PlotRun | null;
  pendingCaptureReview: PlotWorkflowController["pendingCaptureReview"];
  selectedAsset: PlotAsset | null;
  latestCapture: CaptureMetadata | null;
  reviewBusy: boolean;
  onAcceptCaptureReview: (runId: string) => Promise<void>;
  onAdjustCaptureReview: (runId: string, corners: NormalizationCorners) => Promise<void>;
  onReuseLastCaptureReview: (runId: string) => Promise<void>;
  sourceOpen: boolean;
  onToggleSource: () => void;
}) {
  const sourceAsset = displayRun?.asset ?? selectedAsset;
  const resultCapture = displayRun?.observed_result?.capture ?? displayRun?.capture ?? latestCapture;
  const preparedImageUrl = displayRun?.prepared_artifact
    ? resolvePreparedArtifactUrl(displayRun.prepared_artifact.public_url)
    : null;
  const preparedPageAspectRatio = getPreparedPageAspectRatio(displayRun);
  const review =
    displayRun?.status === "awaiting_capture_review" &&
    pendingCaptureReview?.run_id === displayRun.id &&
    pendingCaptureReview.capture.review
      ? pendingCaptureReview.capture.review
      : null;

  return (
    <section className="panel comparison-panel">
      <header className="comparison-header">
        <div>
          <p className="eyebrow">Workflow</p>
          {displayRun ? (
            <p className="run-meta-strip comparison-meta">
              {getExpandedMeta(displayRun, formatRunKindLabel(displayRun.asset.kind))}
            </p>
          ) : latestCapture ? (
            <p className="run-meta-strip comparison-meta">Latest saved result</p>
          ) : null}
        </div>
        <div className="comparison-header-actions">
          <span className={`status-pill status-pill-${getRunStatusTone(displayRun?.status ?? "idle")}`}>
            <span className="status-pill-dot" />
            {displayRun ? getStageLabel(displayRun) : latestCapture ? "Result ready" : "Idle"}
          </span>
        </div>
      </header>

      {displayRun?.status === "awaiting_capture_review" && displayRun.capture && review ? (
        <RunCaptureReview
          run={displayRun}
          preparedImageUrl={preparedImageUrl}
          preparedPageAspectRatio={preparedPageAspectRatio}
          reviewCapture={displayRun.capture}
          review={review}
          reviewBusy={reviewBusy}
          onAccept={() => onAcceptCaptureReview(displayRun.id)}
          onAdjust={(corners) => onAdjustCaptureReview(displayRun.id, corners)}
          onReuseLast={() => onReuseLastCaptureReview(displayRun.id)}
        />
      ) : (
        <RunArtifactCompare
          preparedImageUrl={preparedImageUrl}
          preparedAlt={displayRun ? `Prepared output for run ${displayRun.id}` : "Prepared output"}
          preparedFooter={sourceAsset?.name ?? null}
          resultCapture={resultCapture}
          resultAlt={
            displayRun && resultCapture
              ? `Result image for run ${displayRun.id}`
              : latestCapture
                ? `Latest result capture ${latestCapture.id}`
                : "Result image"
          }
          resultFooter={
            displayRun
              ? getResultFooter({
                  capture: displayRun.observed_result?.capture ?? displayRun.capture ?? null,
                  run: displayRun,
                })
              : latestCapture
                ? formatResultMeta({ capture: latestCapture, includeTimestamp: false })
                : null
          }
          preparedEmptyMessage={
            displayRun
              ? "Prepared output unavailable."
              : "Prepared output appears after a run is prepared."
          }
          resultEmptyMessage={
            displayRun
              ? displayRun.capture_mode === "skip"
                ? "Capture skipped for this run."
                : displayRun.status === "failed"
                  ? displayRun.error ?? "No result saved."
                  : "Result appears once the run reaches capture."
              : "No saved result yet."
          }
          preparedPageAspectRatio={preparedPageAspectRatio}
        />
      )}

      <RunStepSummary run={displayRun} />
      <RunDetailsBlock rows={getPreparationDetails(displayRun)} />
      <RunSourceInspect asset={sourceAsset} open={sourceOpen} onToggle={onToggleSource} />
    </section>
  );
}

export function PlotWorkflowPanel({
  controller,
  hardwareStatus,
  plotterWorkspace,
  latestCapture,
  mode = "workflow",
}: PlotWorkflowPanelProps) {
  const {
    selectedAsset,
    selectionSource,
    latestRun,
    inspectedRun,
    inspectedRunId,
    recentRuns,
    pendingCaptureReview,
    busyAction,
    activeRun,
    error,
    notice,
    createBuiltInPattern,
    uploadSvg,
    startRun,
    inspectRun,
    acceptCaptureReview,
    adjustCaptureReview,
    reuseLastCaptureReview,
  } = controller;
  const [historyRunDetails, setHistoryRunDetails] = useState<Record<string, PlotRun>>({});
  const [workflowSourceOpen, setWorkflowSourceOpen] = useState(false);
  const [historySourceInspectId, setHistorySourceInspectId] = useState<string | null>(null);
  const displayRun = inspectedRun;
  const workspaceInvalidReason =
    plotterWorkspace?.is_valid === false
      ? plotterWorkspace.validation_error ??
        "Saved paper setup no longer fits the current plotter bounds."
      : null;
  const startDisabled =
    !selectedAsset ||
    activeRun ||
    busyAction === "start" ||
    workspaceInvalidReason !== null ||
    !hardwareStatus.plotter.available ||
    !hardwareStatus.camera.available ||
    hardwareStatus.plotter.busy ||
    hardwareStatus.camera.busy;
  const latestRunUsesDifferentSource =
    selectionSource === "manual" &&
    selectedAsset !== null &&
    latestRun !== null &&
    latestRun.asset.id !== selectedAsset.id;
  const blockerMessage = getWorkflowBlockerMessage({
    selectedAsset,
    hardwareStatus,
    plotterWorkspace,
    busyAction,
    activeRun,
  });
  const workflowStatus = blockerMessage
    ? { tone: "warn" as const, message: blockerMessage }
    : notice
      ? { tone: notice.tone, message: notice.message }
      : selectedAsset
        ? { tone: "success" as const, message: "Ready to start a plot run." }
        : { tone: "info" as const, message: "Stage a source to begin the plotter/camera loop." };

  useEffect(() => {
    if (latestRun) {
      setHistoryRunDetails((current) =>
        current[latestRun.id] === latestRun ? current : { ...current, [latestRun.id]: latestRun },
      );
    }
  }, [latestRun]);

  useEffect(() => {
    if (inspectedRun) {
      setHistoryRunDetails((current) =>
        current[inspectedRun.id] === inspectedRun
          ? current
          : { ...current, [inspectedRun.id]: inspectedRun },
      );
    }
  }, [inspectedRun]);

  useEffect(() => {
    setWorkflowSourceOpen(false);
  }, [displayRun?.id, selectedAsset?.id]);

  useEffect(() => {
    setHistorySourceInspectId(null);
  }, [inspectedRunId]);

  useEffect(() => {
    if (mode !== "history" || recentRuns.length === 0) {
      return;
    }

    const missingRunIds = recentRuns
      .map((run) => run.id)
      .filter((runId) => historyRunDetails[runId] === undefined);
    if (missingRunIds.length === 0) {
      return;
    }

    let cancelled = false;
    void Promise.all(
      missingRunIds.map(async (runId) => {
        try {
          const run = await fetchPlotRun(runId);
          if (cancelled) {
            return null;
          }
          return run;
        } catch {
          return null;
        }
      }),
    ).then((runs) => {
      if (cancelled) {
        return;
      }
      setHistoryRunDetails((current) => {
        const next = { ...current };
        for (const run of runs) {
          if (run) {
            next[run.id] = run;
          }
        }
        return next;
      });
    });

    return () => {
      cancelled = true;
    };
  }, [historyRunDetails, mode, recentRuns]);

  const historyRows = useMemo(
    () =>
      recentRuns.map((run) => ({
        summary: run,
        detail:
          historyRunDetails[run.id] ??
          (latestRun?.id === run.id ? latestRun : null) ??
          (inspectedRun?.id === run.id ? inspectedRun : null),
        selected: inspectedRunId === run.id,
      })),
    [historyRunDetails, inspectedRun, inspectedRunId, latestRun, recentRuns],
  );

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) {
      void uploadSvg(file);
      event.target.value = "";
    }
  }

  if (mode === "history") {
    return (
      <section className="panel history-list-panel">
        <header className="section-heading">
          <div>
            <p className="eyebrow">History</p>
            <h2>Recent runs</h2>
          </div>
        </header>
        {error ? <div className="banner">{error}</div> : null}
        {historyRows.length === 0 ? (
          <div className="empty-state">No plot runs yet.</div>
        ) : (
          <div className="history-row-list">
            {historyRows.map(({ summary, detail, selected }) => {
              const thumbnail = getHistoryRowThumbnail(detail);
              const resultCapture = detail?.observed_result?.capture ?? detail?.capture ?? null;
              const sourceInspectOpen = historySourceInspectId === summary.id;
              const title = detail?.asset.name ?? summary.asset_name;
              const meta = getExpandedMeta(detail ?? summary, formatRunKindLabel(summary.asset_kind));

              return (
                <article
                  key={summary.id}
                  className={`history-row${selected ? " history-row-selected" : ""}`}
                >
                  <button
                    type="button"
                    className="history-row-summary"
                    onClick={() => void inspectRun(summary.id)}
                  >
                    <div className="history-row-thumb">
                      {thumbnail ? (
                        <>
                          <img src={thumbnail.url} alt={thumbnail.alt} />
                          <span className="history-thumb-label">{thumbnail.label}</span>
                        </>
                      ) : (
                        <div className="empty-state history-thumb-empty">Loading preview…</div>
                      )}
                    </div>

                    <div className="history-row-copy">
                      <div className="history-row-headline">
                        <strong>{summary.asset_name}</strong>
                        <span
                          className={`status-pill status-pill-${getRunStatusTone(summary.status)}`}
                        >
                          <span className="status-pill-dot" />
                          {detail ? getStageLabel(detail) : getStatusLabel(summary.status)}
                        </span>
                      </div>
                      <p className="history-row-meta">
                        {getCollapsedRowMeta(summary, !selected)}
                      </p>
                    </div>
                  </button>

                  {selected ? (
                    <div className="history-row-detail">
                      <ExpandedRunSummary
                        title={title}
                        meta={meta}
                        status={detail ? getStageLabel(detail) : getStatusLabel(summary.status)}
                        statusTone={getRunStatusTone(summary.status)}
                        run={detail}
                        preparedImageUrl={
                          detail?.prepared_artifact
                            ? resolvePreparedArtifactUrl(detail.prepared_artifact.public_url)
                            : null
                        }
                        resultCapture={resultCapture}
                        sourceAsset={detail?.asset ?? null}
                        sourceInspectOpen={sourceInspectOpen}
                        onToggleSource={() =>
                          setHistorySourceInspectId((current) =>
                            current === summary.id ? null : summary.id,
                          )
                        }
                      />
                    </div>
                  ) : null}
                </article>
              );
            })}
          </div>
        )}
      </section>
    );
  }

  return (
    <section className="workflow-layout">
      <div className="workflow-main">
        <section className="panel workflow-command-bar">
          {error ? <div className="banner">{error}</div> : null}

          <div className="workflow-command-row">
            <div className="workflow-command-copy">
              <p className="eyebrow">Workflow</p>
              <h2>{selectedAsset ? selectedAsset.name : "No staged source"}</h2>
              <div className="workflow-command-meta">
                <span>
                  {selectedAsset ? formatRunKindLabel(selectedAsset.kind) : "Stage a source"}
                </span>
                <span>
                  Drawable area{" "}
                  {plotterWorkspace
                    ? formatPhysicalSize(
                        plotterWorkspace.drawable_area_mm.width_mm,
                        plotterWorkspace.drawable_area_mm.height_mm,
                      )
                    : "unknown"}
                </span>
              </div>
            </div>

            <div className="workflow-actions">
              <label className="button-secondary file-button">
                {busyAction === "upload" ? "Uploading..." : "Upload SVG"}
                <input
                  type="file"
                  accept=".svg,image/svg+xml"
                  onChange={onFileChange}
                  disabled={busyAction !== null}
                />
              </label>
              <button
                type="button"
                className="button-secondary"
                onClick={() => void createBuiltInPattern()}
                disabled={busyAction !== null}
              >
                {busyAction === "pattern" ? "Building..." : "Load test-grid"}
              </button>
              <button
                type="button"
                className="button-primary"
                onClick={() => void startRun()}
                disabled={startDisabled}
              >
                {busyAction === "start" ? "Starting..." : "Start plot run"}
              </button>
            </div>
          </div>

          <div className={`workflow-status-line workflow-status-line-${workflowStatus.tone}`}>
            {workflowStatus.message}
          </div>

          {latestRunUsesDifferentSource ? (
            <p className="workflow-secondary-line">
              The latest completed run used a different source: {latestRun.asset.name}.
            </p>
          ) : null}
        </section>

      <WorkflowRunSummary
        displayRun={displayRun}
        pendingCaptureReview={pendingCaptureReview}
        selectedAsset={selectedAsset}
        latestCapture={latestCapture}
        reviewBusy={busyAction === "review"}
        onAcceptCaptureReview={acceptCaptureReview}
        onAdjustCaptureReview={adjustCaptureReview}
        onReuseLastCaptureReview={reuseLastCaptureReview}
        sourceOpen={workflowSourceOpen}
        onToggleSource={() => setWorkflowSourceOpen((current) => !current)}
      />
      </div>
    </section>
  );
}
