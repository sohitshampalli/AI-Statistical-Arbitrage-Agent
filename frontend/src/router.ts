// A small hash router: the dashboard is served as static files by FastAPI,
// so hash routes need no server-side fallback and add no dependency.
import { useEffect, useState } from "react";

export const ROUTES = [
  { path: "/overview", label: "Overview" },
  { path: "/pairs", label: "Pair explorer" },
  { path: "/cointegration", label: "Cointegration" },
  { path: "/backtest", label: "Backtest" },
  { path: "/controls", label: "Controls" },
  { path: "/agent", label: "Agent" },
  { path: "/methodology", label: "Methodology" },
] as const;

export const GALLERY_PATH = "/dev/components";

export interface Route {
  path: string;
  params: URLSearchParams;
}

export function parseHash(hash: string): Route {
  const body = hash.replace(/^#/, "") || "/overview";
  const [path = "/overview", query = ""] = body.split("?", 2);
  return { path: path.startsWith("/") ? path : `/${path}`, params: new URLSearchParams(query) };
}

export function href(path: string, params?: Record<string, string>): string {
  const query = new URLSearchParams(params ?? {}).toString();
  return `#${path}${query ? `?${query}` : ""}`;
}

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parseHash(window.location.hash));
  useEffect(() => {
    const onChange = () => setRoute(parseHash(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}
