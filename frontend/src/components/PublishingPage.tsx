import { useEffect, useState } from "react";

import { fetchMissions } from "../api";
import type { Mission } from "../types";
import { ErrorState } from "./ErrorState";
import { LoadingScreen } from "./LoadingScreen";

export function PublishingPage() {
  const [missions, setMissions] = useState<Mission[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [requestVersion, setRequestVersion] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    fetchMissions(controller.signal)
      .then((result) => {
        if (active) {
          setMissions(result);
          setError(null);
        }
      })
      .catch((requestError: unknown) => {
        if (
          !active ||
          (requestError instanceof DOMException && requestError.name === "AbortError")
        ) {
          return;
        }
        setError("Publishing data could not be loaded.");
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
  }, [requestVersion]);

  const retry = () => {
    setError(null);
    setLoading(true);
    setRequestVersion((version) => version + 1);
  };

  if (loading) {
    return <LoadingScreen />;
  }
  if (error) {
    return <ErrorState message={error} onRetry={retry} />;
  }
  return <PublishingOverview missions={missions} />;
}

export function PublishingOverview({ missions }: { missions: Mission[] }) {
  return (
    <div>
      <div className="max-w-2xl">
        <p className="text-xs font-semibold uppercase text-[#617066]">Creator Foundation</p>
        <h1 className="mt-2 text-3xl font-semibold text-[#171916]">Publishing</h1>
        <p className="mt-4 text-sm leading-6 text-[#656b64]">
          Platform connections and publishing jobs will be managed here. Upload execution is not enabled yet.
        </p>
      </div>

      <section className="mt-12 border-t border-[#d9dbd5] pt-8">
        <div className="flex items-baseline justify-between gap-4">
          <h2 className="text-lg font-semibold text-[#1b1e1a]">Connected platforms</h2>
          <span className="text-xs font-semibold text-[#737970]">COMING SOON</span>
        </div>
        <p className="mt-4 text-sm text-[#6b7069]">No publishing targets connected</p>
      </section>

      <section className="mt-12 border-t border-[#d9dbd5] pt-8">
        <div className="flex items-baseline justify-between gap-4">
          <h2 className="text-lg font-semibold text-[#1b1e1a]">Missions</h2>
          <span className="text-sm text-[#737970]">{missions.length}</span>
        </div>
        {missions.length === 0 ? (
          <p className="mt-4 text-sm text-[#6b7069]">No missions available for publishing.</p>
        ) : (
          <div className="mt-4 divide-y divide-[#e1e2dd] border-y border-[#d9dbd5]">
            {missions.map((mission) => (
              <div className="grid gap-2 py-4 sm:grid-cols-[1fr_auto_auto] sm:items-center sm:gap-6" key={mission.id}>
                <span className="truncate text-sm font-medium text-[#252824]">{mission.title}</span>
                <span className="text-xs text-[#6d736c]">{mission.platform}</span>
                <span className="text-xs font-semibold text-[#3f5f4d]">{mission.status}</span>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="mt-12 border-t border-[#d9dbd5] pt-8">
        <h2 className="text-lg font-semibold text-[#1b1e1a]">Upload queue</h2>
        <p className="mt-4 text-sm text-[#6b7069]">No publishing jobs queued.</p>
      </section>
    </div>
  );
}
