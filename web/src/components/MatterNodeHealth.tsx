import type { MatterNode, MatterSection } from "../api/types";
import { fmtRelative } from "../utils/format";
import { nodeClassMeta } from "../utils/health";
import { nodeSubtitleParts } from "../utils/nodeIdentity";
import { Badge, Card, EmptyHint } from "./primitives";
import { StatusLegend } from "./StatusLegend";

const GROUP_ORDER: { key: string; title: string }[] = [
  { key: "unavailable", title: "Unavailable" },
  { key: "needs_attention", title: "Needs attention" },
  { key: "recently_unstable", title: "Recently unstable" },
  { key: "diagnostics_limited", title: "Diagnostics limited" },
  { key: "unknown", title: "Unknown" },
  { key: "healthy", title: "Healthy" },
];

function readProbeCountLabel(
  readProbe: MatterNode["read_probe"] | null | undefined,
): string | null {
  if (!readProbe?.diagnostics_available || readProbe.limited) {
    return null;
  }
  const failures = readProbe.failures_24h;
  const successes = readProbe.successes_24h;
  if (typeof failures === "number") {
    const failurePart = `${failures} read failure${failures === 1 ? "" : "s"} (24h)`;
    if (typeof successes === "number") {
      return `${failurePart} · ${successes} OK (24h)`;
    }
    return failurePart;
  }
  if (readProbe.last_ok === false) {
    return "Last read failed";
  }
  return null;
}

function NodeRow({ node, onSelect }: { node: MatterNode; onSelect: (node: MatterNode) => void }) {
  const meta = nodeClassMeta(node.classification);
  const subtitle = nodeSubtitleParts(node).join(" · ");
  const down = node.unsubscribe_count_24h || 0;
  const up = node.resubscribe_count_24h || 0;
  const showChurn = down > 0 || up > 0;
  const readProbe = node.read_probe;
  const overviewLabel = readProbe?.overview_label;
  const showReadProbe =
    readProbe?.diagnostics_available &&
    (readProbe.last_ok === false ||
      readProbe.limited ||
      (readProbe.failures_24h ?? 0) > 0);
  const classificationReason = node.classification_reason || node.health_reason;
  const readProbeHint =
    overviewLabel ||
    (readProbe?.limited
      ? "Read checks unavailable"
      : readProbe?.last_ok === false
        ? "Read probe issue"
        : null);
  const showClassificationReason =
    Boolean(classificationReason) &&
    (node.classification === "recently_unstable" ||
      node.classification === "needs_attention" ||
      node.classification === "diagnostics_limited");
  const reasonHint = showClassificationReason
    ? classificationReason
    : showReadProbe
      ? readProbeHint
      : null;
  const readProbeCount = readProbeCountLabel(readProbe);
  const readProbeFailures = readProbe?.failures_24h ?? 0;
  const showReadProbeBadge =
    readProbe?.diagnostics_available &&
    !readProbe.limited &&
    ((typeof readProbe.failures_24h === "number" && readProbe.failures_24h > 0) ||
      readProbe.last_ok === false);

  return (
    <button
      type="button"
      className={`tl-node-row tl-node-${meta.tone}`}
      onClick={() => onSelect(node)}
      aria-label={`Inspect ${node.name}`}
    >
      <span className="tl-node-main">
        <span className="tl-node-name">{node.name}</span>
        <span className="tl-node-sub tl-muted">
          {node.node_id != null ? `#${node.node_id}` : "node"}
          {subtitle ? ` · ${subtitle}` : ""}
        </span>
        <span className="tl-node-meta tl-muted">
          {showChurn && (
            <span className="tl-node-churn">
              {down} down / {up} up (24h)
            </span>
          )}
          {reasonHint && <span className="tl-node-read-probe tl-muted">{reasonHint}</span>}
          {readProbeCount && (
            <span className="tl-node-read-probe-count tl-muted">{readProbeCount}</span>
          )}
          {node.last_event_at && (
            <span className="tl-node-last">Last event {fmtRelative(node.last_event_at)}</span>
          )}
        </span>
      </span>
      <span className="tl-node-end">
        <Badge tone={meta.tone}>{meta.label}</Badge>
        {showReadProbeBadge && (
          <Badge tone="warn">
            {typeof readProbe?.failures_24h === "number" && readProbeFailures > 0
              ? `${readProbeFailures} read failure${readProbeFailures === 1 ? "" : "s"}`
              : "Read failed"}
          </Badge>
        )}
        {readProbe?.diagnostics_available && !showReadProbeBadge && node.classification === "healthy" && (
          <Badge tone="info">{overviewLabel || "Read checks OK"}</Badge>
        )}
        <span className="tl-node-chevron" aria-hidden="true">
          ›
        </span>
      </span>
    </button>
  );
}

export function MatterNodeHealth({
  matter,
  onSelect,
}: {
  matter: MatterSection;
  onSelect: (node: MatterNode) => void;
}) {
  const nodes = matter.nodes ?? [];

  const counts = (
    <div className="tl-node-counts">
      <span className="tl-count tl-count-critical">{matter.unavailable_count || 0} unavailable</span>
      <span className="tl-count tl-count-warn">{matter.unstable_count || 0} unstable</span>
      <span className="tl-count tl-count-ok">{matter.healthy_count || 0} healthy</span>
      <span className="tl-count tl-count-unknown">{matter.unknown_count || 0} unknown</span>
    </div>
  );

  if (!nodes.length) {
    return (
      <Card title="Matter node health" actions={counts}>
        <EmptyHint>No Matter nodes reported yet. ThreadLens will list nodes as it observes them.</EmptyHint>
      </Card>
    );
  }

  const grouped = new Map<string, MatterNode[]>();
  for (const node of nodes) {
    const key = node.classification || "unknown";
    const list = grouped.get(key) ?? [];
    list.push(node);
    grouped.set(key, list);
  }

  return (
    <Card title="Matter node health" actions={counts}>
      <StatusLegend />
      <div className="tl-node-groups">
        {GROUP_ORDER.filter(({ key }) => (grouped.get(key) ?? []).length > 0).map(({ key, title }) => {
          const group = grouped.get(key) ?? [];
          return (
            <div className="tl-node-group" key={key}>
              <div className="tl-node-group-title">
                {title} <span className="tl-muted">({group.length})</span>
              </div>
              <div className="tl-node-list">
                {group.map((node) => (
                  <NodeRow
                    key={node.subject_id ?? `${node.server_id}:${node.node_id}`}
                    node={node}
                    onSelect={onSelect}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>
      <p className="tl-muted tl-note">
        Select a node to review recent events and a conservative assessment. ThreadLens does not
        infer Thread parentage or routing.
      </p>
    </Card>
  );
}
