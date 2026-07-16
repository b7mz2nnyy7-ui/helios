export interface VideoSummary {
  id: string;
  filename: string;
  created_at: string;
  duration: number;
  size_bytes: number;
  sha256: string;
  model: string;
}

export type GuardianStatus = "HEALTHY" | "DEGRADED" | "UNHEALTHY";
export type CheckStatus = "PASS" | "WARNING" | "FAIL" | "SKIPPED";

export interface SystemCheck {
  id: string;
  name: string;
  severity: "INFO" | "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  status: CheckStatus;
  summary: string;
  details: Record<string, unknown>;
  checked_at: string;
  duration_seconds: number;
}

export interface SystemHealthReport {
  created_at: string;
  guardian_version: string;
  overall_status: GuardianStatus;
  checks: SystemCheck[];
  counters: Record<CheckStatus, number>;
  summary: string;
  generated_by: string;
}

export interface VideoDetail extends VideoSummary {
  mime_type: string;
  metadata: Record<string, unknown>;
}

export type MissionStatus = "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED";
export type MissionPlatform = "YouTube" | "TikTok" | "Instagram" | "X";
export type MissionDuration = 15 | 30 | 60;
export type MissionStage =
  | "Research"
  | "Script"
  | "Storyboard"
  | "Rendering"
  | "Download"
  | "Completed";

export interface MissionPipelineState {
  current_stage: MissionStage;
  completed_stages: MissionStage[];
  completed_task_ids: string[];
}

export interface Mission {
  id: string;
  title: string;
  prompt: string;
  platform: MissionPlatform;
  duration: MissionDuration;
  render_model: string;
  status: MissionStatus;
  created_at: string;
  updated_at: string;
  video_id: string | null;
  render_job_id: string | null;
  render_status: string | null;
  media_asset: MissionMediaAsset | null;
  pipeline_state: MissionPipelineState;
  error_message: string | null;
}

export interface MissionMediaAsset {
  asset_id: string;
  asset_type: string;
  name: string;
  description: string;
  provider: string;
  format: string;
  metadata: Record<string, unknown>;
}

export interface MissionCreateInput {
  prompt: string;
  platform: MissionPlatform;
  duration: MissionDuration;
  render_model: string;
}
