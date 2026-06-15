import type { HealthState, IncidentState, NodeClassification } from "@/api/types";

export type Severity = "healthy" | "watch" | "incident" | "critical";

export function severityBg(severity: Severity): string {
  switch (severity) {
    case "healthy":
      return "bg-zl-healthy/15 text-zl-healthy border-zl-healthy/30";
    case "watch":
      return "bg-zl-watch/15 text-zl-watch border-zl-watch/30";
    case "incident":
      return "bg-zl-incident/15 text-zl-incident border-zl-incident/30";
    case "critical":
      return "bg-zl-critical/15 text-zl-critical border-zl-critical/30";
    default:
      return "bg-zl-surface-2 text-zl-muted border-zl-border";
  }
}

export function severityDot(severity: Severity): string {
  switch (severity) {
    case "healthy":
      return "bg-zl-healthy";
    case "watch":
      return "bg-zl-watch";
    case "incident":
      return "bg-zl-incident";
    case "critical":
      return "bg-zl-critical";
    default:
      return "bg-zl-muted";
  }
}

export function severityLabel(severity: Severity): string {
  switch (severity) {
    case "healthy":
      return "OK";
    case "watch":
      return "Watch";
    case "incident":
      return "Incident";
    case "critical":
      return "Critical";
    default:
      return "Unknown";
  }
}

export function healthToSeverity(state: HealthState | null | undefined): Severity {
  switch (state) {
    case "healthy":
      return "healthy";
    case "warning":
      return "watch";
    case "degraded":
      return "incident";
    case "critical":
      return "critical";
    default:
      return "watch";
  }
}

export function incidentToSeverity(state: IncidentState): Severity {
  switch (state) {
    case "ok":
      return "healthy";
    case "watch":
      return "watch";
    case "incident":
      return "incident";
    default:
      return "watch";
  }
}

export function classificationToSeverity(classification: NodeClassification): Severity {
  switch (classification) {
    case "healthy":
      return "healthy";
    case "recently_unstable":
    case "diagnostics_limited":
    case "unknown":
      return "watch";
    case "needs_attention":
      return "incident";
    case "unavailable":
      return "critical";
    default:
      return "watch";
  }
}

export function classificationLabel(classification: NodeClassification): string {
  switch (classification) {
    case "unavailable":
      return "Needs attention";
    case "needs_attention":
      return "Needs attention";
    case "recently_unstable":
      return "Recently unstable";
    case "diagnostics_limited":
      return "Diagnostics limited";
    case "healthy":
      return "Healthy";
    default:
      return "Unknown";
  }
}
