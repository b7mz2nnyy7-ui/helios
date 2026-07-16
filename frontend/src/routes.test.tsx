import { readFileSync } from "node:fs";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import App from "./App";
import { appRoutes, resolveRoute } from "./routes";

describe("Helios frontend routes", () => {
  it.each([
    ["/missions", "Create your next AI production"],
    ["/agents", "Agents"],
    ["/settings", "Settings"],
  ])("renders direct route %s", (pathname, heading) => {
    const markup = renderToStaticMarkup(<App pathname={pathname} />);

    expect(markup).toContain(`>${heading}</h1>`);
    expect(markup).toContain(`href="${pathname}" aria-current="page"`);
  });

  it("loads the publishing route directly with its active navigation", () => {
    const markup = renderToStaticMarkup(<App pathname="/publishing" />);

    expect(markup).toContain("Starting Helios");
    expect(markup).toContain('href="/publishing" aria-current="page"');
  });

  it("resolves every supported direct path and preserves it after reload", () => {
    for (const route of appRoutes) {
      expect(resolveRoute(route.path)).toBe(route);
      expect(resolveRoute(`${route.path}/`)).toBe(route);
    }
  });

  it("keeps the video route in its React loading state until data arrives", () => {
    const markup = renderToStaticMarkup(<App pathname="/videos" />);

    expect(markup).toContain("Starting Helios");
    expect(markup).toContain("Preparing your workspace");
  });

  it("keeps the system route in its React loading state until data arrives", () => {
    const markup = renderToStaticMarkup(<App pathname="/system" />);

    expect(markup).toContain("Starting Helios");
    expect(markup).toContain('href="/system" aria-current="page"');
  });

  it("contains a static loader before the React entry script", () => {
    const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");
    const loaderPosition = html.indexOf("Starting Helios");
    const scriptPosition = html.indexOf('/src/main.tsx');

    expect(loaderPosition).toBeGreaterThan(-1);
    expect(scriptPosition).toBeGreaterThan(loaderPosition);
    expect(html).toContain("helios-loader__orbit");
  });

  it("falls back safely to videos for an unknown path", () => {
    expect(resolveRoute("/unknown").path).toBe("/videos");
  });
});
