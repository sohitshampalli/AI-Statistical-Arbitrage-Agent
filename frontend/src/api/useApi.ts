// Load one endpoint into a React component, with explicit states for the
// loading, error and loaded views every page must design.
import { useEffect, useState } from "react";
import { ApiFailure, apiGet } from "./client";

export type ApiState<T> =
  | { status: "loading" }
  | { status: "error"; failure: ApiFailure }
  | { status: "ready"; data: T };

export function useApi<T>(
  path: string | null,
  params?: Record<string, string | number | undefined>,
): ApiState<T> {
  const key = path === null ? null : JSON.stringify([path, params ?? {}]);
  const [state, setState] = useState<{ key: string | null; value: ApiState<T> }>({
    key: null,
    value: { status: "loading" },
  });

  useEffect(() => {
    if (key === null || path === null) return;
    const controller = new AbortController();
    apiGet<T>(path, params, { signal: controller.signal })
      .then((data) => setState({ key, value: { status: "ready", data } }))
      .catch((error: unknown) => {
        if (error instanceof ApiFailure) setState({ key, value: { status: "error", failure: error } });
      });
    return () => controller.abort();
    // params is captured by key
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return state.key === key ? state.value : { status: "loading" };
}
