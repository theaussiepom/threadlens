import { HEALTH_PATH, healthUrl, resolveUrl, STATUS_PATH, statusUrl } from "./paths";
import type { DiagnosticsConfig } from "@/lib/monitoringGuide";

export interface CollectorOtbrStatus {
  configured: number;
  collector_running: boolean;
  reachable: number;
  unreachable: number;
  last_poll_at: string | null;
}

export interface CollectorMatterStatus {
  configured: number;
  collector_running: boolean;
  connected: number;
  disconnected: number;
  nodes_seen: number;
  unavailable_nodes: number;
  last_event_at: string | null;
}

export interface CollectorMdnsStatus {
  enabled: boolean;
  services_configured: number;
  observer_running: boolean;
  observation_degraded: boolean | null;
}

export interface CollectorMqttStatus {
  enabled: boolean;
  connected: boolean;
  publisher_running: boolean;
  homeassistant_discovery_enabled: boolean;
  last_publish_at: string | null;
  last_error: string | null;
}

export interface ConfiguredSource {
  id: string;
  name: string;
}

export interface StatusPayload {
  status: string;
  service: string;
  version: string | null;
  mode: string;
  site: { name: string };
  collectors: {
    otbr: CollectorOtbrStatus;
    matter: CollectorMatterStatus;
    mdns: CollectorMdnsStatus;
    mqtt: CollectorMqttStatus;
  };
  agents: Record<string, unknown>;
  storage: {
    sqlite_path: string;
    event_retention_days: number;
    ready: boolean;
  };
  flapping: { debounce_seconds: number };
  diagnostics?: DiagnosticsConfig;
  reports: {
    last_generated_at: string | null;
    last_window: string | null;
  };
  configuration?: {
    mqtt_host: string | null;
    mqtt_topic_prefix: string;
    mqtt_discovery_prefix: string;
    matter_probe_mode: string;
  };
  configured_otbrs?: ConfiguredSource[];
  configured_matter_servers?: ConfiguredSource[];
  features?: Record<string, boolean>;
}

export interface HealthPayload {
  version: string;
  mode: string;
  site: string;
  overall: { state: string; reasons: string[] };
  environment: { state: string; reasons: string[] };
  summary: Record<string, number>;
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

export async function fetchHealth(signal?: AbortSignal): Promise<HealthPayload> {
  const response = await fetch(healthUrl(), {
    headers: { Accept: "application/json" },
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return (await response.json()) as HealthPayload;
}

export { HEALTH_PATH, STATUS_PATH, resolveUrl };
