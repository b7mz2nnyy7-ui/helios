import { afterEach, describe, expect, it, vi } from "vitest";

import {
  fetchSystemHealth,
  fetchSystemReport,
  fetchVideos,
  videoStreamUrl,
} from "./api";

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
