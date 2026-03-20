export interface PlotAsset {
  id: string;
  kind: "uploaded_svg" | "built_in_pattern";
  pattern_id: string | null;
  name: string;
  timestamp: string;
  file_path: string;
  public_url: string;
  mime_type: string;
}

export interface PlotStageState {
  status: "pending" | "in_progress" | "completed" | "failed";
  started_at: string | null;
  completed_at: string | null;
  message: string | null;
}

export interface PlotRun {
  id: string;
  status: "pending" | "plotting" | "capturing" | "completed" | "failed";
  purpose: "normal" | "diagnostic";
  capture_mode: "auto" | "skip";
  created_at: string;
  updated_at: string;
  asset: PlotAsset;
  capture: {
    id: string;
    timestamp: string;
    file_path: string;
    public_url: string;
    width: number;
    height: number;
    mime_type: string;
  } | null;
  observed_result?: {
    capture: {
      id: string;
      timestamp: string;
      file_path: string;
      public_url: string;
      width: number;
      height: number;
      mime_type: string;
    };
    camera_driver: string;
    captured_at: string;
    duration_ms: number;
  } | null;
  error: string | null;
  stage_states: Record<"prepare" | "plot" | "capture", PlotStageState>;
  plotter_run_details: Record<string, unknown>;
  camera_run_details: Record<string, unknown>;
}

export interface PlotRunSummary {
  id: string;
  status: PlotRun["status"];
  purpose: PlotRun["purpose"];
  created_at: string;
  updated_at: string;
  asset_id: string;
  asset_name: string;
  asset_kind: PlotAsset["kind"];
  error: string | null;
}

export interface LatestPlotRunResponse {
  run: PlotRun | null;
}

export interface PlotRunListResponse {
  runs: PlotRunSummary[];
}
