import type { PlotAsset } from "./plotting";

export type DrawingSessionStatus =
  | "running"
  | "awaiting_capture_review"
  | "observed"
  | "proposal_ready"
  | "completed"
  | "failed";

export interface DrawingAdvisorStatus {
  driver: "disabled" | "mock" | "openai";
  available: boolean;
  model: string | null;
  message: string | null;
}

export interface DrawingIterationProposal {
  interpretation: string;
  asset: PlotAsset;
  advisor_driver: string;
  advisor_model: string | null;
  created_at: string;
  approved_at: string | null;
  approved_run_id: string | null;
}

export interface DrawingIteration {
  number: number;
  asset: PlotAsset;
  run_id: string;
  created_at: string;
  next_proposal: DrawingIterationProposal | null;
}

export interface DrawingSession {
  id: string;
  intent: string;
  mode: "additive";
  iteration_limit: number;
  status: DrawingSessionStatus;
  created_at: string;
  updated_at: string;
  iterations: DrawingIteration[];
  advisor: DrawingAdvisorStatus;
  error: string | null;
}

export interface LatestDrawingSessionResponse {
  session: DrawingSession | null;
}
