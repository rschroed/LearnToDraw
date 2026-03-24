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
