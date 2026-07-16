import type { SystemHealthReport, VideoSummary } from "./types";

export async function fetchVideos(signal?: AbortSignal): Promise<VideoSummary[]> {
  const response = await fetch("/api/videos", {
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) {
    throw new Error("Unable to load videos.");
  }
  return (await response.json()) as VideoSummary[];
}

export function videoStreamUrl(videoId: string): string {
  return `/api/videos/${encodeURIComponent(videoId)}/stream`;
}

export async function fetchSystemHealth(
  signal?: AbortSignal,
): Promise<SystemHealthReport> {
  const response = await fetch("/api/system/health", {
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) {
    throw new Error("Unable to load system health.");
  }
  return (await response.json()) as SystemHealthReport;
}

export async function fetchSystemReport(signal?: AbortSignal): Promise<string> {
  const response = await fetch("/api/system/report", {
    headers: { Accept: "text/markdown" },
    signal,
  });
  if (!response.ok) {
    throw new Error("Unable to load system report.");
  }
  return response.text();
}
