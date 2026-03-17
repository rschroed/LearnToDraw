interface PlotterWorkspacePreviewProps {
  pageWidthMm: number | null;
  pageHeightMm: number | null;
  marginLeftMm: number | null;
  marginTopMm: number | null;
  marginRightMm: number | null;
  marginBottomMm: number | null;
  drawableWidthMm: number | null;
  drawableHeightMm: number | null;
  isValid: boolean;
}

function formatPreviewMm(value: number | null) {
  if (value === null) {
    return "unknown";
  }

  return value.toFixed(1).replace(/\.0$/, "");
}

export function PlotterWorkspacePreview({
  pageWidthMm,
  pageHeightMm,
  marginLeftMm,
  marginTopMm,
  marginRightMm,
  marginBottomMm,
  drawableWidthMm,
  drawableHeightMm,
  isValid,
}: PlotterWorkspacePreviewProps) {
  const previewWidth = 320;
  const previewHeight = 280;

  if (
    pageWidthMm === null ||
    pageHeightMm === null ||
    marginLeftMm === null ||
    marginTopMm === null ||
    marginRightMm === null ||
    marginBottomMm === null
  ) {
    return (
      <div className="workspace-preview-empty" aria-label="Paper setup preview">
        Enter page size and margins to preview the drawable area.
      </div>
    );
  }

  const scale = Math.min(previewWidth / pageWidthMm, previewHeight / pageHeightMm);
  const paperWidth = Math.max(24, pageWidthMm * scale);
  const paperHeight = Math.max(24, pageHeightMm * scale);
  const offsetX = (previewWidth - paperWidth) / 2;
  const offsetY = (previewHeight - paperHeight) / 2;
  const drawableX = offsetX + Math.max(0, marginLeftMm * scale);
  const drawableY = offsetY + Math.max(0, marginTopMm * scale);
  const drawableWidth =
    drawableWidthMm !== null ? Math.max(0, drawableWidthMm * scale) : 0;
  const drawableHeight =
    drawableHeightMm !== null ? Math.max(0, drawableHeightMm * scale) : 0;
  const centerLabelX = drawableX + drawableWidth / 2;
  const centerLabelY = drawableY + drawableHeight / 2;
  const topMarginLabelX = drawableX + drawableWidth / 2;
  const topMarginLabelY = Math.max(offsetY + 14, drawableY - 10);
  const bottomMarginLabelX = drawableX + drawableWidth / 2;
  const bottomMarginLabelY = Math.min(
    offsetY + paperHeight - 10,
    drawableY + drawableHeight + 18,
  );
  const leftMarginLabelX = Math.max(offsetX + 14, drawableX - 14);
  const leftMarginLabelY = drawableY + drawableHeight / 2;
  const rightMarginLabelX = Math.min(
    offsetX + paperWidth - 14,
    drawableX + drawableWidth + 14,
  );
  const rightMarginLabelY = drawableY + drawableHeight / 2;

  return (
    <div className="workspace-preview">
      <svg
        aria-label="Paper setup preview"
        className="workspace-preview-svg"
        viewBox={`0 0 ${previewWidth} ${previewHeight}`}
        role="img"
      >
        <rect
          x={offsetX}
          y={offsetY}
          width={paperWidth}
          height={paperHeight}
          rx="10"
          className="workspace-preview-paper"
        />
        {isValid ? (
          <>
            <rect
              x={drawableX}
              y={drawableY}
              width={drawableWidth}
              height={drawableHeight}
              rx="8"
              className="workspace-preview-drawable"
            />
            {drawableWidth > 72 && drawableHeight > 32 ? (
              <text
                x={centerLabelX}
                y={centerLabelY}
                className="workspace-preview-label"
                textAnchor="middle"
              >
                {formatPreviewMm(drawableWidthMm)} x {formatPreviewMm(drawableHeightMm)} mm
              </text>
            ) : null}
            {marginTopMm > 0 && drawableHeight > 44 ? (
              <text
                x={topMarginLabelX}
                y={topMarginLabelY}
                className="workspace-preview-margin-label"
                textAnchor="middle"
              >
                T {formatPreviewMm(marginTopMm)}
              </text>
            ) : null}
            {marginBottomMm > 0 && drawableHeight > 44 ? (
              <text
                x={bottomMarginLabelX}
                y={bottomMarginLabelY}
                className="workspace-preview-margin-label"
                textAnchor="middle"
              >
                B {formatPreviewMm(marginBottomMm)}
              </text>
            ) : null}
            {marginLeftMm > 0 && drawableWidth > 64 ? (
              <text
                x={leftMarginLabelX}
                y={leftMarginLabelY}
                className="workspace-preview-margin-label"
                textAnchor="middle"
                dominantBaseline="middle"
              >
                L {formatPreviewMm(marginLeftMm)}
              </text>
            ) : null}
            {marginRightMm > 0 && drawableWidth > 64 ? (
              <text
                x={rightMarginLabelX}
                y={rightMarginLabelY}
                className="workspace-preview-margin-label"
                textAnchor="middle"
                dominantBaseline="middle"
              >
                R {formatPreviewMm(marginRightMm)}
              </text>
            ) : null}
          </>
        ) : (
          <g className="workspace-preview-invalid">
            <line
              x1={offsetX + 14}
              y1={offsetY + 14}
              x2={offsetX + paperWidth - 14}
              y2={offsetY + paperHeight - 14}
            />
            <line
              x1={offsetX + paperWidth - 14}
              y1={offsetY + 14}
              x2={offsetX + 14}
              y2={offsetY + paperHeight - 14}
            />
          </g>
        )}
      </svg>
      <div className="workspace-preview-legend">
        <span>
          <span className="workspace-preview-swatch workspace-preview-swatch-paper" />
          Paper {formatPreviewMm(pageWidthMm)} x {formatPreviewMm(pageHeightMm)} mm
        </span>
        <span>
          <span className="workspace-preview-swatch workspace-preview-swatch-drawable" />
          Drawable area {formatPreviewMm(drawableWidthMm)} x {formatPreviewMm(drawableHeightMm)} mm
        </span>
      </div>
      <div className="workspace-preview-values">
        <span>Safe margins</span>
        <strong>
          L {formatPreviewMm(marginLeftMm)} · T {formatPreviewMm(marginTopMm)} · R{" "}
          {formatPreviewMm(marginRightMm)} · B {formatPreviewMm(marginBottomMm)} mm
        </strong>
      </div>
    </div>
  );
}
