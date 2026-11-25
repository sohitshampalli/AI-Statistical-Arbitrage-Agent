// Typed access to the dashboard API. Every response type comes from
// src/api/types.ts, generated from the backend's pydantic models.
import type { ErrorBody } from "./types";

export class ApiFailure extends Error {
  readonly status: number;
  readonly endpoint: string;
  readonly body: ErrorBody | null;

  constructor(status: number, endpoint: string, body: ErrorBody | null) {
    super(body?.message ?? `request to ${endpoint} failed with status ${status}`);
    this.name = "ApiFailure";
    this.status = status;
    this.endpoint = endpoint;
    this.body = body;
  }

  get runId(): string | null {
    return this.body?.run_id ?? null;
  }
}

function isErrorBody(value: unknown): value is ErrorBody {
  return (
    typeof value === "object" &&
    value !== null &&
    "error" in value &&
    "message" in value &&
    "endpoint" in value
  );
}

export function buildUrl(path: string, params?: Record<string, string | number | undefined>) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined) query.set(key, String(value));
  }
  const text = query.toString();
  return text ? `${path}?${text}` : path;
}

export async function apiGet<T>(
  path: string,
  params?: Record<string, string | number | undefined>,
  init?: { signal?: AbortSignal },
): Promise<T> {
  const url = buildUrl(path, params);
  let response: Response;
  try {
    response = await fetch(url, { headers: { Accept: "application/json" }, signal: init?.signal });
  } catch (error) {
    if ((error as Error).name === "AbortError") throw error;
    throw new ApiFailure(0, path, null);
  }
  if (!response.ok) {
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      body = null;
    }
    throw new ApiFailure(response.status, path, isErrorBody(body) ? body : null);
  }
  return (await response.json()) as T;
}
