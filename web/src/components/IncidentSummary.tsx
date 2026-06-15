import type { Incident } from "../api/types";
import { incidentMeta } from "../utils/health";
import { Badge, HealthBadge } from "./primitives";

const INFRA_LABELS: { key: keyof Incident["infrastructure"]; label: string }[] = [
  { key: "otbr", label: "OTBR" },
  { key: "matter", label: "Matter" },
  { key: "mdns", label: "mDNS" },
  { key: "trel", label: "TREL" },
];

export function IncidentSummary({ incident }: { incident: Incident }) {
  const meta = incidentMeta(incident.state);
  const affected = incident.affected_nodes ?? [];
  const headline = incident.title || incident.headline || "";
  const detail = incident.summary || incident.detail || "";

  return (
    <section className={`tl-card tl-incident tl-incident-${incident.state || "unknown"}`}>
      <div className="tl-incident-head">
        <div className="tl-incident-state">
          <span className="tl-incident-eyebrow">Incident state</span>
          <Badge tone={meta.tone}>{meta.label}</Badge>
        </div>
      </div>

      <p className="tl-incident-headline">{headline}</p>
      {detail && <p className="tl-incident-detail">{detail}</p>}

      {affected.length > 0 && (
        <div className="tl-incident-affected">
          <span className="tl-incident-affected-label">Affected nodes</span>
          <div className="tl-chip-row">
            {affected.map((node) => (
              <span className="tl-chip tl-chip-alert" key={`${node.node_id ?? node.name}`}>
                {node.name}
                {node.reason ? ` — ${node.reason}` : ""}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="tl-incident-infra">
        {INFRA_LABELS.map(({ key, label }) => (
          <div className="tl-incident-infra-item" key={key}>
            <span className="tl-incident-infra-label">{label}</span>
            <HealthBadge state={incident.infrastructure?.[key]} />
          </div>
        ))}
      </div>
    </section>
  );
}
