import type {
  CameraCaptureResponse,
  HardwareStatus,
  LatestCaptureResponse,
  PlotterCalibration,
  PlotterCalibrationResponse,
  PlotterCommandResponse,
  PlotterDeviceSettings,
  PlotterWorkspace,
  PlotterWorkspaceResponse,
} from "../types/hardware";
import type {
  LatestPlotRunResponse,
  PlotAsset,
  PlotRun,
  PlotRunListResponse,
  PlotSizingMode,
} from "../types/plotting";

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: {
      Accept: "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    const errorBody = (await response.json().catch(() => null)) as
      | { detail?: string; message?: string }
      | null;
    throw new Error(errorBody?.detail ?? errorBody?.message ?? "Request failed.");
  }

  return (await response.json()) as T;
}

export function fetchHardwareStatus() {
  return requestJson<HardwareStatus>("/api/hardware/status");
}

export function fetchLatestCapture() {
  return requestJson<LatestCaptureResponse>("/api/captures/latest");
}

export function walkPlotterHome() {
  return requestJson<PlotterCommandResponse>("/api/plotter/walk-home", {
    method: "POST",
  });
}

export function runPlotterTestAction(action: string) {
  return requestJson<PlotterCommandResponse>("/api/plotter/test-actions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ action }),
  });
}

export function setPlotterPenHeights(penPosUp: number, penPosDown: number) {
  return requestJson<PlotterCommandResponse>("/api/plotter/pen-heights", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      pen_pos_up: penPosUp,
      pen_pos_down: penPosDown,
    }),
  });
}

export function fetchPlotterCalibration() {
  return requestJson<PlotterCalibration>("/api/plotter/calibration");
}

export function fetchPlotterDevice() {
  return requestJson<PlotterDeviceSettings>("/api/plotter/device");
}

export function setPlotterCalibration(nativeResFactor: number) {
  return requestJson<PlotterCalibrationResponse>("/api/plotter/calibration", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      native_res_factor: nativeResFactor,
    }),
  });
}

export function fetchPlotterWorkspace() {
  return requestJson<PlotterWorkspace>("/api/plotter/workspace");
}

export function setPlotterWorkspace(workspace: {
  page_width_mm: number;
  page_height_mm: number;
  margin_left_mm: number;
  margin_top_mm: number;
  margin_right_mm: number;
  margin_bottom_mm: number;
}) {
  return requestJson<PlotterWorkspaceResponse>("/api/plotter/workspace", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(workspace),
  });
}

export function captureImage() {
  return requestJson<CameraCaptureResponse>("/api/camera/capture", {
    method: "POST",
  });
}

export function uploadPlotAsset(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  return requestJson<PlotAsset>("/api/plot-assets/upload", {
    method: "POST",
    body: formData,
  });
}

export function createPatternAsset(patternId: string) {
  return requestJson<PlotAsset>("/api/plot-assets/patterns", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ pattern_id: patternId }),
  });
}

export function createPlotRun(
  assetId: string,
  options?: {
    purpose?: "normal" | "diagnostic";
    capture_mode?: "auto" | "skip";
    sizing_mode?: PlotSizingMode;
  },
) {
  return requestJson<PlotRun>("/api/plot-runs", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      asset_id: assetId,
      purpose: options?.purpose ?? "normal",
      capture_mode: options?.capture_mode ?? "auto",
      sizing_mode: options?.sizing_mode ?? "native",
    }),
  });
}

export function fetchLatestPlotRun() {
  return requestJson<LatestPlotRunResponse>("/api/plot-runs/latest");
}

export function fetchPlotRuns() {
  return requestJson<PlotRunListResponse>("/api/plot-runs");
}
