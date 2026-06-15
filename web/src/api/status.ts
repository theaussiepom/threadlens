import { statusUrl } from "./paths";
import type { DiagnosticsConfig } from "@/lib/monitoringGuide";

export interface StatusPayload {
  status: string;
  version: string | null;
  diagnostics?: DiagnosticsConfig;
}

export async function fetchStatus(signal?: AbortSignal): Promise<StatusPayload> {
  const response = await fetch(statusUrl(), {
    headers: { Accept: "application/json" },
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return (await response.json()) as StatusPayload;
}
