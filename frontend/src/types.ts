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
