import { Link, useParams } from "react-router-dom";
import type { DashboardPayload, MatterNode } from "@/api/types";
import { useDashboardContext } from "@/context/DashboardContext";
import { ClassificationBadge, Card, ErrorState, KeyValue, LoadingState } from "@/components/ui";
import { formatOtbrIds, nodeDrilldownSubtitle } from "@/lib/nodeIdentity";
import { boolText, fmtDuration, fmtTime, orDash } from "@/utils/format";

const INFRA_DEGRADED_EVENTS = new Set([
  "matter_server.disconnected",
  "otbr.unreachable",
  "thread_network.lost",
]);

interface Assessment {
  kind: string;
  text: string;
}

function assess(node: MatterNode, data: DashboardPayload): Assessment {
  const events = data.events?.items ?? [];
  const nodes = data.matter?.nodes ?? [];
  const thisUnstable = (node.recent_unavailable_count || 0) || (node.recent_recovered_count || 0);
  const readProbeIssue =
    Boolean(node.read_probe?.diagnostics_available) &&
    !node.read_probe?.limited &&
    node.read_probe?.last_ok === false;
  const readProbeLimited =
    Boolean(node.read_probe?.limited) || node.classification === "diagnostics_limited";
  const nodeEvents = events.filter((e) => e.subject_id === node.subject_id);
  const otherUnstable = nodes.filter(
    (n) =>
      n.subject_id !== node.subject_id &&
      ((n.recent_unavailable_count || 0) || (n.recent_recovered_count || 0))
  );
  const infraEvents = events.filter(
    (e) => typeof e.event_type === "string" && INFRA_DEGRADED_EVENTS.has(e.event_type)
  );

  if (readProbeLimited) {
    return {
      kind: "individual",
      text:
        node.classification_reason ||
        node.read_probe?.summary ||
        "ThreadLens could not find a read-only Matter attribute this device accepts.",
    };
  }
  if (readProbeIssue && !thisUnstable) {
    return {
      kind: "individual",
      text:
        node.classification_reason ||
        "Matter Server reports this node as available, but the most recent safe read probe did not succeed.",
    };
  }
  if (!nodeEvents.length && !thisUnstable) {
    return {
      kind: "insufficient",
      text: "There is not enough recent event history to classify this as device-local or network-wide.",
    };
  }
  if (otherUnstable.length) {
    return {
      kind: "group",
      text: "Multiple Matter nodes changed state around the same time. This may indicate a wider Matter/Thread network issue.",
    };
  }
  if (infraEvents.length) {
    return {
      kind: "infrastructure",
      text: "Infrastructure events were observed near this node change. Review OTBR, Matter server, mDNS, and TREL.",
    };
  }
  if (thisUnstable) {
    return {
      kind: "individual",
      text: "This looks isolated to this node. ThreadLens does not see a wider infrastructure issue at the same time.",
    };
  }
  return {
    kind: "insufficient",
    text: "There is not enough recent event history to classify this as device-local or network-wide.",
  };
}

