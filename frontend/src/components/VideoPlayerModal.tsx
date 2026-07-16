import { useEffect } from "react";

import { videoStreamUrl } from "../api";
import { formatCreatedAt, formatDuration, formatFileSize, videoTitle } from "../format";
import type { VideoSummary } from "../types";

interface VideoPlayerModalProps {
  video: VideoSummary;
  onClose: () => void;
}

export function VideoPlayerModal({ video, onClose }: VideoPlayerModalProps) {
  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-[#10120f]/80 p-4 backdrop-blur-sm md:p-10"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <section
        className="w-full max-w-[1280px] overflow-hidden rounded-lg bg-[#111310] shadow-2xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="video-player-title"
      >
        <div className="relative aspect-video bg-black">
          <video
            className="size-full"
            controls
            autoPlay
            preload="metadata"
            poster="/poster-placeholder.png"
            src={videoStreamUrl(video.id)}
          />
          <button
            className="absolute right-4 top-4 grid size-9 place-items-center rounded-full bg-black/70 text-xl text-white transition hover:bg-black"
            type="button"
            onClick={onClose}
            title="Close player"
            aria-label="Close player"
          >
            ×
          </button>
        </div>
        <div className="flex flex-col gap-3 px-5 py-5 text-white md:flex-row md:items-center md:justify-between md:px-7">
          <div className="min-w-0">
            <h2 id="video-player-title" className="truncate text-lg font-semibold">
              {videoTitle(video.filename)}
            </h2>
            <p className="mt-1 text-sm text-[#aeb4ab]">
              {formatCreatedAt(video.created_at)}
            </p>
          </div>
          <dl className="grid w-full shrink-0 grid-cols-3 gap-3 text-xs md:w-auto md:gap-6 md:text-sm">
            <div className="min-w-0">
              <dt className="text-[#858c82]">Duration</dt>
              <dd className="mt-1">{formatDuration(video.duration)}</dd>
            </div>
            <div className="min-w-0">
              <dt className="text-[#858c82]">Model</dt>
              <dd className="mt-1 break-words">{video.model}</dd>
            </div>
            <div className="min-w-0">
              <dt className="text-[#858c82]">Size</dt>
              <dd className="mt-1">{formatFileSize(video.size_bytes)}</dd>
            </div>
          </dl>
        </div>
      </section>
    </div>
  );
}
