import { dashboardUrl } from "./paths";
import type { DashboardPayload } from "./types";

export class DashboardError extends Error {}

/**
 * Fetch the dashboard payload from Core using a path-safe relative URL.
 * Never talks to Home Assistant and never uses external origins.
 */
export async function fetchDashboard(signal?: AbortSignal): Promise<DashboardPayload> {
  let response: Response;
  try {
    response = await fetch(dashboardUrl(), {
      headers: { Accept: "application/json" },
      cache: "no-store",
      signal,
    });
  } catch (err) {
    throw new DashboardError(
      err instanceof Error ? err.message : "Failed to reach the ThreadLens API"
    );
  }

  if (!response.ok) {
    throw new DashboardError(`HTTP ${response.status}`);
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new DashboardError("Invalid ThreadLens dashboard response");
  }

  if (!payload || typeof payload !== "object" || !("threadlens" in payload)) {
    throw new DashboardError("Invalid ThreadLens dashboard response");
  }

  return payload as DashboardPayload;
}