export function DeviceDetailPage() {
  const { serverId, nodeId } = useParams();
  const { data, hasLoaded, error, refresh } = useDashboardContext();

  if (!data && !hasLoaded) return <LoadingState />;
  if (!data) return <ErrorState message={error || "Cannot load device"} onRetry={refresh} />;

  const node = data.matter.nodes?.find(
    (n) =>
      String(n.server_id) === decodeURIComponent(serverId ?? "") &&
      String(n.node_id) === decodeURIComponent(nodeId ?? "")
  );

  if (!node) {
    return (
      <div className="max-w-4xl space-y-4">
        <Link to="/devices" className="text-sm text-zl-accent hover:underline">
          ← Back to devices
        </Link>
        <Card title="Device not found">
          <p className="text-zl-muted">No Matter node matches this route.</p>
        </Card>
      </div>
    );
  }

  const subtitle = nodeDrilldownSubtitle(node);
  const assessment = assess(node, data);
  const readProbe = node.read_probe;
  const events =
    node.events?.length
      ? node.events
      : (data.events?.items ?? []).filter((e) => e.subject_id === node.subject_id);

  return (
    <div className="max-w-4xl space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <Link to="/devices" className="text-sm text-zl-accent hover:underline">
          ← Back to devices
        </Link>
        <ClassificationBadge classification={node.classification} />
      </div>

      <header>
        <h1 className="text-2xl font-semibold">{node.name}</h1>
        {subtitle && <p className="mt-1 text-sm text-zl-muted">{subtitle}</p>}
      </header>

      <Card title="What this suggests">
        <p className="text-zl-text">{assessment.text}</p>
        <p className="mt-2 text-sm text-zl-muted">
          ThreadLens does not infer Thread parentage, routing, or root cause.
        </p>
      </Card>

      <Card title="Identity and health">
        <KeyValue
          rows={[
            { label: "Availability", value: boolText(node.available, "Available", "Unavailable") },
            { label: "Health", value: orDash(node.health) },
            { label: "Reason", value: orDash(node.classification_reason || node.health_reason) },
            ...(node.ha_device_name ? [{ label: "HA name", value: orDash(node.ha_device_name) }] : []),
            { label: "Matter name", value: orDash(node.matter_name) },
            { label: "Matter server", value: orDash(node.server_id as string | number | null) },
            { label: "Thread extended address", value: orDash(node.thread_extended_address) },
            { label: "Thread IPv6", value: orDash(node.thread_ipv6_address) },
            { label: "OTBR", value: orDash(formatOtbrIds(node.otbr_ids)) },
            { label: "Vendor", value: orDash(node.vendor) },
            { label: "Product", value: orDash(node.product) },
            { label: "Firmware", value: orDash(node.firmware) },
          ]}
        />
      </Card>

      {readProbe?.diagnostics_available && (
        <Card title="Read diagnostics" subtitle="Safe read-only Matter attribute checks">
          <KeyValue
            rows={[
              { label: "Probe type", value: orDash(readProbe.probe_label) },
              {
                label: "Last result",
                value: readProbe.limited ? "Limited" : boolText(readProbe.last_ok, "OK", "Failed"),
              },
              { label: "Last probe time", value: fmtTime(readProbe.last_at) },
              { label: "Probe path", value: orDash(readProbe.attribute_path) },
              { label: "Working path", value: orDash(readProbe.successful_path) },
              ...(readProbe.unsupported_paths?.length
                ? [
                    {
                      label: "Unsupported paths",
                      value: readProbe.unsupported_paths.join(", "),
                    },
                  ]
                : []),
              {
                label: "Duration",
                value: readProbe.duration_ms != null ? `${readProbe.duration_ms} ms` : "—",
              },
              { label: "Failures (24h)", value: readProbe.failures_24h ?? "—" },
              { label: "Successes (24h)", value: readProbe.successes_24h ?? "—" },
            ]}
          />
          {readProbe.summary && <p className="mt-3 text-sm text-zl-muted">{readProbe.summary}</p>}
          {readProbe.note && <p className="mt-2 text-sm text-zl-muted">{readProbe.note}</p>}
        </Card>
      )}

      {node.ping_probe?.diagnostics_available && (
        <Card title="Ping diagnostics">
          <KeyValue
            rows={[
              {
                label: "Last ping",
                value: boolText(node.ping_probe.last_ok, "Succeeded", "Failed"),
              },
              { label: "Last ping time", value: fmtTime(node.ping_probe.last_at) },
              { label: "Failures (24h)", value: node.ping_probe.failures_24h ?? "—" },
              { label: "Successes (24h)", value: node.ping_probe.successes_24h ?? "—" },
            ]}
          />
        </Card>
      )}

      <Card title="Availability (24h)">
        <KeyValue
          rows={[
            { label: "Unavailable transitions", value: node.unsubscribe_count_24h || 0 },
            { label: "Recovered transitions", value: node.resubscribe_count_24h || 0 },
            { label: "Offline episodes", value: node.offline_episodes_24h || 0 },
            { label: "Median offline", value: fmtDuration(node.median_offline_seconds_24h) },
            { label: "Total offline", value: fmtDuration(node.total_offline_seconds_24h) },
            { label: "Last seen", value: fmtTime(node.last_seen) },
            { label: "Last unavailable", value: fmtTime(node.last_unavailable) },
          ]}
        />
      </Card>

      <Card title="Recent events">
        {events.length ? (
          <ul className="space-y-2">
            {events.map((e, idx) => (
              <li
                key={`${e.timestamp}-${idx}`}
                className="flex flex-wrap gap-2 border-b border-zl-border/50 pb-2 text-sm last:border-0"
              >
                <span className="font-mono text-xs text-zl-muted">{fmtTime(e.timestamp)}</span>
                <span className="text-zl-text">{e.event_type}</span>
                {e.severity && <span className="text-zl-muted">{e.severity}</span>}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-zl-muted">No recent events for this node.</p>
        )}
      </Card>
    </div>
  );
}
