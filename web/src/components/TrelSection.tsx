import type { MdnsSection, TrelSection as TrelSectionData } from "../api/types";
import { boolText } from "../utils/format";
import { Card, HealthBadge, KeyValue } from "./primitives";

const DEFAULT_FOREIGN_MESSAGE =
  "Other Thread/TREL services are visible on the LAN. This is common when HomePods, Apple TVs, " +
  "Nest devices, or other Thread fabrics are present. ThreadLens does not treat this as a fault by itself.";

export function MdnsTrelSection({ mdns, trel }: { mdns: MdnsSection; trel: TrelSectionData }) {
  const foreignMessage = trel.info?.message || DEFAULT_FOREIGN_MESSAGE;
  const showForeignInfo = Boolean(trel.foreign_service_count) && trel.informational;
  const rawDiffersFromDisplay = trel.health_raw && trel.health_raw !== trel.health;

  return (
    <Card title="mDNS / TREL">
      <KeyValue
        rows={[
          { label: "mDNS health", value: <HealthBadge state={mdns.health} /> },
          { label: "mDNS services", value: mdns.service_count || 0 },
          {
            label: "Observation degraded",
            value: boolText(mdns.observation_degraded, "Yes", "No"),
          },
          { label: "TREL health", value: <HealthBadge state={trel.health} /> },
          ...(rawDiffersFromDisplay
            ? [{ label: "TREL raw health", value: <HealthBadge state={trel.health_raw} /> }]
            : []),
          { label: "TREL services", value: trel.service_count || 0 },
          { label: "Foreign TREL", value: trel.foreign_service_count || 0 },
        ]}
      />

      {showForeignInfo && (
        <div className="tl-info-banner">
          <strong>Other Thread/TREL services visible: {trel.foreign_service_count}</strong>
          <p className="tl-info-text">{foreignMessage}</p>
        </div>
      )}

      {mdns.top_service_types && mdns.top_service_types.length > 0 && (
        <div className="tl-chip-row tl-chip-row-spaced">
          {mdns.top_service_types.map((t) => (
            <span className="tl-chip" key={t.service_type}>
              {t.service_type} <span className="tl-muted">({t.count})</span>
            </span>
          ))}
        </div>
      )}

      <p className="tl-muted tl-note">
        TREL/mDNS visibility is observation only and does not imply device parentage.
      </p>
    </Card>
  );
}
