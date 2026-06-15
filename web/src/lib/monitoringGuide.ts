/** Static definitions for the in-app monitoring transparency guide. */

import type { Severity } from "@/lib/severity";

export type GuideSeverity = Severity;

export interface GuideRow {
  label: string;
  condition: string;
  result: string;
  severity: GuideSeverity;
  uiLabel: string;
}

export interface IncidentRuleRow {
  type: string;
  title: string;
  trigger: string;
  severity: GuideSeverity;
  scope: string;
  notes?: string;
}

export type DiagnosticsConfig = Record<string, number | string | boolean | null | undefined>;

export const SEVERITY_ROWS: Array<{ severity: GuideSeverity; label: string; meaning: string }> = [
  {
    severity: "healthy",
    label: "OK",
    meaning: "No current concern, or signals are within normal bounds.",
  },
  {
    severity: "watch",
    label: "Watch",
    meaning: "Something worth attention — not necessarily a fault. May escalate if it persists.",
  },
  {
    severity: "incident",
    label: "Incident",
    meaning: "A clear device or infrastructure problem. Overview incident state becomes Incident.",
  },
  {
    severity: "critical",
    label: "Critical",
    meaning: "OTBR unreachable, Matter server disconnected, or a node unavailable for an extended period.",
  },
];

export const OBSERVATION_SOURCES = [
  {
    source: "OTBR REST",
    use: "Role, network name, device inventory, reachability (read-only polling)",
  },
  {
    source: "Matter Server websocket",
    use: "Inventory, availability, and passive events; read-only commands only",
  },
  {
    source: "mDNS / DNS-SD",
    use: "Configured service types (_trel._udp, _meshcop._udp, _matter._tcp, _matterc._udp)",
  },
  {
    source: "TREL services",
    use: "Foreign or observed-other Extended PAN IDs (informational, not faults)",
  },
  {
    source: "Optional ThreadLens agents",
    use: "Additional read-only observations from remote hosts",
  },
];

export function nodeClassificationRows(d: DiagnosticsConfig): GuideRow[] {
  const readDegraded = d.matter_node_read_probe_failures_degraded_24h ?? 3;
  const readWarning = d.matter_node_read_probe_failures_warning_24h ?? 1;
  const availDegraded = d.matter_node_availability_degraded_24h ?? 6;
  const availWarning = d.matter_node_availability_warning_24h ?? 3;

  return [
    {
      label: "unavailable",
      condition: "Matter Server reports `available=false`",
      result: "Highest-priority dashboard group; drives incident state",
      severity: "critical",
      uiLabel: "Needs attention",
    },
    {
      label: "diagnostics_limited",
      condition: "Read probe active but no working read-only attribute path found",
      result: "Device may still be healthy — identical devices can use different Matter endpoints",
      severity: "watch",
      uiLabel: "Diagnostics limited",
    },
    {
      label: "needs_attention",
      condition: `≥ ${readDegraded} read check failures in the last 24 hours`,
      result: "Repeated read probe failures while node still shows available",
      severity: "incident",
      uiLabel: "Needs attention",
    },
    {
      label: "recently_unstable",
      condition: `Last read check failed, or ${readWarning}+ failure in 24h, or availability transition/flap (≥ ${availWarning} watch / ≥ ${availDegraded} degraded changes in 24h)`,
      result: "Recent churn or a single failed read check",
      severity: "watch",
      uiLabel: "Recently unstable",
    },
    {
      label: "healthy",
      condition: "Available with no recent availability churn or read probe failures",
      result: "No current dashboard concerns for this node",
      severity: "healthy",
      uiLabel: "Healthy",
    },
    {
      label: "unknown",
      condition: "Not enough observation data yet",
      result: "Common shortly after Core startup",
      severity: "watch",
      uiLabel: "Unknown",
    },
  ];
}

export function classificationPriority(): string[] {
  return [
    "unavailable",
    "diagnostics_limited",
    "needs_attention",
    "recently_unstable (read probe or availability)",
    "healthy",
    "unknown",
  ];
}

