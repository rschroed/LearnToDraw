import { useEffect, useMemo, useState, type CSSProperties } from "react";

import type { CaptureMetadata } from "../../types/hardware";
import { ArtifactCard } from "./ArtifactCard";

type CaptureVariantKey = "raw" | "normalized" | "debug";

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
    return resultFooter
      ? `${selectedVariant.label} · Legacy frame · ${resultFooter}`
      : "Normalized · Legacy frame";
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
