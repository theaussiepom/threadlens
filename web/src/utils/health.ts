import type { HealthState, IncidentState, NodeClassification } from "../api/types";

export type Tone = "ok" | "warn" | "degraded" | "critical" | "unknown" | "info";

export function healthTone(state: HealthState | null | undefined): Tone {
  switch (state) {
    case "healthy":
      return "ok";
    case "warning":
      return "warn";
    case "degraded":
      return "degraded";
    case "critical":
      return "critical";
    default:
      return "unknown";
  }
}

export interface ClassMeta {
  label: string;
  tone: Tone;
  /** Lower sorts first. */
  order: number;
}

export const NODE_CLASS_META: Record<string, ClassMeta> = {
  unavailable: { label: "Needs attention", tone: "critical", order: 0 },
  needs_attention: { label: "Needs attention", tone: "degraded", order: 1 },
  recently_unstable: { label: "Recently unstable", tone: "warn", order: 2 },
  diagnostics_limited: { label: "Diagnostics limited", tone: "info", order: 3 },
  unknown: { label: "Unknown", tone: "unknown", order: 4 },
  healthy: { label: "Healthy", tone: "ok", order: 5 },
};

export function nodeClassMeta(classification: NodeClassification): ClassMeta {
  return NODE_CLASS_META[classification] ?? NODE_CLASS_META.unknown;
}

export interface StatusLegendEntry {
  key: string;
  label: string;
  description: string;
}

/** Human-readable definitions for Matter node list badges and groups. */
export const NODE_STATUS_LEGEND: StatusLegendEntry[] = [
  {
    key: "unavailable",
    label: "Needs attention (unavailable)",
    description:
      "Matter Server reports this node as unavailable right now. Commands may not reach the device.",
  },
  {
    key: "needs_attention",
    label: "Needs attention",
    description:
      "Three or more read check failures in the last 24 hours. The node may still show as available in Matter Server.",
  },
  {
    key: "recently_unstable",
    label: "Recently unstable",
    description:
      "A recent availability change, or the last read check failed, or one read check failure in the last 24 hours.",
  },
  {
    key: "diagnostics_limited",
    label: "Diagnostics limited",
    description:
      "ThreadLens could not find a read-only Matter attribute this device accepts. This does not mean the device is broken — identical devices can use different Matter endpoints.",
  },
  {
    key: "healthy",
    label: "Healthy",
    description:
      "Available with no recent availability churn or read probe failures in the last 24 hours.",
  },
  {
    key: "unknown",
    label: "Unknown",
    description: "Not enough observation data yet to classify this node.",
  },
];

export const RECENT_WINDOW_DESCRIPTION =
  "“Recently” and all 24h counters use the last 24 hours of ThreadLens events (up to 100 events per node). Read checks are read-only Matter attribute reads — they do not move blinds or change device state.";

export interface IncidentMeta {
  label: string;
  tone: Tone;
}

export const INCIDENT_META: Record<string, IncidentMeta> = {
  ok: { label: "OK", tone: "ok" },
  watch: { label: "Watch", tone: "warn" },
  incident: { label: "Incident", tone: "critical" },
  unknown: { label: "Unknown", tone: "unknown" },
};

export function incidentMeta(state: IncidentState): IncidentMeta {
  return INCIDENT_META[state] ?? INCIDENT_META.unknown;
}
