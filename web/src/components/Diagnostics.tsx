import type { DashboardPayload } from "../api/types";
import { Card, Collapsible } from "./primitives";

function JsonBlock({ label, value }: { label: string; value: unknown }) {
  return (
    <Collapsible summary={label}>
      <pre className="tl-pre">{JSON.stringify(value, null, 2)}</pre>
    </Collapsible>
  );
}

export function Diagnostics({ data }: { data: DashboardPayload }) {
  const blocks: { label: string; value: unknown }[] = [
    { label: "Overall", value: data.threadlens },
    { label: "Incident", value: data.incident },
    { label: "Reasons (all)", value: data.threadlens?.reasons_all },
    { label: "Matter", value: data.matter },
    { label: "OTBRs", value: data.otbrs },
    { label: "Networks", value: data.networks },
    { label: "mDNS", value: data.mdns },
    { label: "TREL", value: data.trel },
    { label: "Events", value: data.events },
    { label: "MQTT", value: data.mqtt },
    { label: "Report", value: data.report },
  ];

  return (
    <Card title="Diagnostics" className="tl-diagnostics">
      <p className="tl-muted tl-note">
        Advanced raw payload for GitHub issues and community support. Collapsed by default.
      </p>
      {blocks.map((b) => (
        <JsonBlock key={b.label} label={b.label} value={b.value} />
      ))}
    </Card>
  );
}
