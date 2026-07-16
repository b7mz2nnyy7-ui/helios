import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { VideoSummary } from "../types";
import { AppShell } from "./AppShell";
import { EmptyState } from "./EmptyState";
import { VideoCard } from "./VideoCard";
import { VideoPlayerModal } from "./VideoPlayerModal";
import { SystemReportView } from "./SystemPage";

const video: VideoSummary = {
  id: "video-1",
  filename: "launch-film.mp4",
  created_at: "2026-07-16T10:00:00Z",
  duration: 65,
  size_bytes: 1_572_864,
  sha256: "a".repeat(64),
  model: "gen4.5",
};

describe("video interface components", () => {
  it("renders the Helios shell with active video navigation and search", () => {
    const markup = renderToStaticMarkup(
      <AppShell searchValue="" onSearchChange={() => undefined}>
        <p>Library content</p>
      </AppShell>,
    );

    expect(markup).toContain("Helios");
    expect(markup).toContain("Search productions");
    expect(markup).toContain('aria-current="page"');
    expect(markup).toContain("Missions");
    expect(markup).toContain("Agents");
    expect(markup).toContain("Settings");
  });

  it("renders production metadata and the poster asset", () => {
    const markup = renderToStaticMarkup(
      <VideoCard video={video} onSelect={() => undefined} />,
    );

    expect(markup).toContain("Launch Film");
    expect(markup).toContain("1:05");
    expect(markup).toContain("gen4.5");
    expect(markup).toContain("/poster-placeholder.png");
  });

  it("renders a range-capable HTML5 video source", () => {
    const markup = renderToStaticMarkup(
      <VideoPlayerModal video={video} onClose={() => undefined} />,
    );

    expect(markup).toContain("<video");
    expect(markup).toContain("/api/videos/video-1/stream");
    expect(markup).toContain("controls");
  });

  it("renders the required empty state", () => {
    const markup = renderToStaticMarkup(<EmptyState />);

    expect(markup).toContain("Your AI productions will appear here.");
    expect(markup).toContain("Create Mission");
  });

  it("renders ARGUS health, checks, warnings, and Markdown", () => {
    const markup = renderToStaticMarkup(
      <SystemReportView
        report={{
          created_at: "2026-07-16T10:00:00Z",
          guardian_version: "0.1.0",
          overall_status: "DEGRADED",
          checks: [
            {
              id: "provider_config",
              name: "Provider Configuration",
              severity: "HIGH",
              status: "WARNING",
              summary: "Provider is not ready.",
              details: {},
              checked_at: "2026-07-16T10:00:00Z",
              duration_seconds: 0.01,
            },
          ],
          counters: { PASS: 0, WARNING: 1, FAIL: 0, SKIPPED: 0 },
          summary: "One warning.",
          generated_by: "Argus",
        }}
        markdown="# ARGUS REPORT"
      />,
    );

    expect(markup).toContain("System");
    expect(markup).toContain("DEGRADED");
    expect(markup).toContain("Provider Configuration");
    expect(markup).toContain("Warnings");
    expect(markup).toContain("# ARGUS REPORT");
  });
});
