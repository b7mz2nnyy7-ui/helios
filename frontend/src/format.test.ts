import { describe, expect, it } from "vitest";

import {
  formatDuration,
  formatFileSize,
  matchesVideoSearch,
  videoTitle,
} from "./format";
import type { VideoSummary } from "./types";

describe("video formatting", () => {
  it("formats durations without layout-shifting values", () => {
    expect(formatDuration(65)).toBe("1:05");
    expect(formatDuration(0)).toBe("--:--");
  });

  it("formats file sizes", () => {
    expect(formatFileSize(512)).toBe("512 B");
    expect(formatFileSize(1_572_864)).toBe("1.5 MB");
  });

  it("turns safe filenames into display titles", () => {
    expect(videoTitle("gen45-product-launch.mp4")).toBe("Gen45 Product Launch");
  });

  it("matches videos by display title or model", () => {
    const video: VideoSummary = {
      id: "video-1",
      filename: "product-launch.mp4",
      created_at: "2026-07-16T10:00:00Z",
      duration: 30,
      size_bytes: 1024,
      sha256: "a".repeat(64),
      model: "gen4.5",
    };

    expect(matchesVideoSearch(video, "product launch")).toBe(true);
    expect(matchesVideoSearch(video, "GEN4.5")).toBe(true);
    expect(matchesVideoSearch(video, "unrelated")).toBe(false);
  });
});
