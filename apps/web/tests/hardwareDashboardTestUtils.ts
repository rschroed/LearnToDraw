import { act } from "@testing-library/react";

import { HARDWARE_DASHBOARD_POLL_INTERVAL_MS } from "../src/features/hardware/useHardwareDashboard";
import {
  PLOT_WORKFLOW_ACTIVE_POLL_INTERVAL_MS,
  PLOT_WORKFLOW_IDLE_POLL_INTERVAL_MS,
} from "../src/features/plot-workflow/usePlotWorkflow";
import type {
  CaptureMetadata,
  HardwareStatus,
  PlotterCalibration,
  PlotterDeviceSettings,
  PlotterWorkspace,
} from "../src/types/hardware";
import type { HelperStatus } from "../src/types/helper";

export const defaultHardwareStatus: HardwareStatus = {
  plotter: {
    available: true,
    connected: true,
    busy: false,
    error: null,
    driver: "mock-plotter",
    last_updated: "2026-03-15T20:00:00Z",
    details: {
      model: "mock-pen-plotter",
      workspace: "A4",
      position: "origin",
    },
  },
  camera: {
    available: true,
    connected: true,
    busy: false,
    error: null,
    driver: "mock-camera",
    last_updated: "2026-03-15T20:00:00Z",
    details: {
      resolution: "1280x960",
      last_capture_id: null,
    },
  },
};

export const defaultCameraBridgeDetails = {
  base_url: "http://127.0.0.1:8731",
  token_path: "/tmp/camerabridge/auth-token",
  token_readable: true,
  service_available: true,
  permission_status: "authorized",
  permission_message: null,
  permission_next_step_kind: null,
  session_state: "stopped",
  session_owner_id: null,
  active_device_id: "camera-1",
  devices: [
    {
      id: "camera-1",
      name: "Built-in Camera",
      position: "front",
    },
  ],
  device_count: 1,
  persisted_selected_device_id: null,
  effective_selected_device_id: "camera-1",
  selection_required: false,
  readiness_state: "ready",
  last_capture_id: null,
  resolution: null,
  configuration_error: null,
} satisfies Record<string, unknown>;

export const defaultCameraBridgeHardwareStatus: HardwareStatus = {
  ...defaultHardwareStatus,
  camera: {
    available: true,
    connected: true,
    busy: false,
    error: null,
    driver: "camerabridge",
    last_updated: "2026-03-15T20:00:00Z",
    details: { ...defaultCameraBridgeDetails },
  },
};

export const defaultAxiDrawHardwareStatus: HardwareStatus = {
  ...defaultHardwareStatus,
  plotter: {
    ...defaultHardwareStatus.plotter,
    driver: "axidraw-pyapi",
    details: {
      ...defaultHardwareStatus.plotter.details,
      api_surface: "installed_axidrawinternal_compat",
      plot_api_supported: false,
      manual_api_supported: true,
      config_source: "vendor_default",
      calibration_source: "vendor_default",
      native_res_factor: 1016,
      motion_scale: 1,
      pen_tuning: {
        pen_pos_up: 60,
        pen_pos_down: 30,
        pen_rate_raise: 75,
      },
      last_test_action: null,
      last_test_action_status: null,
    },
  },
};

export const defaultCalibration: PlotterCalibration = {
  driver: "axidraw",
  motion_scale: 1,
  driver_calibration: {
    native_res_factor: 1016,
  },
  updated_at: "2026-03-15T20:00:00Z",
  source: "vendor_default",
};

export const defaultWorkspace: PlotterWorkspace = {
  plotter_bounds_mm: {
    width_mm: 210,
    height_mm: 297,
  },
  page_size_mm: {
    width_mm: 210,
    height_mm: 297,
  },
  margins_mm: {
    left_mm: 20,
    top_mm: 20,
    right_mm: 20,
    bottom_mm: 20,
  },
  drawable_area_mm: {
    width_mm: 170,
    height_mm: 257,
  },
  updated_at: "2026-03-15T20:00:00Z",
  source: "config_default",
  is_valid: true,
  validation_error: null,
};

