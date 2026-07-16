import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import { createMission, fetchMissions } from "../api";
import { isMissionActive, startMissionPolling } from "../missionPolling";
import type {
  Mission,
  MissionDuration,
  MissionPlatform,
  MissionStage,
} from "../types";

interface MissionStudioProps {
  onMissionCompleted: (videoId: string) => void;
  onWatchVideo: (videoId: string) => void;
}

const platforms: readonly MissionPlatform[] = [
  "YouTube",
  "TikTok",
  "Instagram",
  "X",
];
const durations: readonly MissionDuration[] = [15, 30, 60];
const stages: readonly MissionStage[] = [
  "Research",
  "Script",
  "Storyboard",
  "Rendering",
  "Download",
  "Completed",
];

export function MissionStudio({
  onMissionCompleted,
  onWatchVideo,
}: MissionStudioProps) {
  const [prompt, setPrompt] = useState("");
  const [platform, setPlatform] = useState<MissionPlatform>("YouTube");
  const [duration, setDuration] = useState<MissionDuration>(30);
  const [missions, setMissions] = useState<Mission[]>([]);
  const [selectedMission, setSelectedMission] = useState<Mission | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchMissions(controller.signal)
      .then((result) => {
        setMissions(result);
        setSelectedMission((current) => current ?? result[0] ?? null);
      })
      .catch((requestError: unknown) => {
        if (requestError instanceof DOMException && requestError.name === "AbortError") {
          return;
        }
        setError("Existing missions could not be loaded.");
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!selectedMission || !isMissionActive(selectedMission)) {
      return undefined;
    }
    return startMissionPolling({
      missionId: selectedMission.id,
      onUpdate: (mission) => {
        setSelectedMission(mission);
        setMissions((current) => upsertMission(current, mission));
        if (mission.status === "COMPLETED" && mission.video_id) {
          onMissionCompleted(mission.video_id);
        }
      },
      onError: () => setError("Mission progress could not be refreshed."),
    });
  }, [onMissionCompleted, selectedMission]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!prompt.trim() || submitting) {
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const mission = await createMission({
        prompt: prompt.trim(),
        platform,
        duration,
        render_model: "gen4.5",
      });
      setSelectedMission(mission);
      setMissions((current) => upsertMission(current, mission));
      if (mission.status === "COMPLETED" && mission.video_id) {
        onMissionCompleted(mission.video_id);
      }
    } catch {
      setError("Mission could not be created. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <section className="max-w-4xl pt-4 md:pt-8">
        <p className="text-xs font-semibold uppercase text-[#617066]">Mission Studio</p>
        <h1 className="mt-4 max-w-3xl text-4xl font-semibold leading-tight text-[#171916] md:text-5xl">
          Create your next AI production
        </h1>
        <p className="mt-5 max-w-2xl text-base leading-7 text-[#60665f]">
          Describe your idea. Helios orchestrates the complete production.
        </p>
      </section>

      <form className="mt-12 max-w-5xl border-t border-[#d9dbd5] pt-9" onSubmit={submit}>
        <label className="text-sm font-semibold text-[#252824]" htmlFor="mission-prompt">
          Production brief
        </label>
        <textarea
          id="mission-prompt"
          className="mt-3 min-h-44 w-full resize-y rounded-lg border border-[#d4d6d0] bg-white p-5 text-base leading-7 text-[#20231f] outline-none transition placeholder:text-[#989d96] focus:border-[#216e4e] focus:ring-2 focus:ring-[#216e4e]/10"
          placeholder="A thoughtful short-form video about..."
          required
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
        />

        <div className="mt-8 grid gap-8 lg:grid-cols-[1.4fr_1fr_0.8fr]">
          <SegmentedField
            legend="Platform"
            values={platforms}
            selected={platform}
            onSelect={(value) => setPlatform(value as MissionPlatform)}
          />
          <SegmentedField
            legend="Video length"
            values={durations.map(String)}
            selected={String(duration)}
            suffix=" sec"
            onSelect={(value) => setDuration(Number(value) as MissionDuration)}
          />
          <label className="block text-sm font-semibold text-[#252824]">
            Render model
            <select
              className="mt-3 h-11 w-full rounded-md border border-[#d4d6d0] bg-white px-3 text-sm text-[#252824] outline-none focus:border-[#216e4e]"
              value="gen4.5"
              disabled
            >
              <option>gen4.5</option>
            </select>
          </label>
        </div>

        {error ? (
          <p className="mt-6 border-l-2 border-[#9e3f35] py-1 pl-4 text-sm text-[#7d3028]" role="alert">
            {error}
          </p>
        ) : null}
        <button
          className="mt-9 min-h-12 rounded-md bg-[#171916] px-7 py-3 text-sm font-semibold text-white transition hover:bg-[#30332f] disabled:cursor-not-allowed disabled:bg-[#aeb2ac]"
          type="submit"
          disabled={submitting || !prompt.trim()}
        >
          {submitting ? "Creating mission..." : "Create Mission"}
        </button>
      </form>

      {selectedMission ? (
        <MissionStatusPanel mission={selectedMission} onWatchVideo={onWatchVideo} />
      ) : null}

      {missions.length > 0 ? (
        <section className="mt-16 border-t border-[#d9dbd5] pt-8">
          <h2 className="text-lg font-semibold text-[#1b1e1a]">Recent missions</h2>
          <div className="mt-4 divide-y divide-[#e0e2dc] border-y border-[#d9dbd5]">
            {missions.map((mission) => (
              <button
                className="grid w-full gap-2 py-4 text-left sm:grid-cols-[1fr_auto_auto] sm:items-center sm:gap-6"
                type="button"
                key={mission.id}
                onClick={() => setSelectedMission(mission)}
              >
                <span className="truncate text-sm font-medium text-[#242724]">{mission.title}</span>
                <span className="text-xs text-[#6c726b]">{mission.platform}</span>
                <span className="text-xs font-semibold text-[#315c45]">{mission.status}</span>
              </button>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

export function MissionStatusPanel({
  mission,
  onWatchVideo,
}: {
  mission: Mission;
  onWatchVideo: (videoId: string) => void;
}) {
  return (
    <section className="mt-14 border-t border-[#d9dbd5] pt-9" aria-label="Mission progress">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase text-[#617066]">Current mission</p>
          <h2 className="mt-2 text-xl font-semibold text-[#1b1e1a]">{mission.title}</h2>
        </div>
        <span className="rounded bg-[#e8ece7] px-3 py-1.5 text-xs font-semibold text-[#315c45]">
          {mission.status}
        </span>
      </div>

      <ol className="mt-8 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
        {stages.map((stage) => {
          const completed = mission.pipeline_state.completed_stages.includes(stage);
          const current = mission.pipeline_state.current_stage === stage;
          return (
            <li className="border-t border-[#d9dbd5] pt-3" key={stage}>
              <span className={`text-xs font-semibold ${completed || current ? "text-[#2d6347]" : "text-[#969b94]"}`}>
                {completed ? "Complete" : current ? "Active" : "Pending"}
              </span>
              <p className="mt-1 text-sm text-[#343834]">{stage}</p>
            </li>
          );
        })}
      </ol>

      {mission.status === "COMPLETED" && mission.video_id ? (
        <button
          className="mt-8 rounded-md bg-[#171916] px-5 py-2.5 text-sm font-semibold text-white"
          type="button"
          onClick={() => onWatchVideo(mission.video_id as string)}
        >
          Watch Video
        </button>
      ) : null}
      {mission.status === "FAILED" ? (
        <div className="mt-8">
          <p className="text-sm text-[#7d3028]">
            {mission.error_message ?? "Mission execution failed."}
          </p>
          <button
            className="mt-4 cursor-not-allowed rounded-md bg-[#dfe2dc] px-5 py-2.5 text-sm font-semibold text-[#777d75]"
            type="button"
            disabled
          >
            Retry · Coming soon
          </button>
        </div>
      ) : null}
    </section>
  );
}

function SegmentedField({
  legend,
  values,
  selected,
  onSelect,
  suffix = "",
}: {
  legend: string;
  values: readonly string[];
  selected: string;
  onSelect: (value: string) => void;
  suffix?: string;
}) {
  return (
    <fieldset>
      <legend className="text-sm font-semibold text-[#252824]">{legend}</legend>
      <div className="mt-3 flex min-h-11 overflow-hidden rounded-md border border-[#d4d6d0] bg-white">
        {values.map((value) => (
          <label className="flex min-w-0 flex-1 cursor-pointer" key={value}>
            <input
              className="peer sr-only"
              type="radio"
              name={legend}
              value={value}
              checked={selected === value}
              onChange={() => onSelect(value)}
            />
            <span className="grid w-full place-items-center border-r border-[#e1e2dd] px-2 text-xs font-medium text-[#666c65] transition last:border-r-0 peer-checked:bg-[#edf2ed] peer-checked:text-[#1d5138]">
              {value}{suffix}
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

function upsertMission(missions: Mission[], mission: Mission): Mission[] {
  return [mission, ...missions.filter((item) => item.id !== mission.id)];
}
