export interface PenHeightValues {
  penPosUp: string;
  penPosDown: string;
}

export interface CalibrationValue {
  nativeResFactor: string;
}

export interface SafeBoundsValues {
  widthMm: string;
  heightMm: string;
}

export interface WorkspaceValues {
  pageWidthMm: string;
  pageHeightMm: string;
  marginLeftMm: string;
  marginTopMm: string;
  marginRightMm: string;
  marginBottomMm: string;
}

export interface WorkspaceMetrics {
  hasBlank: boolean;
  allFinite: boolean;
  pageWidthMm: number | null;
  pageHeightMm: number | null;
  marginLeftMm: number | null;
  marginTopMm: number | null;
  marginRightMm: number | null;
  marginBottomMm: number | null;
  drawableWidthMm: number | null;
  drawableHeightMm: number | null;
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function formatLabel(value: string) {
  return value.replace(/_/g, " ");
}

export function arePenHeightsEqual(
  left: PenHeightValues | null,
  right: PenHeightValues | null,
) {
  return left?.penPosUp === right?.penPosUp && left?.penPosDown === right?.penPosDown;
}

export function areCalibrationValuesEqual(
  left: CalibrationValue | null,
  right: CalibrationValue | null,
) {
  return left?.nativeResFactor === right?.nativeResFactor;
}

export function areSafeBoundsValuesEqual(
  left: SafeBoundsValues | null,
  right: SafeBoundsValues | null,
) {
  return left?.widthMm === right?.widthMm && left?.heightMm === right?.heightMm;
}

export function areWorkspaceValuesEqual(
  left: WorkspaceValues | null,
  right: WorkspaceValues | null,
) {
  return (
    left?.pageWidthMm === right?.pageWidthMm &&
    left?.pageHeightMm === right?.pageHeightMm &&
    left?.marginLeftMm === right?.marginLeftMm &&
    left?.marginTopMm === right?.marginTopMm &&
    left?.marginRightMm === right?.marginRightMm &&
    left?.marginBottomMm === right?.marginBottomMm
  );
}

export function getPenHeightValidation(
  penPosUp: string,
  penPosDown: string,
): string | null {
  if (penPosUp.trim() === "" || penPosDown.trim() === "") {
    return "Enter both pen heights before applying them.";
  }

  const parsedPenPosUp = Number(penPosUp);
  const parsedPenPosDown = Number(penPosDown);

  if (!Number.isFinite(parsedPenPosUp) || !Number.isFinite(parsedPenPosDown)) {
    return "Pen heights must be numeric values.";
  }

  if (
    parsedPenPosUp < 0 ||
    parsedPenPosUp > 100 ||
    parsedPenPosDown < 0 ||
    parsedPenPosDown > 100
  ) {
    return "Pen heights must stay between 0 and 100.";
  }

  if (parsedPenPosDown >= parsedPenPosUp) {
    return "Pen down must be lower than pen up.";
  }

  return null;
}

export function getCalibrationValidation(nativeResFactor: string): string | null {
  if (nativeResFactor.trim() === "") {
    return "Enter a native resolution factor before saving.";
  }

  const parsedNativeResFactor = Number(nativeResFactor);
  if (!Number.isFinite(parsedNativeResFactor)) {
    return "Native resolution factor must be numeric.";
  }

  if (parsedNativeResFactor <= 0) {
    return "Native resolution factor must be greater than zero.";
  }

  return null;
}

export function getSafeBoundsValidation(
  safeBounds: SafeBoundsValues,
  nominalBounds: { width_mm: number; height_mm: number } | null,
): string | null {
  if (safeBounds.widthMm.trim() === "" || safeBounds.heightMm.trim() === "") {
    return "Enter both operational safe bounds before saving.";
  }

  const widthMm = Number(safeBounds.widthMm);
  const heightMm = Number(safeBounds.heightMm);
  if (!Number.isFinite(widthMm) || !Number.isFinite(heightMm)) {
    return "Operational safe bounds must be numeric values.";
  }
  if (widthMm <= 0 || heightMm <= 0) {
    return "Operational safe bounds must be greater than zero.";
  }
  if (
    nominalBounds &&
    (widthMm > nominalBounds.width_mm || heightMm > nominalBounds.height_mm)
  ) {
    return `Operational safe bounds cannot exceed nominal machine bounds of ${nominalBounds.width_mm} x ${nominalBounds.height_mm} mm.`;
  }
  return null;
}

export function getWorkspaceValidation(
  workspace: WorkspaceMetrics,
  plotterBounds: { width_mm: number; height_mm: number } | null,
): string | null {
  if (workspace.hasBlank) {
    return "Enter page size and margins before saving workspace setup.";
  }

  if (!workspace.allFinite) {
    return "Page size and margins must be numeric values.";
  }

  if (
    workspace.pageWidthMm === null ||
    workspace.pageHeightMm === null ||
    workspace.marginLeftMm === null ||
    workspace.marginTopMm === null ||
    workspace.marginRightMm === null ||
    workspace.marginBottomMm === null ||
    workspace.drawableWidthMm === null ||
    workspace.drawableHeightMm === null
  ) {
    return "Enter page size and margins before saving workspace setup.";
  }

  if (workspace.pageWidthMm <= 0 || workspace.pageHeightMm <= 0) {
    return "Page width and height must be greater than zero.";
  }

  if (
    workspace.marginLeftMm < 0 ||
    workspace.marginTopMm < 0 ||
    workspace.marginRightMm < 0 ||
    workspace.marginBottomMm < 0
  ) {
    return "Margins cannot be negative.";
  }

  if (workspace.drawableWidthMm <= 0 || workspace.drawableHeightMm <= 0) {
    return "Safe margins leave no drawable area. Reduce the margins or increase the paper size.";
  }

  if (
    plotterBounds &&
    (workspace.pageWidthMm > plotterBounds.width_mm ||
      workspace.pageHeightMm > plotterBounds.height_mm)
  ) {
    return `Paper size exceeds the plotter's safe bounds of ${plotterBounds.width_mm} x ${plotterBounds.height_mm} mm.`;
  }

  return null;
}

export function getWorkspaceMetrics(workspace: WorkspaceValues): WorkspaceMetrics {
  const hasBlank = Object.values(workspace).some((value) => value.trim() === "");
  const pageWidthMm = Number(workspace.pageWidthMm);
  const pageHeightMm = Number(workspace.pageHeightMm);
  const marginLeftMm = Number(workspace.marginLeftMm);
  const marginTopMm = Number(workspace.marginTopMm);
  const marginRightMm = Number(workspace.marginRightMm);
  const marginBottomMm = Number(workspace.marginBottomMm);
  const allFinite = [
    pageWidthMm,
    pageHeightMm,
    marginLeftMm,
    marginTopMm,
    marginRightMm,
    marginBottomMm,
  ].every((value) => Number.isFinite(value));

  return {
    hasBlank,
    allFinite,
    pageWidthMm: allFinite ? pageWidthMm : null,
    pageHeightMm: allFinite ? pageHeightMm : null,
    marginLeftMm: allFinite ? marginLeftMm : null,
    marginTopMm: allFinite ? marginTopMm : null,
    marginRightMm: allFinite ? marginRightMm : null,
    marginBottomMm: allFinite ? marginBottomMm : null,
    drawableWidthMm: allFinite ? pageWidthMm - marginLeftMm - marginRightMm : null,
    drawableHeightMm: allFinite ? pageHeightMm - marginTopMm - marginBottomMm : null,
  };
}

export function formatMm(value: number | null) {
  if (value === null) {
    return "unknown";
  }
  return `${value.toFixed(1).replace(/\.0$/, "")} mm`;
}
