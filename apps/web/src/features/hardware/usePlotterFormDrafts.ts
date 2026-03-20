import { useEffect, useState } from "react";

import type {
  PlotterDeviceSettings,
  PlotterWorkspace,
} from "../../types/hardware";
import type { ActionFeedback } from "./hardwareDashboardTypes";
import {
  areCalibrationValuesEqual,
  arePenHeightsEqual,
  areSafeBoundsValuesEqual,
  areWorkspaceValuesEqual,
  type CalibrationValue,
  type PenHeightValues,
  type SafeBoundsValues,
  type WorkspaceValues,
} from "./hardwareDashboardUtils";


export function usePlotterFormDrafts({
  polledPenHeights,
  effectiveNativeResFactor,
  plotterDevice,
  plotterWorkspace,
  actionFeedback,
}: {
  polledPenHeights: PenHeightValues | null;
  effectiveNativeResFactor: string | null;
  plotterDevice: PlotterDeviceSettings | null;
  plotterWorkspace: PlotterWorkspace | null;
  actionFeedback: ActionFeedback | null;
}) {
  const [penPosUp, setPenPosUp] = useState("60");
  const [penPosDown, setPenPosDown] = useState("30");
  const [isPenHeightDirty, setIsPenHeightDirty] = useState(false);
  const [lastSyncedPenHeights, setLastSyncedPenHeights] =
    useState<PenHeightValues | null>(null);
  const [pendingAppliedPenHeights, setPendingAppliedPenHeights] =
    useState<PenHeightValues | null>(null);
  const [nativeResFactor, setNativeResFactor] = useState("1016");
  const [isCalibrationDirty, setIsCalibrationDirty] = useState(false);
  const [lastSyncedCalibration, setLastSyncedCalibration] =
    useState<CalibrationValue | null>(null);
  const [pendingAppliedCalibration, setPendingAppliedCalibration] =
    useState<CalibrationValue | null>(null);
  const [safeBoundsValues, setSafeBoundsValues] = useState<SafeBoundsValues>({
    widthMm: "200",
    heightMm: "200",
  });
  const [isSafeBoundsDirty, setIsSafeBoundsDirty] = useState(false);
  const [lastSyncedSafeBounds, setLastSyncedSafeBounds] =
    useState<SafeBoundsValues | null>(null);
  const [pendingAppliedSafeBounds, setPendingAppliedSafeBounds] =
    useState<SafeBoundsValues | null>(null);
  const [workspaceValues, setWorkspaceValues] = useState<WorkspaceValues>({
    pageWidthMm: "210",
    pageHeightMm: "297",
    marginLeftMm: "20",
    marginTopMm: "20",
    marginRightMm: "20",
    marginBottomMm: "20",
  });
  const [isWorkspaceDirty, setIsWorkspaceDirty] = useState(false);
  const [lastSyncedWorkspace, setLastSyncedWorkspace] =
    useState<WorkspaceValues | null>(null);
  const [pendingAppliedWorkspace, setPendingAppliedWorkspace] =
    useState<WorkspaceValues | null>(null);

  const calibrationValue = effectiveNativeResFactor
    ? { nativeResFactor: effectiveNativeResFactor }
    : null;
  const currentWorkspaceValue =
    plotterWorkspace !== null
      ? {
          pageWidthMm: String(plotterWorkspace.page_size_mm.width_mm),
          pageHeightMm: String(plotterWorkspace.page_size_mm.height_mm),
          marginLeftMm: String(plotterWorkspace.margins_mm.left_mm),
          marginTopMm: String(plotterWorkspace.margins_mm.top_mm),
          marginRightMm: String(plotterWorkspace.margins_mm.right_mm),
          marginBottomMm: String(plotterWorkspace.margins_mm.bottom_mm),
        }
      : null;
  const currentSafeBoundsValue =
    plotterDevice !== null
      ? {
          widthMm: String(plotterDevice.plotter_bounds_mm.width_mm),
          heightMm: String(plotterDevice.plotter_bounds_mm.height_mm),
        }
      : null;

  useEffect(() => {
    if (!polledPenHeights) {
      return;
    }

    const shouldSyncDraft =
      lastSyncedPenHeights === null ||
      !isPenHeightDirty ||
      arePenHeightsEqual(pendingAppliedPenHeights, polledPenHeights);

    if (!shouldSyncDraft) {
      return;
    }

    if (
      penPosUp !== polledPenHeights.penPosUp ||
      penPosDown !== polledPenHeights.penPosDown
    ) {
      setPenPosUp(polledPenHeights.penPosUp);
      setPenPosDown(polledPenHeights.penPosDown);
    }

    if (!arePenHeightsEqual(lastSyncedPenHeights, polledPenHeights)) {
      setLastSyncedPenHeights(polledPenHeights);
    }

    if (arePenHeightsEqual(pendingAppliedPenHeights, polledPenHeights)) {
      setIsPenHeightDirty(false);
      setPendingAppliedPenHeights(null);
    }
  }, [
    isPenHeightDirty,
    lastSyncedPenHeights,
    pendingAppliedPenHeights,
    penPosDown,
    penPosUp,
    polledPenHeights,
  ]);

  useEffect(() => {
    if (
      actionFeedback?.action === "plotter-pen-heights" &&
      actionFeedback.tone === "error"
    ) {
      setPendingAppliedPenHeights(null);
    }
  }, [actionFeedback]);

  useEffect(() => {
    if (!calibrationValue) {
      return;
    }

    const shouldSyncDraft =
      lastSyncedCalibration === null ||
      !isCalibrationDirty ||
      areCalibrationValuesEqual(pendingAppliedCalibration, calibrationValue);

    if (!shouldSyncDraft) {
      return;
    }

    if (nativeResFactor !== calibrationValue.nativeResFactor) {
      setNativeResFactor(calibrationValue.nativeResFactor);
    }

    if (!areCalibrationValuesEqual(lastSyncedCalibration, calibrationValue)) {
      setLastSyncedCalibration(calibrationValue);
    }

    if (areCalibrationValuesEqual(pendingAppliedCalibration, calibrationValue)) {
      setIsCalibrationDirty(false);
      setPendingAppliedCalibration(null);
    }
  }, [
    calibrationValue,
    isCalibrationDirty,
    lastSyncedCalibration,
    nativeResFactor,
    pendingAppliedCalibration,
  ]);

  useEffect(() => {
    if (
      actionFeedback?.action === "plotter-calibration" &&
      actionFeedback.tone === "error"
    ) {
      setPendingAppliedCalibration(null);
    }
  }, [actionFeedback]);

  useEffect(() => {
    if (!currentSafeBoundsValue) {
      return;
    }

    const shouldSyncDraft =
      lastSyncedSafeBounds === null ||
      !isSafeBoundsDirty ||
      areSafeBoundsValuesEqual(pendingAppliedSafeBounds, currentSafeBoundsValue);

    if (!shouldSyncDraft) {
      return;
    }

    if (!areSafeBoundsValuesEqual(safeBoundsValues, currentSafeBoundsValue)) {
      setSafeBoundsValues(currentSafeBoundsValue);
    }

    if (!areSafeBoundsValuesEqual(lastSyncedSafeBounds, currentSafeBoundsValue)) {
      setLastSyncedSafeBounds(currentSafeBoundsValue);
    }

    if (areSafeBoundsValuesEqual(pendingAppliedSafeBounds, currentSafeBoundsValue)) {
      setIsSafeBoundsDirty(false);
      setPendingAppliedSafeBounds(null);
    }
  }, [
    currentSafeBoundsValue,
    isSafeBoundsDirty,
    lastSyncedSafeBounds,
    pendingAppliedSafeBounds,
    safeBoundsValues,
  ]);

  useEffect(() => {
    if (
      actionFeedback?.action === "plotter-safe-bounds" &&
      actionFeedback.tone === "error"
    ) {
      setPendingAppliedSafeBounds(null);
    }
  }, [actionFeedback]);

  useEffect(() => {
    if (!currentWorkspaceValue) {
      return;
    }

    const shouldSyncDraft =
      lastSyncedWorkspace === null ||
      !isWorkspaceDirty ||
      areWorkspaceValuesEqual(pendingAppliedWorkspace, currentWorkspaceValue);

    if (!shouldSyncDraft) {
      return;
    }

    if (!areWorkspaceValuesEqual(workspaceValues, currentWorkspaceValue)) {
      setWorkspaceValues(currentWorkspaceValue);
    }

    if (!areWorkspaceValuesEqual(lastSyncedWorkspace, currentWorkspaceValue)) {
      setLastSyncedWorkspace(currentWorkspaceValue);
    }

    if (areWorkspaceValuesEqual(pendingAppliedWorkspace, currentWorkspaceValue)) {
      setIsWorkspaceDirty(false);
      setPendingAppliedWorkspace(null);
    }
  }, [
    currentWorkspaceValue,
    isWorkspaceDirty,
    lastSyncedWorkspace,
    pendingAppliedWorkspace,
    workspaceValues,
  ]);

  useEffect(() => {
    if (
      actionFeedback?.action === "plotter-workspace" &&
      actionFeedback.tone === "error"
    ) {
      setPendingAppliedWorkspace(null);
    }
  }, [actionFeedback]);

  return {
    penPosUp,
    penPosDown,
    nativeResFactor,
    safeBoundsValues,
    workspaceValues,
    penHeightsSynced: arePenHeightsEqual(
      { penPosUp, penPosDown },
      lastSyncedPenHeights,
    ),
    calibrationSynced: areCalibrationValuesEqual(
      { nativeResFactor },
      lastSyncedCalibration,
    ),
    safeBoundsSynced: areSafeBoundsValuesEqual(
      safeBoundsValues,
      lastSyncedSafeBounds,
    ),
    workspaceSynced: areWorkspaceValuesEqual(
      workspaceValues,
      lastSyncedWorkspace,
    ),
    setPenDraft(nextValues: PenHeightValues) {
      setPenPosUp(nextValues.penPosUp);
      setPenPosDown(nextValues.penPosDown);
      setIsPenHeightDirty(!arePenHeightsEqual(nextValues, lastSyncedPenHeights));
    },
    setCalibrationDraft(nextValue: string) {
      setNativeResFactor(nextValue);
      setIsCalibrationDirty(
        !areCalibrationValuesEqual(
          { nativeResFactor: nextValue },
          lastSyncedCalibration,
        ),
      );
    },
    setSafeBoundsDraft(nextValues: SafeBoundsValues) {
      setSafeBoundsValues(nextValues);
      setIsSafeBoundsDirty(!areSafeBoundsValuesEqual(nextValues, lastSyncedSafeBounds));
    },
    setWorkspaceDraft(nextValues: WorkspaceValues) {
      setWorkspaceValues(nextValues);
      setIsWorkspaceDirty(!areWorkspaceValuesEqual(nextValues, lastSyncedWorkspace));
    },
    stagePenHeightsApply() {
      setPendingAppliedPenHeights({ penPosUp, penPosDown });
    },
    stageCalibrationApply() {
      setPendingAppliedCalibration({ nativeResFactor });
    },
    stageSafeBoundsApply() {
      setPendingAppliedSafeBounds(safeBoundsValues);
    },
    clearPendingSafeBoundsApply() {
      setPendingAppliedSafeBounds(null);
    },
    stageWorkspaceApply() {
      setPendingAppliedWorkspace(workspaceValues);
    },
  };
}
