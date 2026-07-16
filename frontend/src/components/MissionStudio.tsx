import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import { createMission, fetchMissions } from "../api";
import { isMissionActive, startMissionPolling } from "../missionPolling";
import type {
  Mission,
  MissionDuration,
  MissionPlatform,
  MissionStage,
  MissionStatus,
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
  const [statusFilter, setStatusFilter] = useState<MissionStatus | "ALL">("ALL");

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
        <>
          <MissionStatusPanel mission={selectedMission} onWatchVideo={onWatchVideo} />
          <MissionDetail mission={selectedMission} onWatchVideo={onWatchVideo} />
        </>
      ) : null}

      <MissionList
        missions={missions}
        selectedMissionId={selectedMission?.id ?? null}
        statusFilter={statusFilter}
        onFilterChange={setStatusFilter}
        onSelect={setSelectedMission}
      />
    </div>
  );
}

export function MissionList({
  missions,
  selectedMissionId,
  statusFilter,
  onFilterChange,
  onSelect,
}: {
  missions: Mission[];
  selectedMissionId: string | null;
  statusFilter: MissionStatus | "ALL";
  onFilterChange: (status: MissionStatus | "ALL") => void;
  onSelect: (mission: Mission) => void;
}) {
  const filters: ReadonlyArray<MissionStatus | "ALL"> = [
    "ALL",
    "RUNNING",
    "COMPLETED",
    "FAILED",
    "QUEUED",
  ];
  const filtered = missions.filter(
    (mission) => statusFilter === "ALL" || mission.status === statusFilter,
  );
  return (
    <section className="mt-16 border-t border-[#d9dbd5] pt-8">
      <div className="flex flex-wrap items-end justify-between gap-5">
        <div>
          <p className="text-xs font-semibold uppercase text-[#617066]">History</p>
          <h2 className="mt-2 text-xl font-semibold text-[#1b1e1a]">Missions</h2>
        </div>
        <div className="flex flex-wrap gap-1" aria-label="Filter missions">
          {filters.map((filter) => (
            <button
              className={`rounded px-3 py-1.5 text-xs font-semibold transition ${
                filter === statusFilter
                  ? "bg-[#253129] text-white"
                  : "bg-[#eceeea] text-[#626861] hover:bg-[#dfe3dd]"
              }`}
              type="button"
              key={filter}
              aria-pressed={filter === statusFilter}
              onClick={() => onFilterChange(filter)}
            >
              {filter === "ALL" ? "All" : titleCase(filter)}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-5 overflow-hidden rounded-lg border border-[#dcddd8] bg-white">
        <div className="hidden grid-cols-[1.5fr_0.7fr_0.8fr_0.9fr_0.8fr_0.6fr] border-b border-[#e3e4df] px-5 py-3 text-xs font-semibold uppercase text-[#737970] lg:grid">
          <span>Title</span>
          <span>Status</span>
          <span>Platform</span>
          <span>Created</span>
          <span>Render</span>
          <span>Video</span>
        </div>
        {filtered.map((mission) => (
          <button
            className={`grid w-full gap-2 border-b border-[#e7e8e3] px-5 py-4 text-left last:border-b-0 lg:grid-cols-[1.5fr_0.7fr_0.8fr_0.9fr_0.8fr_0.6fr] lg:items-center ${
              mission.id === selectedMissionId ? "bg-[#f1f4f0]" : "hover:bg-[#f8f9f7]"
            }`}
            type="button"
            key={mission.id}
            onClick={() => onSelect(mission)}
          >
            <span className="truncate text-sm font-medium text-[#242724]">{mission.title}</span>
            <span className="text-xs font-semibold text-[#315c45]">{mission.status}</span>
            <span className="text-xs text-[#656b64]">{mission.platform}</span>
            <span className="text-xs text-[#656b64]">{formatTimestamp(mission.created_at)}</span>
            <span className="text-xs text-[#656b64]">{mission.render_status ?? "Not started"}</span>
            <span className="text-xs text-[#656b64]">{mission.video_id ? "Available" : "No"}</span>
          </button>
        ))}
        {filtered.length === 0 ? (
          <p className="px-5 py-10 text-center text-sm text-[#6b7069]">
            No missions match this filter.
          </p>
        ) : null}
      </div>
    </section>
  );
}

export function MissionDetail({
  mission,
  onWatchVideo,
}: {
  mission: Mission;
  onWatchVideo: (videoId: string) => void;
}) {
  const asset = mission.media_asset;
  return (
    <section className="mt-12 border-t border-[#d9dbd5] pt-8" aria-label="Mission detail">
      <h2 className="text-xl font-semibold text-[#1b1e1a]">Mission detail</h2>
      <div className="mt-6 grid gap-x-10 gap-y-7 lg:grid-cols-2">
        <DetailField label="Prompt" value={mission.prompt} />
        <DetailField label="Pipeline" value={`${mission.pipeline_state.current_stage} · ${mission.pipeline_state.completed_task_ids.length} tasks completed`} />
        <DetailField label="Render" value={`${mission.render_status ?? "Not started"}${mission.render_job_id ? ` · ${mission.render_job_id}` : ""}`} />
        <DetailField label="Video" value={mission.video_id ?? "No video available"} />
        <DetailField label="Created" value={formatTimestamp(mission.created_at)} />
        <DetailField label="Updated" value={formatTimestamp(mission.updated_at)} />
        <DetailField label="Platform" value={mission.platform} />
        <DetailField label="Model" value={mission.render_model} />
      </div>

      <div className="mt-10 border-t border-[#e1e2dd] pt-7">
        <h3 className="text-sm font-semibold text-[#252824]">Asset</h3>
        {asset ? (
          <dl className="mt-4 grid gap-x-10 gap-y-5 sm:grid-cols-2">
            <DetailField label="Asset ID" value={asset.asset_id} />
            <DetailField label="Provider" value={asset.provider} />
            <DetailField label="Format" value={asset.format} />
            <DetailField label="Type" value={asset.asset_type} />
            <DetailField label="Name" value={asset.name} />
            <DetailField label="Metadata" value={JSON.stringify(asset.metadata)} />
          </dl>
        ) : (
          <p className="mt-3 text-sm text-[#6b7069]">No media asset created yet.</p>
        )}
      </div>

      <div className="mt-10 border-t border-[#e1e2dd] pt-7">
        <h3 className="text-sm font-semibold text-[#252824]">Publishing</h3>
        <p className="mt-3 text-sm text-[#6b7069]">No publishing targets connected</p>
      </div>

      {mission.video_id ? (
        <button
          className="mt-8 rounded-md bg-[#171916] px-5 py-2.5 text-sm font-semibold text-white"
          type="button"
          onClick={() => onWatchVideo(mission.video_id as string)}
        >
          Watch Video
        </button>
      ) : null}
    </section>
  );
}

function DetailField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase text-[#777d75]">{label}</dt>
      <dd className="mt-2 break-words text-sm leading-6 text-[#343834]">{value}</dd>
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

function titleCase(value: string): string {
  return value.charAt(0) + value.slice(1).toLowerCase();
}

function formatTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Unknown";
  }
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}
