import { describe, expect, it, vi } from "vitest";

import {
  isMissionActive,
  startMissionPolling,
} from "./missionPolling";
import type { Mission } from "./types";

function mission(status: Mission["status"]): Mission {
  return {
    id: "mission-1",
    title: "AI Agents",
    prompt: "AI Agents",
    platform: "YouTube",
    duration: 30,
    render_model: "gen4.5",
    status,
    created_at: "2026-07-16T10:00:00Z",
    updated_at: "2026-07-16T10:00:01Z",
    video_id: status === "COMPLETED" ? "video-1" : null,
    render_job_id: "render-1",
    pipeline_state: {
      current_stage: status === "COMPLETED" ? "Completed" : "Research",
      completed_stages: status === "COMPLETED" ? ["Research", "Script", "Storyboard", "Rendering", "Download"] : [],
      completed_task_ids: [],
    },
    error_message: status === "FAILED" ? "Mission execution failed." : null,
  };
}

class FakeScheduler {
  callbacks: Array<() => void> = [];
  delays: number[] = [];
  cleared: number[] = [];

  setTimeout(callback: () => void, delayMilliseconds: number): number {
    this.callbacks.push(callback);
    this.delays.push(delayMilliseconds);
    return this.callbacks.length;
  }

  clearTimeout(handle: number): void {
    this.cleared.push(handle);
  }

  runNext(): void {
    const callback = this.callbacks.shift();
    callback?.();
  }
}

describe("mission polling", () => {
  it("polls every two seconds until the mission completes", async () => {
    const scheduler = new FakeScheduler();
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(mission("RUNNING"))
      .mockResolvedValueOnce(mission("COMPLETED"));
    const updates: Mission[] = [];

    startMissionPolling({
      missionId: "mission-1",
      fetcher,
      scheduler,
      onUpdate: (updatedMission) => updates.push(updatedMission),
      onError: () => undefined,
    });

    expect(scheduler.delays).toEqual([2000]);
    scheduler.runNext();
    await vi.waitFor(() => expect(updates).toHaveLength(1));
    expect(scheduler.delays).toEqual([2000, 2000]);
    scheduler.runNext();
    await vi.waitFor(() => expect(updates).toHaveLength(2));
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(updates[1].status).toBe("COMPLETED");
    expect(scheduler.callbacks).toHaveLength(0);
  });

  it("stops polling at FAILED and reports request errors", async () => {
    const scheduler = new FakeScheduler();
    const updates: Mission[] = [];
    startMissionPolling({
      missionId: "mission-1",
      fetcher: vi.fn().mockResolvedValue(mission("FAILED")),
      scheduler,
      onUpdate: (updatedMission) => updates.push(updatedMission),
      onError: () => undefined,
    });
    scheduler.runNext();
    await vi.waitFor(() => expect(updates).toHaveLength(1));
    expect(scheduler.callbacks).toHaveLength(0);

    const failingScheduler = new FakeScheduler();
    const onError = vi.fn();
    startMissionPolling({
      missionId: "mission-2",
      fetcher: vi.fn().mockRejectedValue(new Error("offline")),
      scheduler: failingScheduler,
      onUpdate: () => undefined,
      onError,
    });
    failingScheduler.runNext();
    await vi.waitFor(() => expect(onError).toHaveBeenCalledOnce());
  });

  it("cancels pending polling and classifies active states", () => {
    const scheduler = new FakeScheduler();
    const cancel = startMissionPolling({
      missionId: "mission-1",
      fetcher: vi.fn(),
      scheduler,
      onUpdate: () => undefined,
      onError: () => undefined,
    });

    cancel();
    expect(scheduler.cleared).toEqual([1]);
    expect(isMissionActive(mission("QUEUED"))).toBe(true);
    expect(isMissionActive(mission("RUNNING"))).toBe(true);
    expect(isMissionActive(mission("COMPLETED"))).toBe(false);
    expect(isMissionActive(mission("FAILED"))).toBe(false);
  });
});
