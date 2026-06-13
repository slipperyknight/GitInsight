// Thin client for the GitInsight read API. Requests go to /api/v1/* (same-origin) and Next
// rewrites them to the FastAPI backend (see next.config.ts). The prototype's dev-auth is the
// X-User-Id header — production swaps this for a real session.

import type { Digest, Identity, TeamRef, TeamSummary } from "./types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function get<T>(path: string, viewerId?: string): Promise<T> {
  const headers: Record<string, string> = {};
  if (viewerId) headers["X-User-Id"] = viewerId;
  const res = await fetch(`/api/v1${path}`, { headers, cache: "no-store" });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  identities: () => get<Identity[]>("/dev/identities"),
  teams: () => get<TeamRef[]>("/dev/teams"),
  digest: (viewerId: string) => get<Digest>("/me/digest", viewerId),
  teamSummary: (teamId: string, viewerId: string) =>
    get<TeamSummary>(`/teams/${teamId}/summary`, viewerId),
};
