import { useState } from "react";

import {
  fetchHardwareStatus,
  fetchLatestCapture,
  fetchPlotterCalibration,
  fetchPlotterDevice,
  fetchPlotterWorkspace,
} from "../../lib/api";
import type {
  CaptureMetadata,
  HardwareStatus,
  PlotterCalibration,
  PlotterDeviceSettings,
  PlotterWorkspace,
} from "../../types/hardware";
import type { HardwareSnapshot } from "./hardwareDashboardTypes";

export function useHardwareSnapshotState() {
  const [hardwareStatus, setHardwareStatus] = useState<HardwareStatus | null>(null);
  const [plotterCalibration, setPlotterCalibrationState] =
    useState<PlotterCalibration | null>(null);
  const [plotterDevice, setPlotterDeviceState] =
    useState<PlotterDeviceSettings | null>(null);
  const [plotterWorkspace, setPlotterWorkspaceState] =
    useState<PlotterWorkspace | null>(null);
  const [latestCapture, setLatestCapture] = useState<CaptureMetadata | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  function clearHardwareState() {
    setHardwareStatus(null);
    setPlotterCalibrationState(null);
    setPlotterDeviceState(null);
    setPlotterWorkspaceState(null);
    setLatestCapture(null);
  }

  function applyHardwareSnapshot(snapshot: HardwareSnapshot) {
    setHardwareStatus(snapshot.status);
    setPlotterCalibrationState(snapshot.calibration);
    setPlotterDeviceState(snapshot.device);
    setPlotterWorkspaceState(snapshot.workspace);
    setLatestCapture(snapshot.latest.capture);
  }

  async function fetchHardwareSnapshot() {
    const [status, calibration, device, workspace, latest] = await Promise.all([
      fetchHardwareStatus(),
      fetchPlotterCalibration(),
      fetchPlotterDevice(),
      fetchPlotterWorkspace(),
      fetchLatestCapture(),
    ]);
    return { status, calibration, device, workspace, latest };
  }

  return {
    hardwareStatus,
    plotterCalibration,
    plotterDevice,
    plotterWorkspace,
    latestCapture,
    loading,
    refreshing,
    setPlotterCalibrationState,
    setPlotterDeviceState,
    setPlotterWorkspaceState,
    setLoading,
    setRefreshing,
    clearHardwareState,
    applyHardwareSnapshot,
    fetchHardwareSnapshot,
  };
}
