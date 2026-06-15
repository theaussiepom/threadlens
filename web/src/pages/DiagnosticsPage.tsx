import { useDashboardContext } from "@/context/DashboardContext";
import { Card, ErrorState, LoadingState } from "@/components/ui";

function JsonBlock({ label, value }: { label: string; value: unknown }) {
  return (
    <details className="rounded-lg border border-zl-border bg-zl-bg/40 p-3">
      <summary className="cursor-pointer text-sm font-medium text-zl-text">{label}</summary>
      <pre className="mt-3 overflow-x-auto text-xs text-zl-muted">{JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}

export function DiagnosticsPage() {
  const { data, hasLoaded, error, connected, refresh } = useDashboardContext();

  if (!data && !hasLoaded) return <LoadingState />;
  if (!data && hasLoaded) return <ErrorState message={error || "Cannot reach API"} onRetry={refresh} />;
  if (!connected) return <ErrorState message={error || "Disconnected"} onRetry={refresh} />;
  if (!data) return null;

  const blocks = [
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
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Diagnostics</h1>
        <p className="mt-1 text-zl-muted">Raw dashboard payload sections for support and GitHub issues.</p>
      </div>

      <Card title="Raw payload">
        <div className="space-y-2">
          {blocks.map((b) => (
            <JsonBlock key={b.label} label={b.label} value={b.value} />
          ))}
        </div>
      </Card>
    </div>
  );
}
