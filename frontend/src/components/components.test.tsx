import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { VideoSummary } from "../types";
import { AppShell } from "./AppShell";
import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";
import { LoadingScreen } from "./LoadingScreen";
import { MissionStatusPanel, MissionStudio } from "./MissionStudio";
import { VideoCard } from "./VideoCard";
import { VideoPlayerModal } from "./VideoPlayerModal";
import { SystemReportView } from "./SystemPage";
import { AgentsPage, SettingsPage } from "./WorkspacePages";
import type { Mission } from "../types";

const video: VideoSummary = {
  id: "video-1",
  filename: "launch-film.mp4",
  created_at: "2026-07-16T10:00:00Z",
  duration: 65,
  size_bytes: 1_572_864,
  sha256: "a".repeat(64),
  model: "gen4.5",
};

const completedMission: Mission = {
  id: "mission-1",
  title: "AI Agents",
  prompt: "AI Agents",
  platform: "YouTube",
  duration: 30,
  render_model: "gen4.5",
  status: "COMPLETED",
  created_at: "2026-07-16T10:00:00Z",
  updated_at: "2026-07-16T10:01:00Z",
  video_id: "video-1",
  render_job_id: "render-1",
  pipeline_state: {
    current_stage: "Completed",
    completed_stages: ["Research", "Script", "Storyboard", "Rendering", "Download"],
    completed_task_ids: Array.from({ length: 12 }, (_, index) => `task-${index}`),
  },
  error_message: null,
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

  it("marks the selected route and links every sidebar destination", () => {
    const markup = renderToStaticMarkup(
      <AppShell
        searchValue=""
        onSearchChange={() => undefined}
        activePath="/agents"
      >
        <p>Agents content</p>
      </AppShell>,
    );

    expect(markup).toContain('href="/videos"');
    expect(markup).toContain('href="/system"');
    expect(markup).toContain('href="/missions"');
    expect(markup).toContain('href="/agents" aria-current="page"');
    expect(markup).toContain('href="/settings"');
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
    expect(markup).not.toContain("Starting Helios");
  });

  it("renders the Mission Studio form with all MVP controls", () => {
    const markup = renderToStaticMarkup(
      <MissionStudio
        onMissionCompleted={() => undefined}
        onWatchVideo={() => undefined}
      />,
    );

    expect(markup).toContain("Create your next AI production");
    expect(markup).toContain("Describe your idea. Helios orchestrates the complete production.");
    expect(markup).toContain("YouTube");
    expect(markup).toContain("TikTok");
    expect(markup).toContain("Instagram");
    expect(markup).toContain("15 sec");
    expect(markup).toContain("30 sec");
    expect(markup).toContain("60 sec");
    expect(markup).toContain("gen4.5");
    expect(markup).toContain("Create Mission");
  });

  it("renders completed and failed mission states honestly", () => {
    const completedMarkup = renderToStaticMarkup(
      <MissionStatusPanel
        mission={completedMission}
        onWatchVideo={() => undefined}
      />,
    );
    const failedMarkup = renderToStaticMarkup(
      <MissionStatusPanel
        mission={{
          ...completedMission,
          status: "FAILED",
          video_id: null,
          pipeline_state: {
            ...completedMission.pipeline_state,
            current_stage: "Rendering",
          },
          error_message: "Mission execution failed.",
        }}
        onWatchVideo={() => undefined}
      />,
    );

    expect(completedMarkup).toContain("Watch Video");
    expect(completedMarkup).toContain("Completed");
    expect(failedMarkup).toContain("Mission execution failed.");
    expect(failedMarkup).toContain("Retry · Coming soon");
    expect(failedMarkup).toContain("disabled");
  });

  it("renders the typed local agent catalog", () => {
    const markup = renderToStaticMarkup(<AgentsPage searchValue="" />);

    expect(markup).toContain("Agents");
    expect(markup).toContain("Atlas");
    expect(markup).toContain("Helios");
    expect(markup).toContain("TREND_RESEARCH");
    expect(markup).toContain("CEO");
  });

  it("renders only safe local settings", () => {
    const markup = renderToStaticMarkup(<SettingsPage />);

    expect(markup).toContain("API base URL");
    expect(markup).toContain("Theme");
    expect(markup).toContain("Browser auto-open");
    expect(markup).toContain("Backend port");
    expect(markup).toContain("Frontend port");
    expect(markup.toLowerCase()).not.toContain("api key");
  });

  it("renders a branded loading state instead of a blank screen", () => {
    const markup = renderToStaticMarkup(<LoadingScreen />);

    expect(markup).toContain("Starting Helios");
    expect(markup).toContain("Preparing your workspace");
    expect(markup).toContain('role="status"');
  });

  it("renders a controlled error state with retry", () => {
    const markup = renderToStaticMarkup(
      <ErrorState message="Data is unavailable." onRetry={() => undefined} />,
    );

    expect(markup).toContain("Something went wrong");
    expect(markup).toContain("Data is unavailable.");
    expect(markup).toContain("Retry");
    expect(markup).not.toContain("stack");
  });
});
