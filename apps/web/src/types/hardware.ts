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

export type PlotterCalibrationSource =
  | "vendor_default"
  | "persisted"
  | "env_override"
  | "explicit_path";
export type PlotterBoundsSource =
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
  plotter_bounds_mm: SizeMm;
  plotter_bounds_source: PlotterBoundsSource;
  updated_at: string;
  source: PlotterDeviceSettingsSource;
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
}

export interface PlotterWorkspaceResponse {
  ok: boolean;
  message: string;
  workspace: PlotterWorkspace;
}
