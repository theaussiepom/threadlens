import { Link } from "react-router-dom";
import type { Incident, MatterNode, SlimEvent } from "@/api/types";
import { matterNodePath, nodeListSubtitleParts } from "@/lib/nodeIdentity";
import { classificationToSeverity } from "@/lib/severity";
import {
  Badge,
  Card,
  ClassificationBadge,
  EvidenceList,
  LastSeenText,
  LimitationsList,
  MetricPill,
  SeverityBadge,
} from "@/components/ui";
import { incidentToSeverity } from "@/lib/severity";
import { fmtRelative } from "@/utils/format";

export function CurrentFindingCard({ incident }: { incident: Incident }) {
  const evidence: string[] = [];
  if (incident.summary || incident.detail) {
    evidence.push(incident.summary || incident.detail);
  }
  for (const node of incident.affected_nodes ?? []) {
    if (node.name) {
      evidence.push(`${node.name}${node.reason ? ` — ${node.reason}` : ""}`);
    }
  }

  const limitations = [
    "ThreadLens does not infer Thread parentage or routing.",
    "Read checks are read-only Matter attribute reads — they do not move devices.",
    "Identical devices can differ by Matter endpoint; unsupported paths are skipped.",
  ];

  return (
    <Card
      title="Current finding"
      subtitle="What ThreadLens sees right now — with evidence and limits"
      className="border-zl-accent/30 bg-gradient-to-br from-zl-surface to-zl-surface-2"
    >
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <SeverityBadge severity={incidentToSeverity(incident.state)} />
      </div>
      <p className="mb-6 text-lg leading-relaxed text-zl-text">
        {incident.title || incident.headline || "No active incident pattern detected."}
      </p>
      <div className="grid gap-4 md:grid-cols-2">
        <EvidenceList items={evidence} emptyText="No supporting evidence yet." />
        <LimitationsList items={limitations} />
      </div>
    </Card>
  );
}

export function MatterNodeCard({ node }: { node: MatterNode }) {
  const subtitle = nodeListSubtitleParts(node).join(" · ");
  const down = node.unsubscribe_count_24h || 0;
  const up = node.resubscribe_count_24h || 0;
  const reason = node.classification_reason || node.health_reason;
  const showReason =
    node.classification !== "healthy" && Boolean(reason);

  return (
    <Link
      to={matterNodePath(node)}
      className="block rounded-lg border border-zl-border bg-zl-bg/40 p-4 transition-colors hover:border-zl-accent/40"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate font-medium text-zl-text">{node.name}</div>
          <div className="mt-1 text-xs text-zl-muted">
            {node.node_id != null ? `#${node.node_id}` : "node"}
            {subtitle ? ` · ${subtitle}` : ""}
          </div>
        </div>
        <ClassificationBadge classification={node.classification} />
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-zl-muted">
        <Badge severity={node.available ? "healthy" : "critical"}>
          {node.available ? "Available" : "Unavailable"}
        </Badge>
        {(down > 0 || up > 0) && (
          <MetricPill
            label="Churn"
            value={`${down}↓ ${up}↑`}
            severity={down > 0 ? "watch" : undefined}
          />
        )}
        {node.read_probe?.failures_24h ? (
          <MetricPill
            label="Read fails"
            value={node.read_probe.failures_24h}
            severity={classificationToSeverity(node.classification)}
          />
        ) : null}
        <LastSeenText iso={node.last_event_at} prefix="event" />
      </div>
      {showReason && reason && (
        <p className="mt-2 border-l-2 border-zl-watch/40 pl-3 text-sm text-zl-muted">{reason}</p>
      )}
    </Link>
  );
}

export function TimelineEventRow({ event }: { event: SlimEvent }) {
  const severity =
    event.severity === "critical"
      ? "critical"
      : event.severity === "warning"
        ? "watch"
        : "healthy";

  return (
    <div className="flex flex-col gap-2 overflow-hidden rounded-lg border-l-2 border-zl-border py-2 pl-4 pr-2 sm:flex-row sm:gap-4">
      <div className="w-full shrink-0 sm:w-32">
        <div className="font-mono text-xs text-zl-muted">{fmtRelative(event.timestamp)}</div>
        <div className="mt-1 text-xs text-zl-muted">{event.event_type?.replace(/_/g, " ") ?? "event"}</div>
      </div>
      <div className="min-w-0 flex-1">
        <div className="break-words font-medium text-zl-text">{event.message || event.event_type}</div>
        {event.subject_id && (
          <div className="mt-1 text-xs text-zl-muted">{event.subject_id}</div>
        )}
        <Badge severity={severity as "healthy" | "watch" | "critical"}>{event.severity || "info"}</Badge>
      </div>
    </div>
  );
}
