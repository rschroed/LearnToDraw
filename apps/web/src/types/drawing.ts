import type { PlotAsset } from "./plotting";

export type DrawingSessionStatus =
  | "planning"
  | "awaiting_approval"
  | "running"
  | "awaiting_capture_review"
  | "observed"
  | "proposal_ready"
  | "paused"
  | "stopping"
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
  session_version: 1 | 2;
  intent: string;
  mode: "additive";
  iteration_limit: number | null;
  status: DrawingSessionStatus;
  created_at: string;
  updated_at: string;
  iterations: DrawingIteration[];
  advisor: DrawingAdvisorStatus;
  error: string | null;
  plan: {
    summary: string;
    paper_strategy: string;
    completion_intent: string;
  } | null;
  current_proposal: {
    asset: PlotAsset;
    created_at: string;
    advisor_driver: string;
    advisor_model: string | null;
  } | null;
  current_run_id: string | null;
  assessing_run_id: string | null;
  pass_count: number;
  planning_generation: number;
  authorization: {
    approved_at: string | null;
    stop_requested: boolean;
    last_heartbeat_at: string | null;
  };
  queued_guidance: string[];
  requested_human_action: string | null;
  events: DrawingSessionEvent[];
  approved_at: string | null;
  paused_at: string | null;
  completed_at: string | null;
}

export type DrawingSessionEventType =
  | "session_created"
  | "user_guidance"
  | "plan_ready"
  | "plan_failed"
  | "session_approved"
  | "plot_started"
  | "observation_ready"
  | "agent_decision"
  | "session_paused"
  | "session_resumed"
  | "stop_requested"
  | "session_completed"
  | "session_failed";

export interface DrawingSessionEvent {
  id: string;
  type: DrawingSessionEventType;
  created_at: string;
  message: string;
  asset_id: string | null;
  run_id: string | null;
  details: Record<string, unknown>;
}

export interface DrawingSessionSummary {
  id: string;
  session_version: 1 | 2;
  intent: string;
  status: DrawingSessionStatus;
  pass_count: number;
  created_at: string;
  updated_at: string;
  preview_url: string | null;
}

export interface DrawingSessionListResponse {
  sessions: DrawingSessionSummary[];
}

export interface LatestDrawingSessionResponse {
  session: DrawingSession | null;
}
