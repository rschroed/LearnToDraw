import type {
  CameraBridgeDeviceOption,
  CameraBridgeDevicePosition,
  CameraBridgePermissionStatus,
  CameraBridgeStatusDetails,
  CameraReadinessState,
  DeviceStatus,
} from "../../types/hardware";
import type { ActionFeedback } from "./hardwareDashboardTypes";

export interface CameraNotice {
  tone: "info" | "success" | "error";
  message: string;
}

export type ParsedCameraStatus =
  | {
      kind: "camerabridge";
      details: CameraBridgeStatusDetails;
      status: DeviceStatus;
    }
  | {
      kind: "generic";
      status: DeviceStatus;
    };

export interface CameraPanelModel {
  notice: CameraNotice | null;
  captureDisabled: boolean;
  capturePending: boolean;
  selectionRequired: boolean;
  availableDevices: CameraBridgeDeviceOption[];
  selectedDeviceId: string;
  selectedDeviceLabel: string | null;
  saveDeviceDisabled: boolean;
  saveDevicePending: boolean;
  footerNote: string;
}

export function parseCameraStatus(status: DeviceStatus): ParsedCameraStatus {
  if (status.driver !== "camerabridge") {
    return {
      kind: "generic",
      status,
    };
  }

  const devicesValue = Array.isArray(status.details.devices)
    ? status.details.devices
    : [];
  const devices = devicesValue
    .filter(
      (device): device is Record<string, unknown> =>
        typeof device === "object" && device !== null,
    )
    .map((device) => ({
      id: getString(device, "id") ?? "",
      name: getString(device, "name") ?? "",
      position:
        (getString(device, "position") as CameraBridgeDevicePosition | null) ??
        "external",
    }))
    .filter((device) => device.id.length > 0);

  return {
    kind: "camerabridge",
    status,
    details: {
      base_url: getString(status.details, "base_url"),
      token_path: getString(status.details, "token_path"),
      token_readable: getBoolean(status.details, "token_readable"),
      service_available: getBoolean(status.details, "service_available"),
      permission_status:
        (getString(
          status.details,
          "permission_status",
        ) as CameraBridgePermissionStatus | null) ?? null,
      permission_message: getString(status.details, "permission_message"),
      permission_next_step_kind: getString(status.details, "permission_next_step_kind"),
      session_state:
        (getString(status.details, "session_state") as "stopped" | "running" | null) ??
        null,
      session_owner_id: getString(status.details, "session_owner_id"),
      active_device_id: getString(status.details, "active_device_id"),
      devices,
      device_count: getNumber(status.details, "device_count", devices.length),
      persisted_selected_device_id: getString(
        status.details,
        "persisted_selected_device_id",
      ),
      effective_selected_device_id: getString(
        status.details,
        "effective_selected_device_id",
      ),
      selection_required: getBoolean(status.details, "selection_required"),
      readiness_state:
        (getString(status.details, "readiness_state") as CameraReadinessState | null) ??
        "error",
      last_capture_id: getString(status.details, "last_capture_id"),
      resolution: getString(status.details, "resolution"),
      configuration_error: getString(status.details, "configuration_error"),
    },
  };
}

export function buildCameraPanelModel({
  parsedStatus,
  actionFeedback,
  actionName,
  selectedDeviceId,
}: {
  parsedStatus: ParsedCameraStatus;
  actionFeedback: ActionFeedback | null;
  actionName: string | null;
  selectedDeviceId: string;
}): CameraPanelModel {
  const notice = buildCameraNotice(parsedStatus, actionFeedback);
  const capturePending = actionName === "camera-capture";
  const saveDevicePending = actionName === "camera-device";

  if (parsedStatus.kind === "camerabridge") {
    const { details, status } = parsedStatus;
    const selectedDeviceLabel =
      details.devices.find(
        (device) => device.id === details.effective_selected_device_id,
      )?.name ?? null;

    return {
      notice,
      captureDisabled:
        capturePending || status.busy || details.readiness_state !== "ready",
      capturePending,
      selectionRequired: details.selection_required,
      availableDevices: details.devices,
      selectedDeviceId,
      selectedDeviceLabel,
      saveDeviceDisabled: saveDevicePending || selectedDeviceId.length === 0,
      saveDevicePending,
      footerNote: `${
        selectedDeviceLabel ? `Selected device: ${selectedDeviceLabel}. ` : ""
      }Captures are saved locally and served back through the backend.`,
    };
  }

  const { status } = parsedStatus;
  return {
    notice,
    captureDisabled:
      capturePending || status.busy || !status.available || status.error !== null,
    capturePending,
    selectionRequired: false,
    availableDevices: [],
    selectedDeviceId,
    selectedDeviceLabel: null,
    saveDeviceDisabled: true,
    saveDevicePending,
    footerNote: "Captures are saved locally and served back through the backend.",
  };
}

function buildCameraNotice(
  parsedStatus: ParsedCameraStatus,
  actionFeedback: ActionFeedback | null,
): CameraNotice | null {
  if (
    actionFeedback?.action === "camera-capture" ||
    actionFeedback?.action === "camera-device"
  ) {
    return {
      tone: actionFeedback.tone,
      message: actionFeedback.message,
    };
  }

  if (parsedStatus.kind === "camerabridge") {
    const { details, status } = parsedStatus;
    switch (details.readiness_state) {
      case "needs_service":
        return {
          tone: "info",
          message:
            "Open CameraBridgeApp, click Start CameraBridge Service, then retry once the local service is running.",
        };
      case "needs_permission":
        return {
          tone: "info",
          message:
            details.permission_message ??
            "Open CameraBridgeApp and request camera access before capturing.",
        };
      case "needs_device_selection":
        return {
          tone: "info",
          message: "Choose a CameraBridge device to enable capture.",
        };
      case "busy_external":
        return {
          tone: "error",
          message:
            "Another local client currently owns the CameraBridge session. Stop it there and retry.",
        };
      case "error":
        if (status.error) {
          return { tone: "error", message: status.error };
        }
        return null;
      default:
        break;
    }
  }

  if (parsedStatus.status.error) {
    return { tone: "error", message: parsedStatus.status.error };
  }

  return null;
}

function getString(details: Record<string, unknown>, key: string) {
  return typeof details[key] === "string" ? details[key] : null;
}

function getBoolean(details: Record<string, unknown>, key: string, fallback = false) {
  return typeof details[key] === "boolean" ? details[key] : fallback;
}

function getNumber(details: Record<string, unknown>, key: string, fallback = 0) {
  return typeof details[key] === "number" ? details[key] : fallback;
}
