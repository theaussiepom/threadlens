/**
 * TypeScript shapes for the `GET api/v1/dashboard` payload.
 *
 * These mirror `threadlens/server/dashboard.py`. Fields are intentionally
 * permissive (optional / nullable) so the UI degrades gracefully when Core
 * omits data rather than crashing on missing keys.
 */

export type HealthState = "healthy" | "warning" | "degraded" | "critical" | "unknown" | string;

export type NodeClassification =
  | "unavailable"
  | "needs_attention"
  | "recently_unstable"
  | "diagnostics_limited"
  | "healthy"
  | "unknown"
  | string;

export interface ReadProbeDiagnostics {
  diagnostics_available: boolean;
  last_at: string | null;
  last_ok: boolean | null;
  limited?: boolean;
  probe_kind?: string | null;
  probe_label?: string | null;
  overview_label?: string | null;
  attribute_path: string | null;
  duration_ms: number | null;
  error_code: string | number | null;
  failures_24h: number | null;
  successes_24h: number | null;
  summary: string | null;
  note?: string | null;
}

export interface PingProbeDiagnostics {
  diagnostics_available: boolean;
  last_at: string | null;
  last_ok: boolean | null;
  failures_24h: number | null;
  successes_24h: number | null;
}

export type IncidentState = "ok" | "watch" | "incident" | "unknown" | string;

export interface Reason {
  code: string;
  label: string;
}

export interface ThreadLensMeta {
  version: string | null;
  api_connected: boolean;
  last_update: string | null;
  overall_health: HealthState;
  environment_health: HealthState;
  overall_health_raw: HealthState;
  environment_health_raw: HealthState;
  reasons: Reason[];
  reasons_all: Reason[];
  informational_reasons: Reason[];
}

export interface IncidentInfrastructure {
  otbr: HealthState;
  matter: HealthState;
  mdns: HealthState;
  trel: HealthState;
}

export interface IncidentAffectedNode {
  node_id: number | null;
  name: string | null;
  health: string | null;
  reason: string | null;
}

export interface Incident {
  state: IncidentState;
  title: string;
  summary: string;
  headline: string;
  detail: string;
  affected_nodes: IncidentAffectedNode[];
  affected_node_names: string[];
  infrastructure: IncidentInfrastructure;
  infrastructure_unhealthy: boolean;
}

export interface SlimEvent {
  timestamp: string | null;
  event_type: string | null;
  severity: string | null;
  source: string | null;
  subject_id: string | null;
  subject_type: string | null;
  message: string | null;
  data?: unknown;
}

export interface Otbr {
  id: string | null;
  name: string | null;
  reachable: boolean;
  health: HealthState;
  display_health: HealthState;
  reasons: Reason[];
  reasons_all: Reason[];
  effective_state: string | null;
  state_source_label: string | null;
  thread_state: string | null;
  role: string | null;
  network_name: string | null;
  extended_pan_id: string | null;
  rloc16: string | null;
  channel: number | string | null;
  thread_state_source: string | null;
  rest_endpoint_mismatch: boolean;
  mismatch_reconciled: boolean;
  mismatch_detail: string | null;
  json_api_thread_state: string | null;
  legacy_node_thread_state: string | null;
  capabilities: Record<string, unknown>;
}

export interface ThreadNetwork {
  extended_pan_id: string | null;
  name: string | null;
  channel: number | string | null;
  pan_id: string | null;
  border_router_count: number | null;
  classification: string | null;
  health: HealthState;
}

export interface MatterNode {
  node_id: number | null;
  server_id: string | number | null;
  subject_id: string | null;
  name: string;
  available: boolean | null;
  health: string;
  health_reason: string | null;
  classification: NodeClassification;
  vendor: string | null;
  product: string | null;
  serial: string | null;
  firmware: string | null;
  last_seen: string | null;
  last_unavailable: string | null;
  last_updated: string | null;
  availability_flaps_24h: number | null;
  recent_unavailable_count: number;
  recent_recovered_count: number;
  last_event_at: string | null;
  sort_key: number;
  events: SlimEvent[];
  unavailable_transitions_24h: number;
  recovered_transitions_24h: number;
  unsubscribe_count_24h: number;
  resubscribe_count_24h: number;
  availability_cycles_24h: number;
  availability_metric_source: string;
  subscription_diagnostics_available: boolean;
  subscription_flaps_24h: number | null;
  availability_flaps_24h_metric?: number | null;
  median_offline_seconds_24h: number | null;
  offline_episodes_24h: number;
  total_offline_seconds_24h: number;
  read_probe?: ReadProbeDiagnostics | null;
  ping_probe?: PingProbeDiagnostics | null;
}

export interface MatterSection {
  health: HealthState;
  servers: number;
  servers_connected: number;
  node_count: number;
  unavailable_count: number;
  unavailable_nodes: { node_id: number | null; server_id: unknown; friendly_name: string }[];
  unstable_count: number;
  needs_attention_count?: number;
  diagnostics_limited_count?: number;
  healthy_count: number;
  unknown_count: number;
  recent_unavailable_count: number;
  recent_recovered_count: number;
  affected_nodes_24h: unknown[];
  nodes: MatterNode[];
  groups: Record<string, MatterNode[]>;
}

export interface MdnsSection {
  health: HealthState;
  health_raw: HealthState;
  service_count: number;
  observation_degraded: boolean | null;
  top_service_types: { service_type: string; count: number }[];
}

export interface TrelSection {
  health: HealthState;
  health_raw: HealthState;
  informational: boolean;
  service_count: number;
  foreign_service_count: number;
  reasons: Reason[];
  reasons_all: Reason[];
  info: {
    foreign_trel_observed: boolean;
    message: string | null;
  };
}

export interface MqttSection {
  enabled: boolean | null;
  connected: boolean | null;
  homeassistant_discovery_enabled: boolean | null;
  last_publish_at: string | null;
  last_error: string | null;
}

export interface EventsSection {
  window: string;
  items: SlimEvent[];
}

export interface ReportSection {
  report_url: string | null;
  report_url_json: string | null;
  last_generated_at: string | null;
}

export interface DashboardPayload {
  threadlens: ThreadLensMeta;
  incident: Incident;
  otbrs: Otbr[];
  networks: ThreadNetwork[];
  matter: MatterSection;
  mdns: MdnsSection;
  trel: TrelSection;
  events: EventsSection;
  mqtt: MqttSection | null;
  report: ReportSection;
  error: string | null;
}
