export interface LocalSetting {
  label: string;
  value: string;
}

export function getLocalSettings(): readonly LocalSetting[] {
  const frontendPort =
    typeof window === "undefined" ? "5173" : window.location.port || "5173";
  return [
    { label: "API base URL", value: "/api" },
    { label: "Theme", value: "System light" },
    { label: "Browser auto-open", value: "Enabled" },
    { label: "Backend port", value: "8001 (preferred)" },
    { label: "Frontend port", value: `${frontendPort} (active)` },
  ];
}
