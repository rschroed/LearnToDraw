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