export function otbrHealthRows(d: DiagnosticsConfig): GuideRow[] {
  const roleDegraded = d.otbr_role_changes_degraded_1h ?? 5;
  const roleWarning = d.otbr_role_changes_warning_1h ?? 2;
  return [
    {
      label: "unreachable",
      condition: "OTBR REST API not reachable",
      result: "Critical infrastructure health; may affect incident assessment",
      severity: "critical",
      uiLabel: "Unreachable",
    },
    {
      label: "thread_disabled",
      condition: "Thread stack state is `disabled`",
      result: "Degraded health — REST may respond but radio is off",
      severity: "incident",
      uiLabel: "Thread disabled",
    },
    {
      label: "endpoint_mismatch",
      condition: "JSON and legacy OTBR endpoints disagree on Thread state",
      result: "Warning — shown explicitly on Infrastructure page",
      severity: "watch",
      uiLabel: "Endpoint mismatch",
    },
    {
      label: "role_flapping",
      condition: `≥ ${roleWarning} role changes in 1h (watch) or ≥ ${roleDegraded} (degraded)`,
      result: "Border router role instability",
      severity: "watch",
      uiLabel: "Role changes",
    },
    {
      label: "healthy",
      condition: "Reachable with known Thread state and no concerning signals",
      result: "No current OTBR health concerns",
      severity: "healthy",
      uiLabel: "Healthy",
    },
  ];
}

export function networkHealthRows(): GuideRow[] {
  return [
    {
      label: "primary",
      condition: "Classification is primary and at least one source OTBR is reachable",
      result: "Healthy primary Thread network",
      severity: "healthy",
      uiLabel: "Primary",
    },
    {
      label: "observed_other",
      condition: "Foreign or other-fabric TREL/mDNS observation",
      result: "Informational warning — common with HomePods, Apple TVs, Nest hubs",
      severity: "watch",
      uiLabel: "Observed other",
    },
    {
      label: "unknown",
      condition: "Primary network not identified yet",
      result: "Watch until OTBR and mDNS observations align",
      severity: "watch",
      uiLabel: "Unknown",
    },
    {
      label: "unreachable_sources",
      condition: "Network visible but source OTBRs unreachable",
      result: "Warning — may indicate collector or connectivity issue",
      severity: "watch",
      uiLabel: "Sources unreachable",
    },
  ];
}

export function incidentRules(d: DiagnosticsConfig): IncidentRuleRow[] {
  const criticalMin = d.matter_node_unavailable_critical_minutes ?? 30;
  return [
    {
      type: "unavailable",
      title: "Matter node unavailable",
      trigger: "One or more nodes report `available=false` in Matter Server",
      severity: "critical",
      scope: "Affected nodes",
      notes: "Overview headline lists unavailable node names.",
    },
    {
      type: "needs_attention",
      title: "Nodes need attention",
      trigger: "Repeated read check failures (see classification thresholds) while still available",
      severity: "incident",
      scope: "Affected nodes",
      notes: "Only when no nodes are currently unavailable.",
    },
    {
      type: "recently_unstable",
      title: "Recently unstable nodes",
      trigger: "Availability transitions or single read check failures in the last 24h",
      severity: "watch",
      scope: "Affected nodes",
    },
    {
      type: "infrastructure",
      title: "Infrastructure issue",
      trigger:
        "OTBR unreachable, Matter server disconnected, mDNS observation degraded, or non-informational mDNS/TREL health degraded",
      severity: "incident",
      scope: "Collectors / LAN observation",
      notes: "Foreign TREL alone is informational and does not open an incident.",
    },
    {
      type: "extended_unavailable",
      title: "Extended unavailability (health engine)",
      trigger: `Node unavailable for ≥ ${criticalMin} minutes`,
      severity: "critical",
      scope: "Single node",
      notes: "Contributes to per-node health reasons on Devices and Diagnostics.",
    },
    {
      type: "insufficient_data",
      title: "Insufficient data",
      trigger: "No nodes, OTBRs, or events observed yet",
      severity: "watch",
      scope: "Whole environment",
    },
  ];
}

