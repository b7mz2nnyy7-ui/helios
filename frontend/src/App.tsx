import { useEffect, useMemo, useState } from "react";

import { fetchVideos } from "./api";
import { AppShell } from "./components/AppShell";
import { EmptyState } from "./components/EmptyState";
import { VideoCard } from "./components/VideoCard";
import { VideoPlayerModal } from "./components/VideoPlayerModal";
import { matchesVideoSearch } from "./format";
import type { VideoSummary } from "./types";

export default function App() {
  const [videos, setVideos] = useState<VideoSummary[]>([]);
  const [selectedVideo, setSelectedVideo] = useState<VideoSummary | null>(null);
  const [searchValue, setSearchValue] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchVideos(controller.signal)
      .then(setVideos)
      .catch((requestError: unknown) => {
        if (requestError instanceof DOMException && requestError.name === "AbortError") {
          return;
        }
        setError("Videos could not be loaded.");
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  const filteredVideos = useMemo(() => {
    return videos.filter((video) => matchesVideoSearch(video, searchValue));
  }, [searchValue, videos]);

  return (
    <AppShell searchValue={searchValue} onSearchChange={setSearchValue}>
      <div className="flex items-end justify-between gap-5">
        <div>
          <p className="text-xs font-semibold uppercase text-[#617066]">Library</p>
          <h1 className="mt-2 text-3xl font-semibold text-[#171916]">Videos</h1>
        </div>
        {!loading && !error && videos.length > 0 ? (
          <p className="text-sm text-[#71766f]">
            {videos.length} {videos.length === 1 ? "production" : "productions"}
          </p>
        ) : null}
      </div>

      {loading ? (
        <div className="mt-10 grid grid-cols-1 gap-7 lg:grid-cols-2 2xl:grid-cols-3">
          {[0, 1, 2].map((item) => (
            <div
              className="aspect-[1.28] animate-pulse rounded-lg border border-[#e0e1dc] bg-white"
              key={item}
            />
          ))}
        </div>
      ) : null}

      {error ? (
        <div className="mt-10 border-l-2 border-[#9e3f35] py-2 pl-4 text-sm text-[#7d3028]">
          {error}
        </div>
      ) : null}

      {!loading && !error && videos.length === 0 ? <EmptyState /> : null}

      {!loading && !error && videos.length > 0 && filteredVideos.length === 0 ? (
        <p className="mt-16 text-sm text-[#6b7069]">
          No videos match “{searchValue}”.
        </p>
      ) : null}

      {!loading && !error && filteredVideos.length > 0 ? (
        <section
          className="mt-9 grid grid-cols-1 gap-7 lg:grid-cols-2 2xl:grid-cols-3"
          aria-label="Video productions"
        >
          {filteredVideos.map((video) => (
            <VideoCard key={video.id} video={video} onSelect={setSelectedVideo} />
          ))}
        </section>
      ) : null}

      {selectedVideo ? (
        <VideoPlayerModal
          video={selectedVideo}
          onClose={() => setSelectedVideo(null)}
        />
      ) : null}
    </AppShell>
  );
}
