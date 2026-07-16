import { useMemo } from "react";

import { agentCatalog } from "../data/agents";
import { getLocalSettings } from "../data/settings";

export function AgentsPage({ searchValue }: { searchValue: string }) {
  const agents = useMemo(() => {
    const query = searchValue.trim().toLowerCase();
    if (!query) {
      return agentCatalog;
    }
    return agentCatalog.filter((agent) =>
      `${agent.name} ${agent.area} ${agent.status} ${agent.capability}`
        .toLowerCase()
        .includes(query),
    );
  }, [searchValue]);

  return (
    <div>
      <PageHeading
        eyebrow="Company"
        title="Agents"
        description="The locally configured specialists that make up the Helios content company."
      />
      <div className="mt-10 overflow-hidden rounded-lg border border-[#dcddd8] bg-white">
        <div className="hidden grid-cols-[1fr_1fr_0.7fr_1.3fr] border-b border-[#e3e4df] px-5 py-3 text-xs font-semibold uppercase text-[#737970] md:grid">
          <span>Name</span>
          <span>Area</span>
          <span>Status</span>
          <span>Capability</span>
        </div>
        {agents.map((agent) => (
          <div
            className="grid gap-3 border-b border-[#e7e8e3] px-5 py-5 last:border-b-0 md:grid-cols-[1fr_1fr_0.7fr_1.3fr] md:items-center"
            key={agent.name}
          >
            <p className="text-sm font-semibold text-[#20231f]">{agent.name}</p>
            <p className="text-sm text-[#646a63]">{agent.area}</p>
            <p className="text-sm text-[#315c45]">{agent.status}</p>
            <p className="break-words font-mono text-xs text-[#555b54]">{agent.capability}</p>
          </div>
        ))}
        {agents.length === 0 ? (
          <p className="px-5 py-12 text-center text-sm text-[#6b7069]">
            No agents match your search.
          </p>
        ) : null}
      </div>
    </div>
  );
}

export function SettingsPage() {
  const settings = getLocalSettings();
  return (
    <div>
      <PageHeading
        eyebrow="Local development"
        title="Settings"
        description="Current local workspace settings. Changes are not persisted from this screen."
      />
      <dl className="mt-10 divide-y divide-[#e1e2dd] border-y border-[#d9dbd5]">
        {settings.map((setting) => (
          <div className="grid gap-2 py-5 sm:grid-cols-[220px_1fr]" key={setting.label}>
            <dt className="text-sm font-medium text-[#353934]">{setting.label}</dt>
            <dd className="break-words text-sm text-[#666c65]">{setting.value}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-5 text-xs leading-5 text-[#7a8078]">
        Credentials and provider secrets are intentionally excluded.
      </p>
    </div>
  );
}

function PageHeading({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <div className="max-w-2xl">
      <p className="text-xs font-semibold uppercase text-[#617066]">{eyebrow}</p>
      <h1 className="mt-2 text-3xl font-semibold text-[#171916]">{title}</h1>
      <p className="mt-4 text-sm leading-6 text-[#656b64]">{description}</p>
    </div>
  );
}
