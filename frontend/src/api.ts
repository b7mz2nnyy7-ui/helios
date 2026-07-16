import type { VideoSummary } from "./types";

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
