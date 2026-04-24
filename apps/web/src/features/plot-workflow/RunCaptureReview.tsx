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
  onAccept: () => Promise<void>;
  onAdjust: (corners: NormalizationCorners) => Promise<void>;
  onReuseLast: () => Promise<void>;
}

export function RunCaptureReview({
  run,
  preparedImageUrl,
  preparedPageAspectRatio,
  reviewCapture,
  review,
  reviewBusy,
  onAccept,
  onAdjust,
  onReuseLast,
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
