import { useEffect } from "react";
import type { DashboardPayload, MatterNode } from "../api/types";
import { boolText, fmtDuration, fmtTime, orDash } from "../utils/format";
import { nodeClassMeta } from "../utils/health";
import { Badge, KeyValue } from "./primitives";

const INFRA_DEGRADED_EVENTS = new Set([
  "matter_server.disconnected",
  "otbr.unreachable",
  "thread_network.lost",
]);

interface Assessment {
  kind: "individual" | "group" | "infrastructure" | "insufficient";
  text: string;
}

/**
 * Conservative, non-causal assessment mirroring Core `build_node_detail`.
 * Never claims root cause; uses hedged language only.
 */
function assess(node: MatterNode, data: DashboardPayload): Assessment {
  const events = data.events?.items ?? [];
  const nodes = data.matter?.nodes ?? [];
  const thisUnstable = (node.recent_unavailable_count || 0) || (node.recent_recovered_count || 0);
  const nodeEvents = events.filter((e) => e.subject_id === node.subject_id);
  const otherUnstable = nodes.filter(
    (n) =>
      n.subject_id !== node.subject_id &&
      ((n.recent_unavailable_count || 0) || (n.recent_recovered_count || 0))
  );
  const infraEvents = events.filter(
    (e) => typeof e.event_type === "string" && INFRA_DEGRADED_EVENTS.has(e.event_type)
  );

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
      text: "Infrastructure events were observed near this node change. Review the OTBR, Matter server, mDNS, and TREL sections.",
    };
  }
  if (thisUnstable) {
    return {
      kind: "individual",
      text: "This looks isolated to this node. ThreadLens does not see a wider Matter/Thread infrastructure issue at the same time.",
    };
  }
  return {
    kind: "insufficient",
    text: "There is not enough recent event history to classify this as device-local or network-wide.",
  };
}

export function NodeDrilldown({
  node,
  data,
  onClose,
}: {
  node: MatterNode;
  data: DashboardPayload;
  onClose: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const meta = nodeClassMeta(node.classification);
  const subtitle = [node.vendor, node.product].filter(Boolean).join(" · ");
  const assessment = assess(node, data);
  const events =
    node.events && node.events.length
      ? node.events
      : (data.events?.items ?? []).filter((e) => e.subject_id === node.subject_id);

  return (
    <div className="tl-sheet-overlay" role="dialog" aria-modal="true" aria-label={`${node.name} details`}>
      <button type="button" className="tl-sheet-scrim" aria-label="Close" onClick={onClose} />
      <div className="tl-sheet">
        <div className="tl-sheet-head">
          <button type="button" className="tl-btn tl-btn-secondary" onClick={onClose}>
            ← Back
          </button>
          <Badge tone={meta.tone}>{meta.label}</Badge>
        </div>

        <div className="tl-sheet-body">
          <div className="tl-sheet-title">
            <h2>{node.name}</h2>
            <span className="tl-muted">{node.node_id != null ? `#${node.node_id}` : ""}</span>
          </div>
          {subtitle && <p className="tl-muted tl-sheet-sub">{subtitle}</p>}

          <div className={`tl-assessment tl-assessment-${assessment.kind}`}>
            <span className="tl-assessment-label">What this suggests</span>
            <p>{assessment.text}</p>
            <p className="tl-muted tl-note">
              ThreadLens does not infer Thread parentage, routing, or root cause. This is a
              conservative read of observed events.
            </p>
          </div>

          <KeyValue
            rows={[
              { label: "Availability", value: boolText(node.available, "Available", "Unavailable") },
              { label: "Health", value: orDash(node.health) },
              { label: "Server", value: orDash(node.server_id as string | number | null) },
              { label: "Vendor", value: orDash(node.vendor) },
              { label: "Product", value: orDash(node.product) },
              { label: "Firmware", value: orDash(node.firmware) },
              { label: "Last seen", value: fmtTime(node.last_seen) },
              { label: "Last unavailable", value: fmtTime(node.last_unavailable) },
              { label: "Unavailable (24h)", value: node.unsubscribe_count_24h || 0 },
              { label: "Recovered (24h)", value: node.resubscribe_count_24h || 0 },
              { label: "Offline episodes (24h)", value: node.offline_episodes_24h || 0 },
              { label: "Median offline (24h)", value: fmtDuration(node.median_offline_seconds_24h) },
              { label: "Total offline (24h)", value: fmtDuration(node.total_offline_seconds_24h) },
              {
                label: "Availability flaps (24h)",
                value: node.availability_flaps_24h ?? "—",
              },
            ]}
          />

          {node.read_probe?.diagnostics_available && (
            <div className="tl-sheet-section">
              <h3>Read diagnostics</h3>
              <p className="tl-muted tl-note">
                Safe read probes check whether the node responds to a read-only Matter attribute
                read. They do not prove open/close or other commands are working.
              </p>
              {node.read_probe.summary && (
                <p className="tl-assessment">{node.read_probe.summary}</p>
              )}
              <KeyValue
                rows={[
                  {
                    label: "Last read probe",
                    value: node.read_probe.limited
                      ? "Limited"
                      : boolText(node.read_probe.last_ok, "Succeeded", "Failed"),
                  },
                  { label: "Last probe time", value: fmtTime(node.read_probe.last_at) },
                  { label: "Attribute path", value: orDash(node.read_probe.attribute_path) },
                  {
                    label: "Duration",
                    value:
                      node.read_probe.duration_ms != null
                        ? `${node.read_probe.duration_ms} ms`
                        : "—",
                  },
                  {
                    label: "Failures (24h)",
                    value: node.read_probe.failures_24h ?? "—",
                  },
                  {
                    label: "Successes (24h)",
                    value: node.read_probe.successes_24h ?? "—",
                  },
                ]}
              />
            </div>
          )}

          {node.ping_probe?.diagnostics_available && (
            <div className="tl-sheet-section">
              <h3>Ping diagnostics</h3>
              <KeyValue
                rows={[
                  {
                    label: "Last ping",
                    value: boolText(node.ping_probe.last_ok, "Succeeded", "Failed"),
                  },
                  { label: "Last ping time", value: fmtTime(node.ping_probe.last_at) },
                  {
                    label: "Failures (24h)",
                    value: node.ping_probe.failures_24h ?? "—",
                  },
                  {
                    label: "Successes (24h)",
                    value: node.ping_probe.successes_24h ?? "—",
                  },
                ]}
              />
            </div>
          )}

          <div className="tl-sheet-events">
            <h3>Recent events</h3>
            {events.length ? (
              <ul className="tl-event-list">
                {events.map((e, idx) => (
                  <li className="tl-event" key={`${e.timestamp}-${idx}`}>
                    <span className="tl-event-time tl-muted">{fmtTime(e.timestamp)}</span>
                    <span className="tl-event-type">{e.event_type}</span>
                    {e.severity && <span className="tl-event-sev tl-muted">{e.severity}</span>}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="tl-muted">No recent events for this node in the current window.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
