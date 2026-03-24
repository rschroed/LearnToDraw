import type {
  CameraCommandResponse,
  CameraCaptureResponse,
  HardwareStatus,
  LatestCaptureResponse,
  PlotterCalibration,
  PlotterCalibrationResponse,
  PlotterCommandResponse,
  PlotterDeviceSettings,
  PlotterDeviceSettingsResponse,
  PlotterWorkspace,
  PlotterWorkspaceResponse,
} from "../types/hardware";
import type {
  LatestPlotRunResponse,
  PlotAsset,
  PlotRun,
  PlotRunListResponse,
} from "../types/plotting";
import type { HelperStatus } from "../types/helper";

const REQUEST_TIMEOUT_MS = 2000;
const HELPER_OPEN_URL = "learntodraw-helper://open";
const CAMERABRIDGE_PERMISSION_URL = "camerabridge://permission";

export class ApiRequestError extends Error {
  readonly statusCode: number | null;
  readonly isNetworkError: boolean;

  constructor(
    message: string,
    {
      statusCode = null,
      isNetworkError = false,
    }: {
      statusCode?: number | null;
      isNetworkError?: boolean;
    } = {},
  ) {
    super(message);
    this.name = "ApiRequestError";
    this.statusCode = statusCode;
    this.isNetworkError = isNetworkError;
  }
}

export function isNetworkRequestError(error: unknown): error is ApiRequestError {
  return error instanceof ApiRequestError && error.isNetworkError;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => {
    controller.abort("timeout");
  }, REQUEST_TIMEOUT_MS);
  const externalSignal = init?.signal;
  const abortFromExternalSignal = () => {
    controller.abort(externalSignal?.reason);
  };

  if (externalSignal) {
    if (externalSignal.aborted) {
      abortFromExternalSignal();
    } else {
      externalSignal.addEventListener("abort", abortFromExternalSignal, {
        once: true,
      });
    }
  }

  let response: Response;
  try {
    response = await fetch(path, {
      headers: {
        Accept: "application/json",
        ...(init?.headers ?? {}),
      },
      ...init,
      signal: controller.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiRequestError("Local service timed out.", {
        isNetworkError: true,
      });
    }
    throw new ApiRequestError("Unable to reach the local service.", {
      isNetworkError: true,
    });
  } finally {
    window.clearTimeout(timeoutId);
    if (externalSignal) {
      externalSignal.removeEventListener("abort", abortFromExternalSignal);
    }
  }

  if (!response.ok) {
    const contentType = response.headers.get("Content-Type");
    const errorBody = (await response.json().catch(() => null)) as
      | { detail?: string; message?: string }
      | null;
    const isProxyConnectionFailure =
      response.status >= 500 &&
      contentType?.startsWith("text/plain") === true &&
      errorBody === null;

    if (isProxyConnectionFailure) {
      throw new ApiRequestError("Unable to reach the local service.", {
        statusCode: response.status,
        isNetworkError: true,
      });
    }

    throw new ApiRequestError(
      errorBody?.detail ?? errorBody?.message ?? "Request failed.",
      {
        statusCode: response.status,
      },
    );
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

export function setPlotterSafeBounds(
  safeBounds: {
    width_mm: number | null;
    height_mm: number | null;
  },
) {
  return requestJson<PlotterDeviceSettingsResponse>("/api/plotter/device/safe-bounds", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(safeBounds),
  });
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

export function setCameraDevice(deviceId: string | null) {
  return requestJson<CameraCommandResponse>("/api/camera/device", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      device_id: deviceId,
    }),
  });
}

export function openCameraBridgeApp() {
  window.location.assign(CAMERABRIDGE_PERMISSION_URL);
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
    }),
  });
}

export function fetchLatestPlotRun() {
  return requestJson<LatestPlotRunResponse>("/api/plot-runs/latest");
}

export function fetchPlotRuns() {
  return requestJson<PlotRunListResponse>("/api/plot-runs");
}

export function fetchPlotRun(runId: string) {
  return requestJson<PlotRun>(`/api/plot-runs/${runId}`);
}

export function fetchHelperStatus() {
  return requestJson<HelperStatus>("/local-helper/status");
}

export function startHelperBackend() {
  return requestJson<HelperStatus>("/local-helper/start", {
    method: "POST",
  });
}

export function restartHelperBackend() {
  return requestJson<HelperStatus>("/local-helper/restart", {
    method: "POST",
  });
}

export function openHelperApp() {
  window.location.assign(HELPER_OPEN_URL);
}
