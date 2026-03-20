export type HelperState = "stopped" | "starting" | "running" | "failed";
export type HelperBackendHealth = "unreachable" | "starting" | "healthy";

export interface HelperStatus {
  helper_instance_id?: string;
  helper_launched_at?: string;
  state: HelperState;
  backend_health: HelperBackendHealth;
  mode: string;
  backend_url: string;
  managed_pid: number | null;
  started_at: string | null;
  last_error: string | null;
  last_exit_code: number | null;
}
