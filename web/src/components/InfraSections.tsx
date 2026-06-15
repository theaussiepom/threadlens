import type { MatterSection, MqttSection, ThreadNetwork } from "../api/types";
import { boolText, fmtTime, orDash } from "../utils/format";
import { Card, EmptyHint, HealthBadge, KeyValue } from "./primitives";

export function NetworksSection({ networks }: { networks: ThreadNetwork[] }) {
  if (!networks.length) {
    return (
      <Card title="Thread networks">
        <EmptyHint>No Thread networks reported.</EmptyHint>
      </Card>
    );
  }
  return (
    <Card title="Thread networks">
      {networks.map((n) => (
        <div className="tl-subcard" key={n.extended_pan_id ?? n.name ?? Math.random()}>
          <div className="tl-subcard-head">
            <strong>{n.name || n.extended_pan_id || "Thread network"}</strong>
            <HealthBadge state={n.health} />
          </div>
          <KeyValue
            rows={[
              { label: "Extended PAN ID", value: orDash(n.extended_pan_id) },
              { label: "Channel", value: orDash(n.channel) },
              { label: "PAN ID", value: orDash(n.pan_id) },
              { label: "Classification", value: orDash(n.classification) },
              { label: "Border routers", value: orDash(n.border_router_count) },
            ]}
          />
        </div>
      ))}
    </Card>
  );
}

export function MatterServerSection({ matter }: { matter: MatterSection }) {
  const reasons = matter.reasons ?? [];

  return (
    <Card title={<>Matter servers <HealthBadge state={matter.health} /></>}>
      <KeyValue
        rows={[
          {
            label: "Servers connected",
            value: `${matter.servers_connected || 0} / ${matter.servers || 0}`,
          },
          { label: "Total nodes", value: matter.node_count || 0 },
          { label: "Unavailable nodes", value: matter.unavailable_count || 0 },
          {
            label: "Recent down / up (24h)",
            value: `${matter.recent_unavailable_count || 0} / ${matter.recent_recovered_count || 0}`,
          },
        ]}
      />

      {reasons.length > 0 && (
        <div className="tl-chip-row tl-chip-row-spaced">
          {reasons.map((reason) => (
            <span className="tl-chip tl-chip-alert" key={reason.code} title={reason.label}>
              {reason.label}
            </span>
          ))}
        </div>
      )}
    </Card>
  );
}

export function MqttSectionView({ mqtt }: { mqtt: MqttSection | null }) {
  if (!mqtt) {
    return (
      <Card title="MQTT">
        <EmptyHint>MQTT publishing is not configured.</EmptyHint>
      </Card>
    );
  }
  return (
    <Card title="MQTT">
      <KeyValue
        rows={[
          { label: "Enabled", value: boolText(mqtt.enabled, "Yes", "No") },
          { label: "Connected", value: boolText(mqtt.connected, "Yes", "No") },
          {
            label: "HA Discovery",
            value: boolText(mqtt.homeassistant_discovery_enabled, "Enabled", "Disabled"),
          },
          { label: "Last publish", value: fmtTime(mqtt.last_publish_at) },
          { label: "Last error", value: orDash(mqtt.last_error) },
        ]}
      />
    </Card>
  );
}
