import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createMission,
  fetchMission,
  fetchMissions,
  fetchSystemHealth,
  fetchSystemReport,
  fetchVideos,
  videoStreamUrl,
} from "./api";
import type { Mission } from "./types";

const mission: Mission = {
  id: "mission-1",
  title: "AI Agents",
  prompt: "AI Agents",
  platform: "YouTube",
  duration: 30,
  render_model: "gen4.5",
  status: "RUNNING",
  created_at: "2026-07-16T10:00:00Z",
  updated_at: "2026-07-16T10:00:01Z",
  video_id: null,
  render_job_id: null,
  pipeline_state: {
    current_stage: "Research",
    completed_stages: [],
    completed_task_ids: [],
  },
  error_message: null,
};

describe("video API client", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("loads videos from the local API", async () => {
    const payload = [{ id: "video-1" }];
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => payload,
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchVideos()).resolves.toEqual(payload);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/videos",
      expect.objectContaining({ headers: { Accept: "application/json" } }),
    );
  });

  it("encodes public IDs in stream URLs", () => {
    expect(videoStreamUrl("video one")).toBe("/api/videos/video%20one/stream");
  });

  it("loads the ARGUS JSON health report", async () => {
    const payload = { overall_status: "HEALTHY", checks: [] };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => payload,
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchSystemHealth()).resolves.toEqual(payload);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/system/health",
      expect.objectContaining({ headers: { Accept: "application/json" } }),
    );
  });

  it("loads the ARGUS Markdown report", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      text: async () => "# ARGUS REPORT",
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchSystemReport()).resolves.toBe("# ARGUS REPORT");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/system/report",
      expect.objectContaining({ headers: { Accept: "text/markdown" } }),
    );
  });
});

describe("mission API client", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("creates a mission through the public API contract", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mission,
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      createMission({
        prompt: "AI Agents",
        platform: "YouTube",
        duration: 30,
        render_model: "gen4.5",
      }),
    ).resolves.toEqual(mission);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/missions",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          prompt: "AI Agents",
          platform: "YouTube",
          duration: 30,
          render_model: "gen4.5",
        }),
      }),
    );
  });

  it("loads mission lists and individual progress", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [mission] })
      .mockResolvedValueOnce({ ok: true, json: async () => mission });
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchMissions()).resolves.toEqual([mission]);
    await expect(fetchMission("mission one")).resolves.toEqual(mission);
    expect(fetchMock).toHaveBeenLastCalledWith(
      "/api/missions/mission%20one",
      expect.objectContaining({ headers: { Accept: "application/json" } }),
    );
  });
});