export const DASHBOARD_LABELS = [
  {
    surface: "Overview → Incident headline",
    source: "Unavailable nodes first; otherwise infrastructure problems; otherwise needs-attention count",
  },
  {
    surface: "Overview → Incident state badge",
    source: "ok / watch / incident / unknown from incident summary",
  },
  {
    surface: "Overview → Overall health badge",
    source: "Health engine rollup across OTBR, Matter, mDNS, TREL, and nodes",
  },
  {
    surface: "Devices → Group badges",
    source: "Dashboard node classification (first match in priority order above)",
  },
  {
    surface: "Device detail → Classification badge",
    source: "Same classification with explicit classification_reason text",
  },
  {
    surface: "Infrastructure → OTBR / network cards",
    source: "Per-entity health engine results and capability flags",
  },
  {
    surface: "Header → Live / Polling indicator",
    source: "SSE stream connected vs 30s polling fallback",
  },
];

export const LIMITATIONS = [
  "ThreadLens is read-only — it never commissions Thread devices, sends Matter control commands, or mutates OTBR state.",
  "Subscription, CASE, and command diagnostics are unavailable unless structured Matter Server events expose them.",
  "ThreadLens never infers subscription flaps from availability flaps.",
  "mDNS/TREL visibility does not prove device parentage or mesh topology.",
  "Initial mDNS discovery after startup is baseline observation, not service flapping.",
  "Unavailable metrics are reported as null or explicit capability flags — never inferred as zero.",
  "Incidents describe observed patterns — they are not root-cause verdicts.",
];

export function thresholdRows(d: DiagnosticsConfig): Array<[string, string | number | boolean, string]> {
  return [
    ["matter_node_availability_warning_24h", d.matter_node_availability_warning_24h ?? 3, "Availability flaps → watch health"],
    ["matter_node_availability_degraded_24h", d.matter_node_availability_degraded_24h ?? 6, "Availability flaps → degraded health"],
    ["matter_node_unavailable_critical_minutes", d.matter_node_unavailable_critical_minutes ?? 30, "Extended unavailability → critical"],
    ["matter_node_read_probe_failures_warning_24h", d.matter_node_read_probe_failures_warning_24h ?? 1, "Read failures → watch / recently unstable"],
    ["matter_node_read_probe_failures_degraded_24h", d.matter_node_read_probe_failures_degraded_24h ?? 3, "Read failures → needs attention"],
    ["otbr_role_changes_warning_1h", d.otbr_role_changes_warning_1h ?? 2, "OTBR role flapping → watch"],
    ["otbr_role_changes_degraded_1h", d.otbr_role_changes_degraded_1h ?? 5, "OTBR role flapping → degraded"],
    ["mdns_service_flaps_warning_1h", d.mdns_service_flaps_warning_1h ?? 5, "mDNS/TREL add-remove churn → watch"],
    ["mdns_service_flaps_degraded_1h", d.mdns_service_flaps_degraded_1h ?? 15, "mDNS/TREL add-remove churn → degraded"],
    ["debounce_seconds", d.debounce_seconds ?? 30, "Event debounce for flapping counters"],
    ["matter_probe_mode", d.matter_probe_mode ?? "disabled", "Read probe schedule mode"],
    ["matter_probe_interval_seconds", d.matter_probe_interval_seconds ?? "—", "Scheduled read probe interval"],
    ["matter_probe_ping_enabled", d.matter_probe_ping_enabled ?? false, "Optional Matter ping probes"],
    ["otbr_poll_interval_seconds", d.otbr_poll_interval_seconds ?? 60, "OTBR REST poll interval"],
    ["event_retention_days", d.event_retention_days ?? 30, "SQLite event retention"],
  ];
}
