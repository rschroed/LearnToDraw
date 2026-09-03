import type {
  CaptureMetadata,
  CaptureReview,
  NormalizationCorners,
} from "../../types/hardware";
import type { PlotRun } from "../../types/plotting";
import { ArtifactCard } from "./ArtifactCard";
import { CaptureReviewEditor } from "./CaptureReviewEditor";

interface RunCaptureReviewProps {
  run: PlotRun;
  preparedImageUrl: string | null;
  preparedPageAspectRatio: number | null;
  reviewCapture: CaptureMetadata;
  review: CaptureReview;
  reviewBusy: boolean;
  reviewError: string | null;
  revision?: boolean;
  onCancel?: () => void;
  onConfirm: (corners: NormalizationCorners) => Promise<void>;
}

export function RunCaptureReview({
  run,
  preparedImageUrl,
  preparedPageAspectRatio,
  reviewCapture,
  review,
  reviewBusy,
  reviewError,
  revision = false,
  onCancel,
  onConfirm,
}: RunCaptureReviewProps) {
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
          <h3>{revision ? "Adjust registration" : "Review capture"}</h3>
        </header>
        <div className="artifact-frame artifact-frame-review">
          <CaptureReviewEditor
            capture={reviewCapture}
            review={review}
            busy={reviewBusy}
            error={reviewError}
            revision={revision}
            onCancel={onCancel}
            onConfirm={onConfirm}
          />
        </div>
        <p className="artifact-footer">
          {revision
            ? "Saving regenerates this capture's page-aligned artifacts without plotting again."
            : "Processing continues after you confirm all four page corners."}
        </p>
      </article>
    </div>
  );
}
