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
