export interface VideoSummary {
  id: string;
  filename: string;
  created_at: string;
  duration: number;
  size_bytes: number;
  sha256: string;
  model: string;
}

export interface VideoDetail extends VideoSummary {
  mime_type: string;
  metadata: Record<string, unknown>;
}
