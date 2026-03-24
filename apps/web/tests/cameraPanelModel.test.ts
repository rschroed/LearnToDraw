import type { DeviceStatus } from "../src/types/hardware";
import {
  buildCameraPanelModel,
  parseCameraStatus,
} from "../src/features/hardware/cameraPanelModel";

function buildDeviceStatus(overrides: Partial<DeviceStatus> = {}): DeviceStatus {
  return {
    available: true,
    connected: true,
    busy: false,
    error: null,
    driver: "camerabridge",
    last_updated: "2026-03-24T00:00:00Z",
    details: {
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
    },
    ...overrides,
  };
}

describe("cameraPanelModel", () => {
  it("builds a ready CameraBridge model", () => {
    const parsedStatus = parseCameraStatus(buildDeviceStatus());

    const model = buildCameraPanelModel({
      parsedStatus,
      actionFeedback: null,
      actionName: null,
      selectedDeviceId: "camera-1",
    });

    expect(model.notice).toBeNull();
    expect(model.captureDisabled).toBe(false);
    expect(model.selectionRequired).toBe(false);
    expect(model.canEditDevice).toBe(true);
    expect(model.savedDeviceLabel).toBe("Built-in Camera");
    expect(model.saveDeviceDisabled).toBe(true);
    expect(model.deviceEditLabel).toBe("Edit");
    expect(model.headerStatusLabel).toBeNull();
    expect(model.summaryTitle).toBe("Ready to capture");
    expect(model.summaryDetail).toBeNull();
    expect(model.captureActionLabel).toBe("Capture image");
    expect(model.capturePendingLabel).toBe("Capturing...");
    expect(model.secondaryActionLabel).toBeNull();
    expect(model.secondaryActionIntent).toBeNull();
  });

  it("maps service unavailable to an informational notice", () => {
    const parsedStatus = parseCameraStatus(
      buildDeviceStatus({
        available: false,
        connected: false,
        details: {
          ...buildDeviceStatus().details,
          service_available: false,
          readiness_state: "needs_service",
          active_device_id: null,
          effective_selected_device_id: null,
          devices: [],
          device_count: 0,
        },
      }),
    );

    const model = buildCameraPanelModel({
      parsedStatus,
      actionFeedback: null,
      actionName: null,
      selectedDeviceId: "",
    });

    expect(model.captureDisabled).toBe(true);
    expect(model.notice).toBeNull();
    expect(model.headerStatusLabel).toBe("Offline");
    expect(model.summaryTitle).toBe("Start CameraBridge");
    expect(model.summaryDetail).toBe("Open CameraBridge and start the local service.");
    expect(model.secondaryActionLabel).toBe("Open CameraBridgeApp");
    expect(model.secondaryActionIntent).toBe("open_camera_bridge_app");
  });

  it("maps permission-required state to the backend guidance", () => {
    const parsedStatus = parseCameraStatus(
      buildDeviceStatus({
        available: false,
        details: {
          ...buildDeviceStatus().details,
          permission_status: "not_determined",
          permission_message: "Open CameraBridgeApp to request camera access.",
          permission_next_step_kind: "open_camera_bridge_app",
          readiness_state: "needs_permission",
        },
      }),
    );

    const model = buildCameraPanelModel({
      parsedStatus,
      actionFeedback: null,
      actionName: null,
      selectedDeviceId: "camera-1",
    });

    expect(model.notice).toBeNull();
    expect(model.headerStatusLabel).toBe("Needs permission");
    expect(model.summaryTitle).toBe("Camera access required");
    expect(model.summaryDetail).toBe(
      "Grant camera access in CameraBridgeApp before capturing.",
    );
    expect(model.secondaryActionLabel).toBe("Open CameraBridgeApp");
    expect(model.secondaryActionIntent).toBe("open_camera_bridge_app");
  });

  it("requires explicit device selection when the backend says so", () => {
    const parsedStatus = parseCameraStatus(
      buildDeviceStatus({
        available: false,
        details: {
          ...buildDeviceStatus().details,
          devices: [
            { id: "camera-1", name: "Built-in Camera", position: "front" },
            { id: "camera-2", name: "Desk Camera", position: "external" },
          ],
          device_count: 2,
          active_device_id: null,
          effective_selected_device_id: null,
          persisted_selected_device_id: null,
          selection_required: true,
          readiness_state: "needs_device_selection",
        },
      }),
    );

    const model = buildCameraPanelModel({
      parsedStatus,
      actionFeedback: null,
      actionName: null,
      selectedDeviceId: "camera-2",
    });

    expect(model.selectionRequired).toBe(true);
    expect(model.canEditDevice).toBe(true);
    expect(model.captureDisabled).toBe(true);
    expect(model.availableDevices).toHaveLength(2);
    expect(model.saveDeviceDisabled).toBe(false);
    expect(model.deviceSelectionHelper).toBe(
      "Pick a camera and save it before capturing.",
    );
    expect(model.deviceEditLabel).toBeNull();
    expect(model.secondaryActionLabel).toBeNull();
  });

  it("keeps save disabled when the selected camera already matches the saved device", () => {
    const parsedStatus = parseCameraStatus(
      buildDeviceStatus({
        details: {
          ...buildDeviceStatus().details,
          devices: [
            { id: "camera-1", name: "Built-in Camera", position: "front" },
            { id: "camera-2", name: "Desk Camera", position: "external" },
          ],
          device_count: 2,
          persisted_selected_device_id: "camera-1",
          effective_selected_device_id: "camera-1",
        },
      }),
    );

    const model = buildCameraPanelModel({
      parsedStatus,
      actionFeedback: null,
      actionName: null,
      selectedDeviceId: "camera-1",
    });

    expect(model.canEditDevice).toBe(true);
    expect(model.saveDeviceDisabled).toBe(true);
    expect(model.deviceSelectionHelper).toBeNull();
    expect(model.deviceEditLabel).toBe("Edit");
  });

  it("maps external ownership to an error notice", () => {
    const parsedStatus = parseCameraStatus(
      buildDeviceStatus({
        error: "CameraBridge is busy because another local client owns the current session.",
        details: {
          ...buildDeviceStatus().details,
          readiness_state: "busy_external",
          session_owner_id: "other-client",
        },
      }),
    );

    const model = buildCameraPanelModel({
      parsedStatus,
      actionFeedback: null,
      actionName: null,
      selectedDeviceId: "camera-1",
    });

    expect(model.notice).toBeNull();
    expect(model.headerStatusLabel).toBe("Busy");
    expect(model.summaryTitle).toBe("Camera busy");
  });

  it("prefers action feedback over readiness messaging", () => {
    const parsedStatus = parseCameraStatus(
      buildDeviceStatus({
        available: false,
        details: {
          ...buildDeviceStatus().details,
          readiness_state: "needs_service",
          service_available: false,
        },
      }),
    );

    const model = buildCameraPanelModel({
      parsedStatus,
      actionFeedback: {
        action: "camera-device",
        message: "Camera selection saved.",
        tone: "success",
      },
      actionName: null,
      selectedDeviceId: "camera-1",
    });

    expect(model.notice).toEqual({
      tone: "success",
      message: "Camera selection saved.",
    });
    expect(model.summaryTitle).toBe("Start CameraBridge");
  });

  it("falls back cleanly for non-CameraBridge drivers", () => {
    const parsedStatus = parseCameraStatus(
      buildDeviceStatus({
        driver: "mock-camera",
        details: {
          resolution: "1280x960",
          last_capture_id: null,
        },
      }),
    );

    const model = buildCameraPanelModel({
      parsedStatus,
      actionFeedback: null,
      actionName: null,
      selectedDeviceId: "",
    });

    expect(parsedStatus.kind).toBe("generic");
    expect(model.availableDevices).toEqual([]);
    expect(model.selectionRequired).toBe(false);
    expect(model.canEditDevice).toBe(false);
    expect(model.saveDeviceDisabled).toBe(true);
    expect(model.summaryTitle).toBe("Ready to capture");
  });
});
