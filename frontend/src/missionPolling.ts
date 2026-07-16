import { fetchMission } from "./api";
import type { Mission } from "./types";

export interface MissionPollScheduler {
  setTimeout(callback: () => void, delayMilliseconds: number): number;
  clearTimeout(handle: number): void;
}

interface MissionPollingOptions {
  missionId: string;
  onUpdate: (mission: Mission) => void;
  onError: () => void;
  fetcher?: (missionId: string) => Promise<Mission>;
  scheduler?: MissionPollScheduler;
  intervalMilliseconds?: number;
}

const browserScheduler: MissionPollScheduler = {
  setTimeout: (callback, delayMilliseconds) =>
    window.setTimeout(callback, delayMilliseconds),
  clearTimeout: (handle) => window.clearTimeout(handle),
};

export function isMissionActive(mission: Mission): boolean {
  return mission.status === "QUEUED" || mission.status === "RUNNING";
}

export function startMissionPolling({
  missionId,
  onUpdate,
  onError,
  fetcher = fetchMission,
  scheduler = browserScheduler,
  intervalMilliseconds = 2000,
}: MissionPollingOptions): () => void {
  if (!missionId.trim()) {
    throw new Error("missionId must not be empty.");
  }
  if (intervalMilliseconds <= 0) {
    throw new Error("intervalMilliseconds must be greater than 0.");
  }
  let active = true;
  let timeoutHandle: number | null = null;

  const schedule = () => {
    timeoutHandle = scheduler.setTimeout(() => {
      void poll();
    }, intervalMilliseconds);
  };
  const poll = async () => {
    try {
      const mission = await fetcher(missionId);
      if (!active) {
        return;
      }
      onUpdate(mission);
      if (isMissionActive(mission)) {
        schedule();
      }
    } catch {
      if (active) {
        onError();
      }
    }
  };

  schedule();
  return () => {
    active = false;
    if (timeoutHandle !== null) {
      scheduler.clearTimeout(timeoutHandle);
    }
  };
}
