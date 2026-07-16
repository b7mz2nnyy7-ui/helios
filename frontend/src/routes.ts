export const appRoutes = [
  { label: "Videos", path: "/videos" },
  { label: "System", path: "/system" },
  { label: "Missions", path: "/missions" },
  { label: "Agents", path: "/agents" },
  { label: "Publishing", path: "/publishing" },
  { label: "Settings", path: "/settings" },
] as const;

export type AppRoute = (typeof appRoutes)[number];
export type AppRoutePath = AppRoute["path"];

export function resolveRoute(pathname: string): AppRoute {
  const normalizedPath = normalizePath(pathname);
  return (
    appRoutes.find((route) => route.path === normalizedPath) ?? appRoutes[0]
  );
}

function normalizePath(pathname: string): string {
  if (pathname === "/") {
    return "/videos";
  }
  return pathname.length > 1 && pathname.endsWith("/")
    ? pathname.slice(0, -1)
    : pathname;
}
