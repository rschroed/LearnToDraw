import { useEffect, useMemo, useState, type CSSProperties } from "react";

import type { CaptureMetadata } from "../../types/hardware";
import { ArtifactCard } from "./ArtifactCard";

type CaptureVariantKey = "raw" | "normalized" | "debug";
type ComparisonMode = "side-by-side" | "overlay";

interface CaptureVariantOption {
  key: CaptureVariantKey;
  label: string;
  url: string;
}

interface RunArtifactCompareProps {
  preparedImageUrl: string | null;
  preparedAlt: string;
  preparedFooter: string | null;
  resultCapture: CaptureMetadata | null;
  resultAlt: string;
  resultFooter: string | null;
  preparedEmptyMessage: string;
  resultEmptyMessage: string;
  preparedPageAspectRatio: number | null;
}

export function isV2PageAlignedCapture(capture: CaptureMetadata | null): boolean {
  const metadata = capture?.normalized?.metadata;
  return (
    metadata?.method === "manual_corners_v2" &&
    metadata.frame?.kind === "page_aligned" &&
    metadata.frame.version === 2 &&
    metadata.frame.origin === "top-left"
  );
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
  if (selectedVariant?.key === "normalized" && !isV2PageAlignedCapture(capture)) {
    return resultFooter
      ? `${selectedVariant.label} · Legacy registration · ${resultFooter}`
      : "Normalized · Legacy registration";
  }
  if (selectedVariant && resultFooter) {
    return `${selectedVariant.label} · ${resultFooter}`;
  }
  return selectedVariant?.label ?? resultFooter;
}

function getNormalizedPageAspectRatio(capture: CaptureMetadata | null): number | null {
  if (!isV2PageAlignedCapture(capture)) {
    return null;
  }
  const frame = capture?.normalized?.metadata.frame;
  if (!frame || frame.page_width_mm <= 0 || frame.page_height_mm <= 0) {
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
  if (selectedVariant?.key !== "normalized") {
    return undefined;
  }
  const normalizedAspectRatio = getNormalizedPageAspectRatio(capture);
  if (normalizedAspectRatio !== null) {
    return { aspectRatio: `${normalizedAspectRatio}` };
  }
  const legacyAspectRatio = capture?.normalized?.metadata.output.aspect_ratio;
  return legacyAspectRatio ? { aspectRatio: `${legacyAspectRatio}` } : undefined;
}

function getCaptureVariantOptions(capture: CaptureMetadata | null): CaptureVariantOption[] {
  if (!capture) {
    return [];
  }
  const options: CaptureVariantOption[] = [
    { key: "raw", label: "Raw", url: capture.public_url },
  ];
  if (capture.normalized) {
    options.push(
      {
        key: "normalized",
        label: "Normalized",
        url: capture.normalized.rectified_grayscale_url,
      },
      { key: "debug", label: "Debug", url: capture.normalized.debug_overlay_url },
    );
  }
  return options;
}

export function RunArtifactCompare({
  preparedImageUrl,
  preparedAlt,
  preparedFooter,
  resultCapture,
  resultAlt,
  resultFooter,
  preparedEmptyMessage,
  resultEmptyMessage,
  preparedPageAspectRatio,
}: RunArtifactCompareProps) {
  const variantOptions = useMemo(
    () => getCaptureVariantOptions(resultCapture),
    [resultCapture],
  );
  const defaultVariant: CaptureVariantKey = resultCapture?.normalized ? "normalized" : "raw";
  const [resultVariant, setResultVariant] = useState<CaptureVariantKey>(defaultVariant);
  const [comparisonMode, setComparisonMode] = useState<ComparisonMode>("side-by-side");
  const [preparedOpacity, setPreparedOpacity] = useState(50);
  const overlayAvailable = Boolean(preparedImageUrl && isV2PageAlignedCapture(resultCapture));

  useEffect(() => {
    setResultVariant(defaultVariant);
    setComparisonMode("side-by-side");
  }, [defaultVariant, resultCapture?.id]);

  useEffect(() => {
    if (!overlayAvailable) {
      setComparisonMode("side-by-side");
    }
  }, [overlayAvailable]);

  const selectedVariant =
    variantOptions.find((option) => option.key === resultVariant) ?? variantOptions[0] ?? null;
  const variantFooter = getSelectedVariantFooter({
    capture: resultCapture,
    selectedVariant,
    resultFooter,
  });
  const preparedFrameStyle =
    preparedPageAspectRatio !== null ? { aspectRatio: `${preparedPageAspectRatio}` } : undefined;
  const resultFrameStyle = getSelectedVariantFrameStyle({ capture: resultCapture, selectedVariant });

  return (
    <section className="artifact-comparison-shell">
      {overlayAvailable ? (
        <div className="artifact-comparison-toolbar">
          <div className="artifact-variant-selector" role="group" aria-label="Comparison mode">
            <button
              type="button"
              className={`artifact-variant-button${
                comparisonMode === "side-by-side" ? " artifact-variant-button-active" : ""
              }`}
              aria-pressed={comparisonMode === "side-by-side"}
              onClick={() => setComparisonMode("side-by-side")}
            >
              Side by side
            </button>
            <button
              type="button"
              className={`artifact-variant-button${
                comparisonMode === "overlay" ? " artifact-variant-button-active" : ""
              }`}
              aria-pressed={comparisonMode === "overlay"}
              onClick={() => setComparisonMode("overlay")}
            >
              Overlay
            </button>
          </div>
          {comparisonMode === "overlay" ? (
            <label className="artifact-overlay-opacity">
              Intended opacity
              <input
                type="range"
                min="0"
                max="100"
                value={preparedOpacity}
                onChange={(event) => setPreparedOpacity(Number(event.target.value))}
                aria-label="Intended overlay opacity"
              />
              <span>{preparedOpacity}%</span>
            </label>
          ) : null}
        </div>
      ) : null}

      {comparisonMode === "overlay" && overlayAvailable ? (
        <div className="run-artifact-overlay">
          <ArtifactCard
            title="Intended versus observed"
            emptyMessage={resultEmptyMessage}
            footer="V2 page-aligned grayscale capture with prepared SVG overlay"
            frameStyle={preparedFrameStyle}
            frameContent={
              <div className="artifact-overlay-stack">
                <img
                  src={resultCapture?.normalized?.rectified_grayscale_url}
                  alt={`Observed ${resultAlt}`}
                />
                <img
                  className="artifact-overlay-intended"
                  src={preparedImageUrl ?? undefined}
                  alt={preparedAlt}
                  style={{ opacity: preparedOpacity / 100 }}
                />
              </div>
            }
          />
        </div>
      ) : (
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
            alt={selectedVariant ? `${selectedVariant.label.toLowerCase()} ${resultAlt}` : resultAlt}
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
                      className={`artifact-variant-button${
                        option.key === resultVariant ? " artifact-variant-button-active" : ""
                      }`}
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
      )}
    </section>
  );
}
