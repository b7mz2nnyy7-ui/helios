import { formatCreatedAt, formatDuration, formatFileSize, videoTitle } from "../format";
import type { VideoSummary } from "../types";

interface VideoCardProps {
  video: VideoSummary;
  onSelect: (video: VideoSummary) => void;
}

export function VideoCard({ video, onSelect }: VideoCardProps) {
  return (
    <button
      className="group w-full overflow-hidden rounded-lg border border-[#dcddd8] bg-white text-left transition hover:border-[#bfc3bb] hover:shadow-[0_14px_34px_rgba(30,35,29,0.08)] focus:outline-none focus:ring-2 focus:ring-[#216e4e]/25"
      type="button"
      onClick={() => onSelect(video)}
    >
      <div className="relative aspect-video overflow-hidden bg-[#dfe4df]">
        <img
          className="size-full object-cover transition duration-300 group-hover:scale-[1.015]"
          src="/poster-placeholder.png"
          alt=""
        />
        <span className="absolute bottom-3 right-3 rounded bg-black/75 px-2 py-1 text-xs font-medium text-white">
          {formatDuration(video.duration)}
        </span>
      </div>
      <div className="px-5 py-5">
        <h2 className="truncate text-base font-semibold text-[#1b1e1a]">
          {videoTitle(video.filename)}
        </h2>
        <div className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 text-xs text-[#6b7069]">
          <span>{video.model}</span>
          <span className="text-right">{formatFileSize(video.size_bytes)}</span>
          <span className="col-span-2">{formatCreatedAt(video.created_at)}</span>
        </div>
      </div>
    </button>
  );
}