export const defaultDevice: PlotterDeviceSettings = {
  driver: "mock",
  plotter_model: null,
  nominal_plotter_bounds_mm: {
    width_mm: 210,
    height_mm: 297,
  },
  nominal_plotter_bounds_source: "config_default",
  plotter_bounds_mm: {
    width_mm: 210,
    height_mm: 297,
  },
  plotter_bounds_source: "config_default",
  updated_at: "2026-03-15T20:00:00Z",
  source: "config_default",
};

export function makeHelperStatus(
  overrides: Partial<HelperStatus> = {},
): HelperStatus {
  return {
    state: "stopped",
    backend_health: "unreachable",
    mode: "camera",
    backend_url: "http://127.0.0.1:8000",
    managed_pid: null,
    started_at: null,
    last_error: null,
    last_exit_code: null,
    ...overrides,
  };
}

export interface HardwareDashboardHarness {
  currentHardwareStatus: HardwareStatus;
  currentCalibration: PlotterCalibration;
  currentDevice: PlotterDeviceSettings;
  currentWorkspace: PlotterWorkspace;
  latestCapture: CaptureMetadata | null;
  latestRun: Record<string, unknown> | null;
  recentRuns: Record<string, unknown>[];
  plotRunsById: Record<string, Record<string, unknown>>;
  backendReachable: boolean;
  helperReachable: boolean;
  helperStatus: HelperStatus;
  helperStartCount: number;
  helperRestartCount: number;
  helperStatusPollCount: number;
  helperTransitionsToRunning: boolean;
  helperFailsOnStart: boolean;
  backendProxyReturns500: boolean;
  cameraCaptureError: string | null;
  cameraCaptureStatusCode: number;
  cameraCaptureAttempts: number;
  cameraDeviceRequests: Array<string | null>;
  plotterTestActions: string[];
  safeBoundsRequests: Array<{
    width_mm: number | null;
    height_mm: number | null;
  }>;
  workspaceRequests: Array<{
    page_width_mm: number;
    page_height_mm: number;
    margin_left_mm: number;
    margin_top_mm: number;
    margin_right_mm: number;
    margin_bottom_mm: number;
  }>;
}

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function computeWorkspaceValidation(
  workspace: PlotterWorkspace,
  plotterBounds: PlotterDeviceSettings["plotter_bounds_mm"],
) {
  if (workspace.page_size_mm.width_mm > plotterBounds.width_mm) {
    return {
      isValid: false,
      validationError: "Configured page width exceeds the plotter bounds width.",
    };
  }

  if (workspace.page_size_mm.height_mm > plotterBounds.height_mm) {
    return {
      isValid: false,
      validationError: "Configured page height exceeds the plotter bounds height.",
    };
  }

  return {
    isValid: true,
    validationError: null,
  };
}

export function createHardwareDashboardHarness(
  overrides: Partial<HardwareDashboardHarness> = {},
): HardwareDashboardHarness {
  return {
    currentHardwareStatus: structuredClone(defaultHardwareStatus),
    currentCalibration: structuredClone(defaultCalibration),
    currentDevice: structuredClone(defaultDevice),
    currentWorkspace: structuredClone(defaultWorkspace),
    latestCapture: null,
    latestRun: null,
    recentRuns: [],
    plotRunsById: {},
    backendReachable: true,
    helperReachable: false,
    helperStatus: makeHelperStatus(),
    helperStartCount: 0,
    helperRestartCount: 0,
    helperStatusPollCount: 0,
    helperTransitionsToRunning: true,
    helperFailsOnStart: false,
    backendProxyReturns500: false,
    cameraCaptureError: null,
    cameraCaptureStatusCode: 503,
    cameraCaptureAttempts: 0,
    cameraDeviceRequests: [],
    plotterTestActions: [],
    safeBoundsRequests: [],
    workspaceRequests: [],
    ...overrides,
  };
}

export function useDashboardFakeTimers() {
  vi.useFakeTimers();
}

export async function flushDashboardEffects() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

