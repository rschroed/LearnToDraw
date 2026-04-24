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
  review: CaptureReview | null;
  normalized: NormalizedCaptureArtifacts | null;
}

export interface CaptureReview {
  review_required: boolean;
  review_status: "pending" | "confirmed";
  proposed_corners: NormalizationCorners;
  confirmed_corners: NormalizationCorners | null;
  confirmation_source: "auto" | "adjusted" | "reused_last" | null;
  detector_method: "paper_contour_v3" | "paper_region_v2" | "paper_edges_v1" | "fallback_full_frame";
  detector_confidence: number;
  reuse_last_available: boolean;
}

export interface NormalizationCorners {
  top_left: [number, number];
  top_right: [number, number];
  bottom_right: [number, number];
  bottom_left: [number, number];
}

export interface NormalizationTransform {
  matrix: number[][];
}

export interface NormalizationOutput {
  width: number;
  height: number;
  aspect_ratio: number;
}

export interface NormalizationFrame {
  kind: "page_aligned";
  version: number;
  page_width_mm: number;
  page_height_mm: number;
}

export interface NormalizationDiagnosticCandidate {
  corners?: NormalizationCorners | null;
  bounds?: [number, number, number, number] | null;
  component_area?: number | null;
  rect_area?: number | null;
  fill_ratio?: number | null;
  occupancy_score?: number | null;
  edge_support_score?: number | null;
  top_score?: number | null;
  right_score?: number | null;
  bottom_score?: number | null;
  left_score?: number | null;
  mean_border_support?: number | null;
  max_outward_expansion_px?: number | null;
  refined_area_ratio?: number | null;
  aspect_log_error?: number | null;
  score?: number | null;
  confidence?: number | null;
  rejection_reason?: string | null;
}

export interface NormalizationMethodDiagnostics {
  status: "used" | "rejected" | "not_run" | "unavailable";
  rejection_reason?: string | null;
  candidate_count: number;
  best_candidate?: NormalizationDiagnosticCandidate | null;
}

export interface NormalizationDiagnostics {
  mode: "default" | "region_only";
  contour_v3?: NormalizationMethodDiagnostics | null;
  region_v2: NormalizationMethodDiagnostics;
  line_v1: NormalizationMethodDiagnostics;
}

export interface NormalizationMetadata {
  method: "paper_contour_v3" | "paper_region_v2" | "paper_edges_v1" | "fallback_full_frame";
  confidence: number;
  corners: NormalizationCorners;
  transform: NormalizationTransform;
  output: NormalizationOutput;
  target_frame_source: "prepared_svg" | "workspace_drawable_area";
  frame?: NormalizationFrame | null;
  diagnostics?: NormalizationDiagnostics | null;
}

export interface NormalizedCaptureArtifacts {
  rectified_color_url: string;
  rectified_grayscale_url: string;
  debug_overlay_url: string;
  metadata: NormalizationMetadata;
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
