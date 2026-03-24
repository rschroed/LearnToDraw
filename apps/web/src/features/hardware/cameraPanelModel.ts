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
  headerStatusLabel: string | null;
  headerStatusTone: "ok" | "warn";
  summaryTitle: string;
  summaryDetail: string | null;
  summaryBadges: string[];
  captureActionLabel: string;
  capturePendingLabel: string;
  captureDisabled: boolean;
  capturePending: boolean;
  secondaryActionLabel: string | null;
  secondaryActionIntent: "open_camera_bridge_app" | null;
  canEditDevice: boolean;
  selectionRequired: boolean;
  availableDevices: CameraBridgeDeviceOption[];
  selectedDeviceId: string;
  savedDeviceLabel: string | null;
  hasSelectionDraft: boolean;
  deviceSelectionHelper: string | null;
  deviceEditLabel: string | null;
  saveDeviceDisabled: boolean;
  saveDevicePending: boolean;
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
    const savedDeviceLabel =
      details.devices.find(
        (device) => device.id === details.effective_selected_device_id,
      )?.name ?? null;
    const currentSavedDeviceId =
      details.effective_selected_device_id ?? details.persisted_selected_device_id ?? "";
    const hasSelectionDraft =
      selectedDeviceId.length > 0 && selectedDeviceId !== currentSavedDeviceId;
    const summaryTitle = buildCameraSummaryTitle(details, savedDeviceLabel);
    const summaryDetail = buildCameraSummaryDetail(details, savedDeviceLabel);

    return {
      notice,
      headerStatusLabel:
        details.readiness_state === "ready"
          ? null
          : describeHeaderStatus(details.readiness_state),
      headerStatusTone: details.readiness_state === "ready" ? "ok" : "warn",
      summaryTitle,
      summaryDetail,
      summaryBadges: [],
      captureActionLabel: "Capture image",
      capturePendingLabel: "Capturing...",
      captureDisabled:
        capturePending || status.busy || details.readiness_state !== "ready",
      capturePending,
      secondaryActionLabel: shouldShowCameraBridgeAppHandoff(details)
        ? "Open CameraBridgeApp"
        : null,
      secondaryActionIntent: shouldShowCameraBridgeAppHandoff(details)
        ? "open_camera_bridge_app"
        : null,
      canEditDevice: details.devices.length > 0,
      selectionRequired: details.selection_required,
      availableDevices: details.devices,
      selectedDeviceId,
      savedDeviceLabel,
      hasSelectionDraft,
      deviceSelectionHelper:
        details.selection_required
          ? "Pick a camera and save it before capturing."
          : null,
      deviceEditLabel:
        details.devices.length > 0 && !details.selection_required && savedDeviceLabel
          ? "Edit"
          : null,
      saveDeviceDisabled:
        saveDevicePending ||
        selectedDeviceId.length === 0 ||
        selectedDeviceId === currentSavedDeviceId,
      saveDevicePending,
    };
  }

  const { status } = parsedStatus;
  return {
    notice,
    headerStatusLabel: status.available ? null : "Unavailable",
    headerStatusTone: status.available ? "ok" : "warn",
    summaryTitle: status.available ? "Ready to capture" : "Camera unavailable",
    summaryDetail: status.error ?? "Backend-owned capture is available from this panel.",
    summaryBadges: [],
    captureActionLabel: "Capture image",
    capturePendingLabel: "Capturing...",
    captureDisabled:
      capturePending || status.busy || !status.available || status.error !== null,
    capturePending,
    secondaryActionLabel: null,
    secondaryActionIntent: null,
    canEditDevice: false,
    selectionRequired: false,
    availableDevices: [],
    selectedDeviceId,
    savedDeviceLabel: null,
    hasSelectionDraft: false,
    deviceSelectionHelper: null,
    deviceEditLabel: null,
    saveDeviceDisabled: true,
    saveDevicePending,
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
    const { details } = parsedStatus;
    switch (details.readiness_state) {
      case "error":
        if (parsedStatus.status.error) {
          return { tone: "error", message: parsedStatus.status.error };
        }
        return null;
      default:
        return null;
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

function describeHeaderStatus(readinessState: CameraReadinessState) {
  switch (readinessState) {
    case "ready":
      return "Ready";
    case "needs_service":
      return "Offline";
    case "needs_permission":
      return "Needs permission";
    case "needs_device_selection":
      return "Choose camera";
    case "busy_external":
      return "Busy";
    default:
      return "Unavailable";
  }
}

function buildCameraSummaryTitle(
  details: CameraBridgeStatusDetails,
  _selectedDeviceLabel: string | null,
) {
  switch (details.readiness_state) {
    case "ready":
      return "Ready to capture";
    case "needs_service":
      return "Start CameraBridge";
    case "needs_permission":
      return "Camera access required";
    case "needs_device_selection":
      return "Choose a camera";
    case "busy_external":
      return "Camera busy";
    default:
      return "Camera unavailable";
  }
}

function buildCameraSummaryDetail(
  details: CameraBridgeStatusDetails,
  _selectedDeviceLabel: string | null,
) {
  switch (details.readiness_state) {
    case "ready":
      return null;
    case "needs_service":
      return "Open CameraBridge and start the local service.";
    case "needs_permission":
      return "Grant camera access in CameraBridgeApp before capturing.";
    case "needs_device_selection":
      return "Pick a camera and save it before capturing.";
    case "busy_external":
      return "Another local app is using CameraBridge right now.";
    default:
      return details.configuration_error ?? "Check the camera state and retry.";
  }
}

function shouldShowCameraBridgeAppHandoff(details: CameraBridgeStatusDetails) {
  return (
    details.readiness_state === "needs_service" ||
    details.readiness_state === "needs_permission"
  );
}
