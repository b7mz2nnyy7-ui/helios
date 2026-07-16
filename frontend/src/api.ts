import type {
  Mission,
  MissionCreateInput,
  SystemHealthReport,
  VideoSummary,
} from "./types";

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

export async function createMission(input: MissionCreateInput): Promise<Mission> {
  const response = await fetch("/api/missions", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error("Unable to create mission.");
  }
  return (await response.json()) as Mission;
}

export async function fetchMissions(signal?: AbortSignal): Promise<Mission[]> {
  const response = await fetch("/api/missions", {
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) {
    throw new Error("Unable to load missions.");
  }
  return (await response.json()) as Mission[];
}

export async function fetchMission(
  missionId: string,
  signal?: AbortSignal,
): Promise<Mission> {
  const response = await fetch(`/api/missions/${encodeURIComponent(missionId)}`, {
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) {
    throw new Error("Unable to load mission.");
  }
  return (await response.json()) as Mission;
}
