import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { fetchVideos } from "./api";
import { AppShell } from "./components/AppShell";
import { EmptyState } from "./components/EmptyState";
import { ErrorState } from "./components/ErrorState";
import { LoadingScreen } from "./components/LoadingScreen";
import { MissionStudio } from "./components/MissionStudio";
import { PublishingPage } from "./components/PublishingPage";
import { SystemPage } from "./components/SystemPage";
import { VideoCard } from "./components/VideoCard";
import { VideoPlayerModal } from "./components/VideoPlayerModal";
import {
  AgentsPage,
  SettingsPage,
} from "./components/WorkspacePages";
import { matchesVideoSearch } from "./format";
import { resolveRoute } from "./routes";
import type { AppRoutePath } from "./routes";
import type { VideoSummary } from "./types";

interface AppProps {
  pathname?: string;
}

export default function App({ pathname }: AppProps) {
  const [currentPath, setCurrentPath] = useState(
    pathname ?? window.location.pathname,
  );
  const [galleryRevision, setGalleryRevision] = useState(0);
  const [videoToOpen, setVideoToOpen] = useState<string | null>(null);
  const route = resolveRoute(currentPath);
  const [searchValue, setSearchValue] = useState("");

  useEffect(() => {
    if (pathname !== undefined) {
      return undefined;
    }
    const handlePopState = () => setCurrentPath(window.location.pathname);
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, [pathname]);

  const navigate = useCallback(
    (path: AppRoutePath) => {
      if (pathname === undefined) {
        window.history.pushState({}, "", path);
        window.scrollTo({ top: 0, behavior: "smooth" });
      }
      setCurrentPath(path);
      setSearchValue("");
    },
    [pathname],
  );

  const missionCompleted = useCallback(() => {
    setGalleryRevision((revision) => revision + 1);
  }, []);

  const watchVideo = useCallback(
    (videoId: string) => {
      setVideoToOpen(videoId);
      setGalleryRevision((revision) => revision + 1);
      navigate("/videos");
    },
    [navigate],
  );

  if (route.path === "/videos") {
    return (
      <VideosRoute
        searchValue={searchValue}
        onSearchChange={setSearchValue}
        onNavigate={navigate}
        refreshKey={galleryRevision}
        initialVideoId={videoToOpen}
        onInitialVideoOpened={() => setVideoToOpen(null)}
      />
    );
  }
  if (route.path === "/system") {
    return (
      <AppShell
        searchValue={searchValue}
        onSearchChange={setSearchValue}
        activePath={route.path}
        onNavigate={navigate}
        searchLabel="Search system checks"
        searchPlaceholder="Search system checks"
      >
        <SystemPage searchValue={searchValue} />
      </AppShell>
    );
  }
  if (route.path === "/missions") {
    return (
      <StaticRouteShell
        activePath={route.path}
        searchValue={searchValue}
        onSearchChange={setSearchValue}
        onNavigate={navigate}
      >
        <MissionStudio
          onMissionCompleted={missionCompleted}
          onWatchVideo={watchVideo}
        />
      </StaticRouteShell>
    );
  }
  if (route.path === "/agents") {
    return (
      <StaticRouteShell
        activePath={route.path}
        searchValue={searchValue}
        onSearchChange={setSearchValue}
        onNavigate={navigate}
        searchLabel="Search agents"
        searchPlaceholder="Search agents"
      >
        <AgentsPage searchValue={searchValue} />
      </StaticRouteShell>
    );
  }
  if (route.path === "/publishing") {
    return (
      <StaticRouteShell
        activePath={route.path}
        searchValue={searchValue}
        onSearchChange={setSearchValue}
        onNavigate={navigate}
        searchLabel="Search publishing"
        searchPlaceholder="Search publishing"
      >
        <PublishingPage />
      </StaticRouteShell>
    );
  }
  return (
    <StaticRouteShell
      activePath={route.path}
      searchValue={searchValue}
      onSearchChange={setSearchValue}
      onNavigate={navigate}
    >
      <SettingsPage />
    </StaticRouteShell>
  );
}

function VideosRoute({
  searchValue,
  onSearchChange,
  onNavigate,
  refreshKey,
  initialVideoId,
  onInitialVideoOpened,
}: {
  searchValue: string;
  onSearchChange: (value: string) => void;
  onNavigate: (path: AppRoutePath) => void;
  refreshKey: number;
  initialVideoId: string | null;
  onInitialVideoOpened: () => void;
}) {
  const [videos, setVideos] = useState<VideoSummary[]>([]);
  const [selectedVideo, setSelectedVideo] = useState<VideoSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [requestVersion, setRequestVersion] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    fetchVideos(controller.signal)
      .then((result) => {
        if (active) {
          setVideos(result);
          setError(null);
          if (initialVideoId) {
            const requestedVideo = result.find((video) => video.id === initialVideoId);
            if (requestedVideo) {
              setSelectedVideo(requestedVideo);
              onInitialVideoOpened();
            }
          }
        }
      })
      .catch((requestError: unknown) => {
        if (
          !active ||
          (requestError instanceof DOMException && requestError.name === "AbortError")
        ) {
          return;
        }
        setError("The video library could not be loaded. Please try again.");
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [initialVideoId, onInitialVideoOpened, refreshKey, requestVersion]);

  const filteredVideos = useMemo(() => {
    return videos.filter((video) => matchesVideoSearch(video, searchValue));
  }, [searchValue, videos]);

  const retry = () => {
    setError(null);
    setLoading(true);
    setRequestVersion((version) => version + 1);
  };

  if (loading) {
    return <LoadingScreen />;
  }

  return (
    <AppShell
      searchValue={searchValue}
      onSearchChange={onSearchChange}
      activePath="/videos"
      onNavigate={onNavigate}
    >
      <div className="flex items-end justify-between gap-5">
        <div>
          <p className="text-xs font-semibold uppercase text-[#617066]">Library</p>
          <h1 className="mt-2 text-3xl font-semibold text-[#171916]">Videos</h1>
        </div>
        {!error && videos.length > 0 ? (
          <p className="text-sm text-[#71766f]">
            {videos.length} {videos.length === 1 ? "production" : "productions"}
          </p>
        ) : null}
      </div>

      {error ? (
        <ErrorState
          message={error}
          onRetry={retry}
          title="Videos are unavailable"
        />
      ) : null}
      {!error && videos.length === 0 ? <EmptyState /> : null}
      {!error && videos.length > 0 && filteredVideos.length === 0 ? (
        <p className="mt-16 text-sm text-[#6b7069]">
          No videos match “{searchValue}”.
        </p>
      ) : null}
      {!error && filteredVideos.length > 0 ? (
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

function StaticRouteShell({
  activePath,
  children,
  searchValue,
  onSearchChange,
  onNavigate,
  searchLabel = "Search workspace",
  searchPlaceholder = "Search workspace",
}: {
  activePath: AppRoutePath;
  children: ReactNode;
  searchValue: string;
  onSearchChange: (value: string) => void;
  onNavigate: (path: AppRoutePath) => void;
  searchLabel?: string;
  searchPlaceholder?: string;
}) {
  return (
    <AppShell
      searchValue={searchValue}
      onSearchChange={onSearchChange}
      activePath={activePath}
      onNavigate={onNavigate}
      searchLabel={searchLabel}
      searchPlaceholder={searchPlaceholder}
    >
      {children}
    </AppShell>
  );
}
