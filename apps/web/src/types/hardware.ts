export interface DeviceStatus {
  available: boolean;
  connected: boolean;
  busy: boolean;
  error: string | null;
  driver: string;
  last_updated: string;
  details: Record<string, unknown>;
}

export interface HardwareStatus {
  plotter: DeviceStatus;
  camera: DeviceStatus;
}

export type CameraReadinessState =
  | "ready"
  | "needs_service"
  | "needs_permission"
  | "needs_device_selection"
  | "busy_external"
  | "error";

export type CameraBridgePermissionStatus =
  | "authorized"
  | "not_determined"
  | "restricted"
  | "denied";

export type CameraBridgeDevicePosition = "front" | "back" | "external";

export interface CameraBridgeDeviceOption {
  id: string;
  name: string;
  position: CameraBridgeDevicePosition;
}

export interface CameraBridgeStatusDetails {
  base_url: string | null;
  token_path: string | null;
  token_readable: boolean;
  service_available: boolean;
  permission_status: CameraBridgePermissionStatus | null;
  permission_message: string | null;
  permission_next_step_kind: string | null;
  session_state: "stopped" | "running" | null;
  session_owner_id: string | null;
  active_device_id: string | null;
  devices: CameraBridgeDeviceOption[];
  device_count: number;
  persisted_selected_device_id: string | null;
  effective_selected_device_id: string | null;
  selection_required: boolean;
  readiness_state: CameraReadinessState;
  last_capture_id: string | null;
  resolution: string | null;
  configuration_error: string | null;
}

export interface CaptureMetadata {
  id: string;
  timestamp: string;
  file_path: string;
  public_url: string;
  width: number;
  height: number;
  mime_type: string;
}

export interface LatestCaptureResponse {
  capture: CaptureMetadata | null;
}

export interface PlotterCommandResponse {
  ok: boolean;
  message: string;
  status: DeviceStatus;
}

export interface CameraCaptureResponse extends PlotterCommandResponse {
  capture: CaptureMetadata;
}

export interface CameraCommandResponse extends PlotterCommandResponse {}

export type PlotterCalibrationSource =
  | "vendor_default"
  | "persisted"
  | "env_override"
  | "explicit_path";
export type PlotterBoundsSource =
  | "manual_override"
  | "default_clearance"
  | "config_default";
export type NominalPlotterBoundsSource =
  | "model_default"
  | "config_override"
  | "config_default";

export interface PlotterCalibration {
  driver: string;
  motion_scale: number;
  driver_calibration: Record<string, unknown>;
  updated_at: string;
  source: PlotterCalibrationSource;
}

export interface PlotterCalibrationResponse {
  ok: boolean;
  message: string;
  calibration: PlotterCalibration;
}

export interface PlotterModelDescriptor {
  code: number;
  label: string;
}

export type PlotterDeviceSettingsSource = "config_default" | "persisted";

export interface PlotterDeviceSettings {
  driver: string;
  plotter_model: PlotterModelDescriptor | null;
  nominal_plotter_bounds_mm: SizeMm;
  nominal_plotter_bounds_source: NominalPlotterBoundsSource;
  plotter_bounds_mm: SizeMm;
  plotter_bounds_source: PlotterBoundsSource;
  updated_at: string;
  source: PlotterDeviceSettingsSource;
}

export interface PlotterDeviceSettingsResponse {
  ok: boolean;
  message: string;
  device: PlotterDeviceSettings;
}

export interface SizeMm {
  width_mm: number;
  height_mm: number;
}

export interface MarginsMm {
  left_mm: number;
  top_mm: number;
  right_mm: number;
  bottom_mm: number;
}

export type PlotterWorkspaceSource = "config_default" | "persisted";

export interface PlotterWorkspace {
  plotter_bounds_mm: SizeMm;
  page_size_mm: SizeMm;
  margins_mm: MarginsMm;
  drawable_area_mm: SizeMm;
  updated_at: string;
  source: PlotterWorkspaceSource;
  is_valid: boolean;
  validation_error: string | null;
}

export interface PlotterWorkspaceResponse {
  ok: boolean;
  message: string;
  workspace: PlotterWorkspace;
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

export function getCameraBridgeStatusDetails(
  status: DeviceStatus,
): CameraBridgeStatusDetails | null {
  if (status.driver !== "camerabridge") {
    return null;
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
    base_url: getString(status.details, "base_url"),
    token_path: getString(status.details, "token_path"),
    token_readable: getBoolean(status.details, "token_readable"),
    service_available: getBoolean(status.details, "service_available"),
    permission_status:
      (getString(status.details, "permission_status") as CameraBridgePermissionStatus | null) ??
      null,
    permission_message: getString(status.details, "permission_message"),
    permission_next_step_kind: getString(status.details, "permission_next_step_kind"),
    session_state:
      (getString(status.details, "session_state") as "stopped" | "running" | null) ??
      null,
    session_owner_id: getString(status.details, "session_owner_id"),
    active_device_id: getString(status.details, "active_device_id"),
    devices,
    device_count: getNumber(status.details, "device_count", devices.length),
    persisted_selected_device_id: getString(status.details, "persisted_selected_device_id"),
    effective_selected_device_id: getString(status.details, "effective_selected_device_id"),
    selection_required: getBoolean(status.details, "selection_required"),
    readiness_state:
      (getString(status.details, "readiness_state") as CameraReadinessState | null) ??
      "error",
    last_capture_id: getString(status.details, "last_capture_id"),
    resolution: getString(status.details, "resolution"),
    configuration_error: getString(status.details, "configuration_error"),
  };
}