async function advanceDashboardTimersBy(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

export async function advanceHardwareDashboardPoll(cycles = 1) {
  await advanceDashboardTimersBy(HARDWARE_DASHBOARD_POLL_INTERVAL_MS * cycles);
}

export async function advancePlotWorkflowIdlePoll(cycles = 1) {
  await advanceDashboardTimersBy(PLOT_WORKFLOW_IDLE_POLL_INTERVAL_MS * cycles);
}

export async function advancePlotWorkflowActivePoll(cycles = 1) {
  await advanceDashboardTimersBy(PLOT_WORKFLOW_ACTIVE_POLL_INTERVAL_MS * cycles);
}

export function installHardwareDashboardFetchMock(
  harness: HardwareDashboardHarness,
) {
  vi.spyOn(globalThis, "fetch").mockImplementation(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";

      if (url.startsWith("/local-helper/")) {
        if (!harness.helperReachable) {
          throw new TypeError("Failed to fetch");
        }

        if (url === "/local-helper/status") {
          harness.helperStatusPollCount += 1;
          if (
            harness.helperStatus.state === "starting" &&
            harness.helperFailsOnStart &&
            harness.helperStatusPollCount >= 1
          ) {
            harness.helperStatus = makeHelperStatus({
              state: "failed",
              backend_health: "unreachable",
              started_at: harness.helperStatus.started_at,
              last_error: "camera init failed",
              last_exit_code: 1,
            });
          } else if (
            harness.helperStatus.state === "starting" &&
            harness.helperTransitionsToRunning &&
            harness.helperStatusPollCount >= 1
          ) {
            harness.backendReachable = true;
            harness.helperStatus = makeHelperStatus({
              state: "running",
              backend_health: "healthy",
              managed_pid: harness.helperStatus.managed_pid,
              started_at: harness.helperStatus.started_at,
            });
          }

          return jsonResponse(harness.helperStatus);
        }

        if (url === "/local-helper/start" && method === "POST") {
          harness.helperStartCount += 1;
          harness.helperStatusPollCount = 0;
          harness.helperStatus = makeHelperStatus({
            state: "starting",
            backend_health: "starting",
            managed_pid: 1473,
            started_at: "2026-03-15T20:00:05Z",
          });
          return jsonResponse(harness.helperStatus);
        }

        if (url === "/local-helper/restart" && method === "POST") {
          harness.helperRestartCount += 1;
          harness.helperStatusPollCount = 0;
          harness.helperStatus = makeHelperStatus({
            state: "starting",
            backend_health: "starting",
            managed_pid: 1473,
            started_at: "2026-03-15T20:00:05Z",
          });
          return jsonResponse(harness.helperStatus);
        }

        return new Response("Not found", { status: 404 });
      }

      if (url.startsWith("/api/") && !harness.backendReachable) {
        if (harness.backendProxyReturns500) {
          return new Response("", {
            status: 500,
            headers: { "Content-Type": "text/plain" },
          });
        }
        throw new TypeError("Failed to fetch");
      }

      if (url === "/api/hardware/status") {
        return jsonResponse(harness.currentHardwareStatus);
      }

      if (url === "/api/captures/latest") {
        return jsonResponse({ capture: harness.latestCapture });
      }

      if (url === "/api/camera/capture" && method === "POST") {
        harness.cameraCaptureAttempts += 1;

        if (harness.cameraCaptureError) {
          return new Response(
            JSON.stringify({ detail: harness.cameraCaptureError }),
            {
              status: harness.cameraCaptureStatusCode,
              headers: { "Content-Type": "application/json" },
            },
          );
        }

        harness.latestCapture = {
          id: "capture-real-001",
          timestamp: "2026-03-15T20:05:00Z",
          file_path: "/tmp/capture-real-001.jpg",
          public_url: "/captures/capture-real-001.jpg",
          width: 1920,
          height: 1080,
          mime_type: "image/jpeg",
        };
        harness.currentHardwareStatus = {
          ...harness.currentHardwareStatus,
          camera: {
            ...harness.currentHardwareStatus.camera,
            available: true,
            connected: true,
            error: null,
            last_updated: "2026-03-15T20:05:00Z",
            details: {
              ...harness.currentHardwareStatus.camera.details,
              readiness_state: "ready",
              selection_required: false,
              service_available: true,
              permission_status: "authorized",
              effective_selected_device_id:
                typeof harness.currentHardwareStatus.camera.details
                  .effective_selected_device_id === "string"
                  ? harness.currentHardwareStatus.camera.details
                    .effective_selected_device_id
                  : (Array.isArray(harness.currentHardwareStatus.camera.details.devices)
                    ? harness.currentHardwareStatus.camera.details.devices
                    : []
                  ).find(
                    (
                      device,
                    ): device is { id?: string } =>
                      typeof device === "object" && device !== null,
                  )?.id ?? null,
              last_capture_id: harness.latestCapture.id,
              resolution: "1920x1080",
            },
          },
        };

        return jsonResponse({
          ok: true,
          message: "Image captured.",
          status: harness.currentHardwareStatus.camera,
          capture: harness.latestCapture,
        });
      }

      if (url === "/api/camera/device" && method === "POST") {
        const body = JSON.parse(String(init?.body ?? "{}")) as {
          device_id: string | null;
        };
        harness.cameraDeviceRequests.push(body.device_id);
        const availableDevices = Array.isArray(harness.currentHardwareStatus.camera.details.devices)
          ? harness.currentHardwareStatus.camera.details.devices.filter(
              (device): device is { id: string } =>
                typeof device === "object" &&
                device !== null &&
                typeof (device as { id?: unknown }).id === "string",
            )
          : [];
        const effectiveSelectedDeviceId =
          body.device_id ??
          (availableDevices.length === 1 ? availableDevices[0].id : null);

        harness.currentHardwareStatus = {
          ...harness.currentHardwareStatus,
          camera: {
            ...harness.currentHardwareStatus.camera,
            available: effectiveSelectedDeviceId !== null,
            connected: true,
            busy: false,
            error: null,
            last_updated: "2026-03-15T20:05:00Z",
            details: {
              ...harness.currentHardwareStatus.camera.details,
              persisted_selected_device_id: body.device_id,
              effective_selected_device_id: effectiveSelectedDeviceId,
              selection_required:
                effectiveSelectedDeviceId === null && availableDevices.length > 1,
              readiness_state:
                effectiveSelectedDeviceId === null && availableDevices.length > 1
                  ? "needs_device_selection"
                  : "ready",
            },
          },
        };

        return jsonResponse({
          ok: true,
          message:
            body.device_id === null
              ? "Camera device preference cleared."
              : "Camera device preference updated.",
          status: harness.currentHardwareStatus.camera,
        });
      }

      if (url === "/api/plot-runs/latest") {
        return jsonResponse({ run: harness.latestRun });
      }

      if (url === "/api/plot-runs" && method === "GET") {
        return jsonResponse({ runs: harness.recentRuns });
      }

      if (url.startsWith("/api/plot-runs/") && method === "GET") {
        const runId = url.slice("/api/plot-runs/".length);
        if (harness.latestRun && harness.latestRun.id === runId) {
          return jsonResponse(harness.latestRun);
        }
        if (harness.plotRunsById[runId]) {
          return jsonResponse(harness.plotRunsById[runId]);
        }
        return new Response("Not found", { status: 404 });
      }

      if (url === "/api/plotter/calibration") {
        if (method === "POST") {
          const body = JSON.parse(String(init?.body ?? "{}")) as {
            native_res_factor: number;
          };
          harness.currentCalibration = {
            ...harness.currentCalibration,
            motion_scale: Number((body.native_res_factor / 1016).toFixed(6)),
            driver_calibration: {
              native_res_factor: body.native_res_factor,
            },
            updated_at: "2026-03-15T20:00:10Z",
            source: "persisted",
          };

          return jsonResponse({
            ok: true,
            message: "Plotter calibration updated.",
            calibration: harness.currentCalibration,
          });
        }

        return jsonResponse(harness.currentCalibration);
      }

      if (url === "/api/plotter/device") {
        return jsonResponse(harness.currentDevice);
      }

      if (url === "/api/plotter/device/safe-bounds" && method === "POST") {
        const body = JSON.parse(String(init?.body ?? "{}")) as {
          width_mm: number | null;
          height_mm: number | null;
        };
        harness.safeBoundsRequests.push(body);
        harness.currentDevice = {
          ...harness.currentDevice,
          plotter_bounds_mm:
            body.width_mm === null && body.height_mm === null
              ? {
                  width_mm: harness.currentDevice.nominal_plotter_bounds_mm.width_mm,
                  height_mm: harness.currentDevice.nominal_plotter_bounds_mm.height_mm,
                }
              : {
                  width_mm: body.width_mm ?? harness.currentDevice.plotter_bounds_mm.width_mm,
                  height_mm:
                    body.height_mm ?? harness.currentDevice.plotter_bounds_mm.height_mm,
                },
          plotter_bounds_source:
            body.width_mm === null && body.height_mm === null
              ? harness.currentDevice.driver === "axidraw"
                ? "default_clearance"
                : "config_default"
              : "manual_override",
          updated_at: "2026-03-15T20:00:11Z",
          source: "persisted",
        };
        if (
          body.width_mm === null &&
          body.height_mm === null &&
          harness.currentDevice.driver === "axidraw"
        ) {
          harness.currentDevice = {
            ...harness.currentDevice,
            plotter_bounds_mm: {
              width_mm: harness.currentDevice.nominal_plotter_bounds_mm.width_mm - 10,
              height_mm: harness.currentDevice.nominal_plotter_bounds_mm.height_mm - 10,
            },
          };
        }

        const workspaceValidation = computeWorkspaceValidation(
          harness.currentWorkspace,
          harness.currentDevice.plotter_bounds_mm,
        );
        harness.currentWorkspace = {
          ...harness.currentWorkspace,
          plotter_bounds_mm: harness.currentDevice.plotter_bounds_mm,
          is_valid: workspaceValidation.isValid,
          validation_error: workspaceValidation.validationError,
        };

        return jsonResponse({
          ok: true,
          message:
            body.width_mm === null && body.height_mm === null
              ? "Operational safe bounds reset to the default clearance."
              : "Operational safe bounds updated.",
          device: harness.currentDevice,
        });
      }

      if (url === "/api/plotter/workspace") {
        if (method === "POST") {
          const body = JSON.parse(String(init?.body ?? "{}")) as {
            page_width_mm: number;
            page_height_mm: number;
            margin_left_mm: number;
            margin_top_mm: number;
            margin_right_mm: number;
            margin_bottom_mm: number;
          };
          harness.workspaceRequests.push(body);
          harness.currentWorkspace = {
            ...harness.currentWorkspace,
            page_size_mm: {
              width_mm: body.page_width_mm,
              height_mm: body.page_height_mm,
            },
            margins_mm: {
              left_mm: body.margin_left_mm,
              top_mm: body.margin_top_mm,
              right_mm: body.margin_right_mm,
              bottom_mm: body.margin_bottom_mm,
            },
            drawable_area_mm: {
              width_mm: body.page_width_mm - body.margin_left_mm - body.margin_right_mm,
              height_mm: body.page_height_mm - body.margin_top_mm - body.margin_bottom_mm,
            },
            updated_at: "2026-03-15T20:00:12Z",
            source: "persisted",
            is_valid: true,
            validation_error: null,
          };

          return jsonResponse({
            ok: true,
            message: "Plotter workspace updated.",
            workspace: harness.currentWorkspace,
          });
        }

        return jsonResponse(harness.currentWorkspace);
      }

      if (url === "/api/plotter/test-actions" && method === "POST") {
        const body = JSON.parse(String(init?.body ?? "{}")) as { action: string };
        harness.plotterTestActions.push(body.action);
        harness.currentHardwareStatus = {
          ...harness.currentHardwareStatus,
          plotter: {
            ...harness.currentHardwareStatus.plotter,
            details: {
              ...harness.currentHardwareStatus.plotter.details,
              last_test_action: body.action,
              last_test_action_status: "completed",
            },
          },
        };

        return jsonResponse({
          ok: true,
          message: `Plotter test action '${body.action}' completed.`,
          status: harness.currentHardwareStatus.plotter,
        });
      }

      return new Response("Not found", { status: 404 });
    },
  );
}
