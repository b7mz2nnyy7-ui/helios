import { useEffect, useMemo, useState } from "react";

import { fetchSystemHealth, fetchSystemReport } from "../api";
import { ErrorState } from "./ErrorState";
import { LoadingScreen } from "./LoadingScreen";
import type {
  CheckStatus,
  GuardianStatus,
  SystemCheck,
  SystemHealthReport,
} from "../types";

interface SystemPageProps {
  searchValue: string;
}

interface SystemReportViewProps {
  report: SystemHealthReport;
  markdown: string;
  searchValue?: string;
}

const statusStyles: Record<GuardianStatus | CheckStatus, string> = {
  HEALTHY: "bg-[#e8f1eb] text-[#1f6142]",
  DEGRADED: "bg-[#f4edda] text-[#765d1d]",
  UNHEALTHY: "bg-[#f3e4e1] text-[#8a352d]",
  PASS: "bg-[#e8f1eb] text-[#1f6142]",
  WARNING: "bg-[#f4edda] text-[#765d1d]",
  FAIL: "bg-[#f3e4e1] text-[#8a352d]",
  SKIPPED: "bg-[#eceeeb] text-[#626861]",
};

export function SystemPage({ searchValue }: SystemPageProps) {
  const [report, setReport] = useState<SystemHealthReport | null>(null);
  const [markdown, setMarkdown] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [requestVersion, setRequestVersion] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    Promise.all([
      fetchSystemHealth(controller.signal),
      fetchSystemReport(controller.signal),
    ])
      .then(([health, reportMarkdown]) => {
        if (active) {
          setReport(health);
          setMarkdown(reportMarkdown);
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
        setError("System health could not be loaded. Please try again.");
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
  if (error || !report) {
    return (
      <ErrorState
        message={error ?? "System health is unavailable."}
        onRetry={retry}
      />
    );
  }
  return (
    <SystemReportView
      report={report}
      markdown={markdown}
      searchValue={searchValue}
    />
  );
}

export function SystemReportView({
  report,
  markdown,
  searchValue = "",
}: SystemReportViewProps) {
  const filteredChecks = useMemo(() => {
    const query = searchValue.trim().toLowerCase();
    if (!query) {
      return report.checks;
    }
    return report.checks.filter((check) =>
      `${check.name} ${check.summary} ${check.status}`
        .toLowerCase()
        .includes(query),
    );
  }, [report.checks, searchValue]);
  const warnings = report.checks.filter((check) =>
    ["WARNING", "FAIL"].includes(check.status),
  );

  return (
    <div>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase text-[#617066]">Argus</p>
          <h1 className="mt-2 text-3xl font-semibold text-[#171916]">System</h1>
        </div>
        <span
          className={`w-fit rounded px-3 py-1.5 text-xs font-semibold ${statusStyles[report.overall_status]}`}
        >
          {report.overall_status}
        </span>
      </div>

      <section className="mt-9 grid grid-cols-1 gap-4 md:grid-cols-3" aria-label="System overview">
        <OverviewItem label="Health" value={report.overall_status} />
        <OverviewItem label="Warnings" value={String(warnings.length)} />
        <OverviewItem label="Last check" value={formatTimestamp(report.created_at)} />
      </section>

      <section className="mt-12">
        <div className="flex items-baseline justify-between gap-4">
          <h2 className="text-lg font-semibold text-[#1b1e1a]">Checks</h2>
          <p className="text-xs text-[#71766f]">{filteredChecks.length} shown</p>
        </div>
        <div className="mt-4 overflow-hidden rounded-lg border border-[#dcddd8] bg-white">
          {filteredChecks.map((check) => (
            <CheckRow key={check.id} check={check} />
          ))}
          {filteredChecks.length === 0 ? (
            <p className="px-5 py-8 text-sm text-[#6b7069]">No checks match your search.</p>
          ) : null}
        </div>
      </section>

      <section className="mt-12">
        <h2 className="text-lg font-semibold text-[#1b1e1a]">Warnings</h2>
        {warnings.length > 0 ? (
          <div className="mt-4 space-y-3">
            {warnings.map((warning) => (
              <div className="border-l-2 border-[#a9842e] py-2 pl-4" key={warning.id}>
                <p className="text-sm font-medium text-[#282b27]">{warning.name}</p>
                <p className="mt-1 text-sm text-[#6a6f68]">{warning.summary}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-3 text-sm text-[#687069]">No active warnings.</p>
        )}
      </section>

      <section className="mt-12">
        <h2 className="text-lg font-semibold text-[#1b1e1a]">Markdown Report</h2>
        <pre className="mt-4 max-h-[520px] overflow-auto whitespace-pre-wrap rounded-lg border border-[#dcddd8] bg-[#20231f] p-5 text-xs leading-6 text-[#e8ebe5]">
          {markdown}
        </pre>
      </section>
    </div>
  );
}

function OverviewItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[#dcddd8] bg-white px-5 py-5">
      <p className="text-xs font-medium text-[#70766e]">{label}</p>
      <p className="mt-3 break-words text-base font-semibold text-[#1b1e1a]">{value}</p>
    </div>
  );
}

function CheckRow({ check }: { check: SystemCheck }) {
  return (
    <div className="grid gap-3 border-b border-[#e5e6e1] px-5 py-4 last:border-b-0 sm:grid-cols-[minmax(150px,0.8fr)_minmax(220px,2fr)_auto] sm:items-center">
      <div>
        <p className="text-sm font-medium text-[#222521]">{check.name}</p>
        <p className="mt-1 text-xs text-[#7a8078]">{check.severity}</p>
      </div>
      <p className="text-sm text-[#626861]">{check.summary}</p>
      <span className={`w-fit rounded px-2.5 py-1 text-xs font-semibold ${statusStyles[check.status]}`}>
        {check.status}
      </span>
    </div>
  );
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
